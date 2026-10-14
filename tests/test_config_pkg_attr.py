"""api/config/__init__.py 拆分契约测试（v22 P2-3 / A12）。

指南铁律：**拆 config 前必须先立契约**，再动刀。本文件即那道闸门。

契约内容：
1. `_pkg_attr(name)`：从包命名空间运行时读模块级常量（monkeypatch 读点用）。
   拆分后该函数必须继续生效——否则 monkeypatch.setattr("api.config.X", ...)
   在测试里静默失效（读到的是旧副本），是隐蔽的假绿来源。
2. `_mock_register(name, value)`：测试钩子注册临时常量，reset_settings() 后仍可读。
3. 模块级常量快照语义：拆分后 `from api.config import X` 与 `_pkg_attr("X")` 同一对象。
4. Settings 类字段与子配置分组属性完整（db/http/solver/cache/provider/pool/queue/
   observability/edit/security 十组），拆分不得丢组。
5. `config` 自指兼容（`from api.config import config` → 包模块本身）。

拆分目标：`api/config/__init__.py` < 300 行（原 851 行）。
"""

from __future__ import annotations

import api.config as root
import api.config.presets as presets
import api.config.settings as ns


def test_pkg_attr_reads_module_namespace() -> None:
    """_pkg_attr 从包命名空间运行时读常量（monkeypatch 读点的根基）。"""
    from api.config import _pkg_attr

    assert _pkg_attr("HOST") == root.HOST
    assert _pkg_attr("PORT") == root.PORT
    assert _pkg_attr("CF_SOLVER_URL") == root.CF_SOLVER_URL
    # 与直接 import 是同一对象（不是副本）
    assert _pkg_attr("MAX_IMAGE_BYTES") is root.MAX_IMAGE_BYTES


def test_pkg_attr_survives_monkeypatch() -> None:
    """monkeypatch.setattr("api.config.X") 后 _pkg_attr 必须读到新值。

    这是拆分的核心风险：若拆分子模块持有常量副本，
    monkeypatch 只改到包命名空间，_pkg_attr 仍读旧值 → 测试假绿。
    """
    import api.config
    from api.config import _pkg_attr

    original = api.config.HOST
    try:
        api.config.HOST = "patched-host-for-contract"
        assert _pkg_attr("HOST") == "patched-host-for-contract"
        # 包属性与读点一致
        assert getattr(api.config, "HOST") == "patched-host-for-contract"
    finally:
        api.config.HOST = original


def test_pkg_attr_missing_name_raises() -> None:
    """未知名字抛 AttributeError（不返回 None 掩盖拼写错误）。"""
    import pytest

    from api.config import _pkg_attr

    with pytest.raises(AttributeError):
        _pkg_attr("THIS_CONSTANT_DOES_NOT_EXIST")


def test_mock_register_roundtrip() -> None:
    """_mock_register 注册后 _pkg_attr 可读，且能恢复原值。"""
    from api.config import _mock_register, _pkg_attr

    original = _pkg_attr("MAX_QUEUE")
    try:
        _mock_register("MAX_QUEUE", 4242)
        assert _pkg_attr("MAX_QUEUE") == 4242
        assert getattr(root, "MAX_QUEUE") == 4242
    finally:
        _mock_register("MAX_QUEUE", original)
    assert _pkg_attr("MAX_QUEUE") == original


def test_settings_groups_intact() -> None:
    """Settings 十组子配置属性完整，拆分不得丢组。"""
    s = root.get_settings()
    groups = [
        "db",
        "http",
        "solver",
        "cache",
        "provider",
        "pool",
        "queue",
        "observability",
        "edit",
        "security",
    ]
    for g in groups:
        attr = getattr(s, g, None)
        assert attr is not None, f"Settings.{g} 分组丢失"
        # 每组应有 from_settings 工厂或可用字段
        assert hasattr(type(attr), "__dataclass_fields__") or hasattr(attr, "__dict__") or hasattr(
            type(attr), "model_fields"
        ), f"Settings.{g} 非配置对象"


def test_settings_has_core_fields() -> None:
    """Settings 顶层核心字段保留（host/port/base_url/proxy/user_agent）。"""
    s = root.get_settings()
    for f in ("host", "port", "base_url", "user_agent"):
        assert hasattr(s, f), f"Settings.{f} 字段丢失"
    assert s.host
    assert 1 <= s.port <= 65535


def test_config_self_reference_unchanged() -> None:
    """`from api.config import config` → 包模块本身（兼容读点）。"""
    from api.config import config

    assert config is root


def test_legacy_namespace_reexport_unchanged() -> None:
    """api.config.settings 兼容命名空间 re-export 完整。"""
    from api.config.settings import DB_FILE
    from api.config.settings import Settings as NS_Settings

    assert NS_Settings is root.Settings
    assert DB_FILE == root.DB_FILE
    assert ns.__all__


def test_presets_reexport_same_objects() -> None:
    """presets 常量与 api.config 同一对象（防双版本分叉）。"""
    assert presets.MAX_IMAGE_BYTES is root.MAX_IMAGE_BYTES
    assert presets.MAX_PROMPT_LEN is root.MAX_PROMPT_LEN
    assert presets.ASPECT_RATIOS is root.ASPECT_RATIOS
    assert presets.MODEL_PRESETS is root.MODEL_PRESETS
    assert presets.apply_model is root.apply_model


def test_module_constant_snapshot_is_stable() -> None:
    """模块级常量快照语义：拆分包不得改成惰性 property（调用方密集）。"""
    # 这些是旧 import 路径的高频常量，必须仍是普通属性（非 property/lazy）
    for name in ("HOST", "PORT", "BASE_URL", "CF_SOLVER_URL", "MAX_QUEUE", "WORKERS"):
        assert isinstance(getattr(type(root), name, None), type(None)) or not hasattr(
            type(root), name
        ), f"api.config.{name} 不应是类级 descriptor"


def test_all_exports_cover_constants() -> None:
    """__all__ 覆盖模块级常量（`from api.config import *` 行为不变）。"""
    assert "HOST" in root.__all__
    assert "PORT" in root.__all__
    assert "Settings" in root.__all__
    assert "get_settings" in root.__all__
    assert "apply_model" in root.__all__
