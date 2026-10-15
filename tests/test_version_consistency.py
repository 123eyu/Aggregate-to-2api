"""版本全链一致性门禁（v21 T1）。

读取全链版本号源并断言彼此一致 + 符合 semver；同时校验 scripts/e2e_v12.py
的契约断言版本与全链一致（防漂移）。CI 首步 fail-fast。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def _extract(pattern: str, path: Path, group: int = 1) -> str:
    m = re.search(pattern, path.read_text(encoding="utf-8"), flags=re.MULTILINE)
    assert m, f"在 {path.relative_to(ROOT)} 中未找到匹配 {pattern!r}"
    return m.group(group)


@pytest.fixture(scope="module")
def version_sources() -> dict[str, str]:
    """全链版本源 → 提取的版本串。"""
    return {
        "pyproject.toml": _extract(r'^version = "([^"]+)"', ROOT / "pyproject.toml"),
        "deploy/pyproject.toml": _extract(r'^version = "([^"]+)"', ROOT / "deploy" / "pyproject.toml"),
        "api/main.py": _extract(r'version="([^"]+)"', ROOT / "api" / "main.py"),
        "frontend/package.json": _extract(r'"version": "([^"]+)"', ROOT / "frontend" / "package.json"),
        "landing/package.json": _extract(r'"version": "([^"]+)"', ROOT / "landing" / "package.json"),
        "desktop/package.json": _extract(r'"version": "([^"]+)"', ROOT / "desktop" / "package.json"),
        "desktop/src-tauri/tauri.conf.json": _extract(
            r'"version": "([^"]+)"', ROOT / "desktop" / "src-tauri" / "tauri.conf.json"
        ),
        "desktop/src-tauri/Cargo.toml": _extract(
            r'^version = "([^"]+)"', ROOT / "desktop" / "src-tauri" / "Cargo.toml"
        ),
        "README.md": _extract(r"version-([0-9]+\.[0-9]+\.[0-9]+)", ROOT / "README.md"),
    }


def test_all_sources_exist() -> None:
    """全链版本源文件必须存在（H1：防拷贝漏文件——先于提取给清晰失败信息而非裸 assert）。"""
    missing = [
        rel
        for rel in (
            "pyproject.toml",
            "deploy/pyproject.toml",
            "api/main.py",
            "frontend/package.json",
            "landing/package.json",
            "desktop/package.json",
            "desktop/src-tauri/tauri.conf.json",
            "desktop/src-tauri/Cargo.toml",
            "README.md",
        )
        if not (ROOT / rel).exists()
    ]
    assert not missing, f"版本全链缺失文件: {missing}（请先补全再跑版本门禁）"


def test_all_sources_parse_semver(version_sources: dict[str, str]) -> None:
    """每个源都提取到合法的 X.Y.Z。"""
    for name, ver in version_sources.items():
        assert SEMVER.match(ver), f"{name} 版本 {ver!r} 非合法 semver"


def test_all_sources_agree(version_sources: dict[str, str]) -> None:
    """全链版本彼此相等。"""
    values = list(version_sources.values())
    assert len(set(values)) == 1, f"版本漂移: {version_sources}"


def test_e2e_v12_contract_matches(version_sources: dict[str, str]) -> None:
    """scripts/e2e_v12.py 的契约断言版本必须与全链一致（防上次 20.0.0 漂移复发）。"""
    expected = version_sources["api/main.py"]
    e2e = (ROOT / "scripts" / "e2e_v12.py").read_text(encoding="utf-8")
    # 匹配任意 X.Y.Z 契约断言（勿硬编码 20.x——版本升级后 hits 会空导致误报）
    hits = re.findall(r'"(\d+\.\d+\.\d+)"', e2e)
    assert hits, "e2e_v12.py 中未找到版本契约断言"
    for hit in hits:
        assert hit == expected, f"e2e_v12 契约版本 {hit} != 全链 {expected}"


# ── 文档版本漂移门禁（2026-10-15）────────────────────────────────────
#
# 背景：`scripts/sync_version.py` 的 TARGETS 只覆盖 10 个代码/配置文件，
# **不含 .claude/skills/** 下的开发文档。实证：2026-10-15 审计时 SKILL.md
# 写「当前版本 v23.1.0」，而实际已是 v23.2.0——漂移 2 个小版本且无人发现。
#
# 处置选择：**不把 skill 文档塞进 sync_version 自动改写**（其版本号是叙述性中文
# 文字，格式多样，正则替换易误伤），改为**加门禁测试**——漂移即红，由人确认后手工改。

# (相对路径, 提取正则, 说明) —— 版本号必须与全链一致
_DOC_VERSION_TARGETS: list[tuple[str, str]] = [
    (
        ".claude/skills/imagefree-workflow/SKILL.md",
        r"当前版本 v(\d+\.\d+\.\d+)",
    ),
]


def test_dev_doc_version_not_drifted(version_sources: dict[str, str]) -> None:
    """开发文档里声明的版本必须与全链一致（防 SKILL.md 式静默漂移）。

    漂移时给出明确修复指引：手工改文档中的版本串，而非跑 sync_version
    （后者不覆盖文档文件）。
    """
    expected = version_sources["api/main.py"]
    drifted: list[str] = []
    for rel, pattern in _DOC_VERSION_TARGETS:
        p = ROOT / rel
        if not p.exists():
            continue  # 文档可选；缺失不判失败（与 OPTIONAL_TARGETS 语义一致）
        m = re.search(pattern, p.read_text(encoding="utf-8"))
        assert m, f"{rel} 中未匹配到版本声明（正则 {pattern!r}）——文档结构可能已改，请同步本测试"
        found = m.group(1)
        if found != expected:
            drifted.append(f"{rel}: 文档写 {found}，全链为 {expected}")
    assert not drifted, (
        "开发文档版本漂移（sync_version.py 不覆盖文档，需手工修改）:\n  "
        + "\n  ".join(drifted)
        + "\n修复：把文档中的版本串改为全链版本；本测试有意不做自动改写。"
    )
