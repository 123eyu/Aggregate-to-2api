"""IF_CORS_ORIGINS 环境变量必须真正生效（回归锁）。

## 背景（真实缺陷）

`api/main.py` 挂载 CORSMiddleware 时读 `config.CORS_ORIGINS`：

    allow_origins=[o.strip() for o in (config.CORS_ORIGINS or "*").split(",") if o.strip()]

但该值曾被硬编码为字面量 `"*"`，导致**设置 `IF_CORS_ORIGINS` 环境变量完全无效**——
运维以为收紧了 CORS 白名单，实际仍是 `allow_origins=["*"]`。属安全相关的静默失效。

历史成因（拆分前就存在）：`Settings.__init__` 内的 `global CORS_ORIGINS` 与模块级
字面量 `CORS_ORIGINS = "*"` 同处 `api.config` 命名空间，字面量在后执行 → 覆盖 env 值。
拆包后 `global` 写的是 `settings_core` 命名空间，与包命名空间更不相干。
修复：`constants.py` 改为读单例 + `Settings.__init__` 同布包命名空间。

本文件锁死"env 必须生效"，防止再次静默退化。
"""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def fresh_config(monkeypatch):
    """在受控 env 下重新导入 api.config，返回包模块。

    注意：`constants.py` 在 import 期绑定 CORS_ORIGINS，故必须**重新导入**才能
    观察到 import 期行为（用 importlib.reload 链）。
    """
    import api.config as config
    import api.config.constants as constants
    import api.config.settings_core as settings_core

    yield config, constants, settings_core

    # 还原：清 env 后重建，避免污染其他用例
    monkeypatch.delenv("IF_CORS_ORIGINS", raising=False)
    settings_core.reset_settings()


def test_env_value_reaches_package_namespace(monkeypatch, fresh_config):
    """核心回归：设了 env，`api.config.CORS_ORIGINS`（main.py 读的那个）必须变。"""
    config, constants, settings_core = fresh_config
    monkeypatch.setenv("IF_CORS_ORIGINS", "https://prod.example.com,https://admin.example.com")
    settings_core.reset_settings()

    assert config.CORS_ORIGINS == "https://prod.example.com,https://admin.example.com", (
        "IF_CORS_ORIGINS 未生效 —— main.py 会退回 allow_origins=['*']，属安全静默失效"
    )


def test_env_value_reaches_constants_snapshot(monkeypatch):
    """constants.py 的快照读点也必须在 import 期取到 env 值（非字面量）。"""
    monkeypatch.setenv("IF_CORS_ORIGINS", "https://snapshot.example.com")
    import api.config.constants as constants
    import api.config.settings_core as settings_core

    settings_core.reset_settings()
    importlib.reload(constants)

    assert constants.CORS_ORIGINS == "https://snapshot.example.com"


def test_default_is_wildcard_without_env(monkeypatch, fresh_config):
    """未设 env 时回退 "*"（保持公益开放默认，行为不可变）。"""
    config, _constants, settings_core = fresh_config
    monkeypatch.delenv("IF_CORS_ORIGINS", raising=False)
    settings_core.reset_settings()

    assert config.CORS_ORIGINS == "*"


def test_empty_env_falls_back_to_wildcard(monkeypatch, fresh_config):
    """空字符串 env 视为未配置 → "*"（避免生成 allow_origins=[] 导致全站 CORS 失败）。"""
    config, _constants, settings_core = fresh_config
    monkeypatch.setenv("IF_CORS_ORIGINS", "")
    settings_core.reset_settings()

    assert config.CORS_ORIGINS == "*"


def test_main_reads_package_attr(monkeypatch, fresh_config):
    """契约：main.py 通过 `config.CORS_ORIGINS` 读取——确认该属性存在且可解析为列表。"""
    config, _constants, settings_core = fresh_config
    monkeypatch.setenv("IF_CORS_ORIGINS", "https://a.example.com, https://b.example.com")
    settings_core.reset_settings()

    parsed = [o.strip() for o in (config.CORS_ORIGINS or "*").split(",") if o.strip()]
    assert parsed == ["https://a.example.com", "https://b.example.com"]
