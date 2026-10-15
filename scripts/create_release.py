"""创建 GitHub Release（复用 git credential manager 已存凭据，不打印密钥）。

用法：
    ./.venv/Scripts/python.exe scripts/create_release.py v23.3.1
凭据来源：`git credential fill`（与 git push 同源）。
注意：本机 schannel 吊销检查离线，纯 urllib 调 GitHub 会失败，
故此处显式禁用代理 + 依赖系统 CA 是否可用；若不行请改用 curl --ssl-no-revoke。
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import urllib.error
import urllib.request

REPO = "lza6/Aggregate-to-2api"


def github_token() -> str:
    """从 git credential manager 取 github.com 凭据（不落盘、不打印）。"""
    r = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"},
    )
    for line in (r.stdout or "").splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1].strip()
    return ""


def main() -> int:
    tag = sys.argv[1] if len(sys.argv) > 1 else "v23.3.1"
    notes_path = pathlib.Path(f"docs/releases/release_notes_{tag.lstrip('v')}.md")
    if not notes_path.exists():
        print(f"BLOCKED: 找不到发行说明 {notes_path}")
        return 2

    title = subprocess.run(
        # encoding/errors 必须显式指定：tag 备注含 UTF-8 破折号（—），
        # Windows 默认 GBK 解码会抛 UnicodeDecodeError 并让 stdout 变 None。
        ["git", "tag", "-l", "-n1", tag],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    ).stdout.strip()
    name = title.split(maxsplit=1)[1].splitlines()[0] if " " in title else tag

    token = github_token()
    if not token:
        print("BLOCKED: 未从 git credential manager 取到 github.com 凭据")
        return 3

    payload = json.dumps(
        {
            "tag_name": tag,
            "name": name,
            "body": notes_path.read_text(encoding="utf-8"),
            "draft": False,
            "prerelease": False,
        },
        ensure_ascii=False,
    ).encode("utf-8")

    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/releases",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "imagefree-release",
        },
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=60) as resp:
            d = json.loads(resp.read().decode("utf-8"))
            print(f"OK Release created: id={d['id']} tag={d['tag_name']} draft={d['draft']}")
            print(f"   url={d['html_url']}")
        return 0
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        if e.code == 422 and "already_exists" in body:
            print(f"SKIP: {tag} 的 Release 已存在")
            return 0
        print(f"FAIL HTTP {e.code}: {body[:300]}")
        return 4
    except Exception as e:  # noqa: BLE001
        print(f"FAIL {type(e).__name__}: {e}")
        return 5


if __name__ == "__main__":
    sys.exit(main())
