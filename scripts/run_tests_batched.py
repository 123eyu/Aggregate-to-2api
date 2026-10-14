"""分批跑后端单测（规避宿主进程 kill —— 单次 pytest 进程存活过久会被终止）。

用法：
    ./.venv/Scripts/python.exe scripts/run_tests_batched.py [--batch-size 12] [--filter "not integration and not chaos and not slow"]

设计要点：
- 用**独立的 pytest 子进程**逐批执行（不是同进程多次调用），每批结束即释放，
  避免长驻进程被宿主 kill 后丢失全部结果。
- 结果增量写盘（JSON + 文本），中断后可用 --resume 从断点续跑。
- 汇总输出：总通过/失败/错误文件，以及失败文件的完整输出（截断保存）。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = ROOT / "tests"
PY = ROOT / ".venv" / "Scripts" / "python.exe"
if not PY.exists():
    PY = Path(sys.executable)

# Windows GBK 终端无法打印非 ASCII 汇总文案 —— 强制 UTF-8 输出
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

RESULT_JSON = ROOT / "data" / "batched_test_results.json"
RESULT_TXT = ROOT / "data" / "batched_test_results.txt"


def collect_test_files() -> list[str]:
    files = sorted(p.name for p in TESTS_DIR.glob("test_*.py"))
    return files


def _count_from_progress(out: str) -> dict:
    """从 pytest `-q` 的进度行（`....F...  [ 49%]`）数出结果符号。

    为何不用尾部摘要行 / --junitxml：本仓库 `tests/conftest.py` 的
    `pytest_sessionfinish` 调 `os._exit(exitstatus)` 兜底退出（Windows 本地
    teardown 永不返回），它在 terminal reporter 与 junitxml 插件写盘**之前**
    结束进程 —— 实测摘要行与 junit XML 都不会生成。

    但 `-q` 的进度行是**逐字符实时输出**的，在 sessionfinish 之前就已落盘，
    因此按符号计数可靠：
      `.` 通过 / `F` 失败 / `E` 错误 / `s` 跳过 / `x` xfail / `X` xpass
    """
    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for raw in out.splitlines():
        line = raw.strip()
        # 去掉行尾的 `[ 49%]`
        line = re.sub(r"\[\s*\d+%\]\s*$", "", line).strip()
        if not line or not re.fullmatch(r"[.FEsxX]+", line):
            continue
        counts["passed"] += line.count(".")
        counts["failed"] += line.count("F")
        counts["errors"] += line.count("E")
        counts["skipped"] += line.count("s") + line.count("x") + line.count("X")
    return counts


def run_batch(files: list[str], marker_filter: str, timeout: int) -> dict:
    """跑一批；返回 {files, exit, passed, failed, errors, duration, output_tail}。"""
    cmd = [
        str(PY),
        "-m",
        "pytest",
        *[f"tests/{f}" for f in files],
        "-q",
        "-p",
        "no:cacheprovider",
        "--no-header",
    ]
    if marker_filter:
        cmd += ["-m", marker_filter]

    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        code = proc.returncode
    except subprocess.TimeoutExpired as e:
        raw = e.stdout or ""
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "replace")
        out = f"[TIMEOUT after {timeout}s]\n" + raw
        code = -9
    dur = time.time() - t0

    counts = _count_from_progress(out)
    tail = ""
    if code not in (0, 1) or counts["failed"] or counts["errors"]:
        tail = "\n".join(out.strip().splitlines()[-60:])

    return {
        "files": files,
        "exit": code,
        "passed": counts["passed"],
        "failed": counts["failed"],
        "skipped": counts["skipped"],
        "errors": counts["errors"],
        "duration": round(dur, 1),
        "summary": f"progress: {counts['passed']} passed / {counts['failed']} failed / "
        f"{counts['errors']} errors / {counts['skipped']} skipped",
        "output_tail": tail,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-size", type=int, default=12)
    ap.add_argument("--filter", default="not integration and not chaos and not slow")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--resume", action="store_true", help="跳过已完成批次")
    ap.add_argument("--only", default="", help="只跑名称含此子串的文件")
    ap.add_argument("--files", default="", help="只跑指定文件（逗号分隔，可省 test_ 前缀与 .py）")
    args = ap.parse_args()

    files = collect_test_files()
    if args.only:
        files = [f for f in files if args.only in f]
    if args.files:
        want = []
        for raw in args.files.split(","):
            name = raw.strip()
            if not name:
                continue
            if not name.endswith(".py"):
                name += ".py"
            if not name.startswith("test_"):
                name = "test_" + name
            want.append(name)
        missing = [w for w in want if w not in files]
        if missing:
            print(f"[ERROR] 未知测试文件: {missing}", flush=True)
            return 2
        files = want

    batches = [files[i : i + args.batch_size] for i in range(0, len(files), args.batch_size)]
    print(f"共 {len(files)} 个测试文件 → {len(batches)} 批（每批 {args.batch_size}）", flush=True)

    all_results: list[dict] = []
    covered: set[str] = set()
    if args.resume and RESULT_JSON.exists():
        try:
            all_results = json.loads(RESULT_JSON.read_text(encoding="utf-8"))
            # 已覆盖 = **正常终止**批次（exit 0/1）的文件并集。
            # 必须排除超时/异常终止批次（exit=-9 等），否则：
            #   (a) 汇总会把没跑完的文件算作已覆盖；
            #   (b) --resume 会判定"全部已完成"而跳过，超时批次永不重试。
            covered = {f for r in all_results if r.get("exit") in (0, 1) for f in r.get("files", [])}
            print(
                f"resume：已有 {len(all_results)} 批结果，已覆盖 {len(covered)} 个文件"
                f"（{len(all_results) - sum(1 for r in all_results if r.get('exit') in (0, 1))} 批异常终止，将重试）",
                flush=True,
            )
        except Exception:
            all_results = []
            covered = set()

    for idx, batch in enumerate(batches):
        pending = [f for f in batch if f not in covered]
        if not pending:
            print(f"\n[批 {idx + 1}/{len(batches)}] 已完成，跳过", flush=True)
            continue
        print(f"\n[批 {idx + 1}/{len(batches)}] {len(pending)} 文件…", flush=True)
        r = run_batch(pending, args.filter, args.timeout)
        all_results.append(r)
        # 仅正常终止（exit 0=全过 / 1=有失败）且无未捕获失败符号时才标记为已覆盖。
        # 超时(-9)/异常终止不得标记，否则 --resume 会静默跳过这批（S6）；
        # 含 F/E 的批次即使 exit=1 也保留（供 bisect），但视为已完成以免死循环。
        if r["exit"] in (0, 1):
            covered.update(pending)
        else:
            print(f"  ⚠ exit={r['exit']} 异常终止，本批不计入已覆盖（--resume 会重试）", flush=True)
        status = "OK" if (r["exit"] == 0 and not r["failed"] and not r["errors"]) else "FAIL"
        print(f"  {status} exit={r['exit']} | {r['summary']} | {r['duration']}s", flush=True)
        if r["failed"] or r["errors"] or r["exit"] not in (0, 1):
            print(f"  尾部:\n{r['output_tail'][-1200:]}", flush=True)

        # 增量落盘
        RESULT_JSON.parent.mkdir(parents=True, exist_ok=True)
        RESULT_JSON.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")

    # 汇总（按文件去重：同一文件可能出现在多批结果中）
    total_p = sum(r["passed"] for r in all_results)
    total_f = sum(r["failed"] for r in all_results)
    total_e = sum(r["errors"] for r in all_results)
    bad = [r for r in all_results if r["exit"] != 0]
    missing = sorted(set(files) - covered)

    lines = [
        "=" * 60,
        f"分批测试汇总  批次 {len(all_results)}  覆盖文件 {len(covered)}/{len(files)}",
        f"passed={total_p}  failed={total_f}  errors={total_e}",
        f"失败批次：{len(bad)}",
    ]
    if missing:
        lines.append(f"未覆盖文件（{len(missing)}）: {', '.join(missing[:20])}{' …' if len(missing) > 20 else ''}")
    lines.append("=" * 60)
    for r in bad:
        lines.append(f"\n--- exit={r['exit']} | {r['summary']} ---")
        lines.append(f"文件: {', '.join(r['files'])}")
        lines.append(r["output_tail"])
    report = "\n".join(lines)
    RESULT_TXT.write_text(report, encoding="utf-8")
    print("\n" + report, flush=True)

    return 1 if (bad or missing) else 0


if __name__ == "__main__":
    sys.exit(main())
