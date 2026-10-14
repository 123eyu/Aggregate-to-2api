"""imagefree_api 配置包。全部可用环境变量覆盖，便于部署。

v22 P2-3 / A12 拆分（851 行 → <300 行垫片）：
- Settings 类 + get_settings/reset_settings 工厂 → `settings_core.py`
- 模块级便捷常量快照（HOST/PORT/...）→ `constants.py`
- 纯常量 + apply_model → `presets.py`
- OpenTelemetry 配置 → `otlp.py`
- Settings 级聚合函数（apply_adaptive_defaults/validate_settings/settings_json）→ `base.py`
- 子配置类（DBSettings 等）各在独立子模块，暴露 `from_settings(cls, s)` 工厂

向后兼容全部保留：`from api.config import Settings / settings / get_settings / HOST / ...` 不变。

**monkeypatch 读点**：测试改常量必须用 `_pkg_attr(name)`（运行时读本包命名空间），
直接 `from api.config import HOST` 拿到的是 import 期副本，setattr 后不生效。
"""

from __future__ import annotations

import sys

from .base import apply_adaptive_defaults, settings_json, validate_settings  # noqa: F401
from .cache import CacheSettings  # noqa: F401
from .constants import *  # noqa: F401,F403  (模块级常量快照)
from .db import DBSettings  # noqa: F401
from .edit import EditSettings  # noqa: F401
from .http import HTTPSettings  # noqa: F401
from .observability import ObservabilitySettings  # noqa: F401
from .otlp import (  # noqa: F401
    OTEL_CONSOLE_EXPORTER,
    OTEL_ENABLED,
    OTEL_ERROR_SAMPLE_RATE,
    OTEL_EXPORTER_OTLP_ENDPOINT,
    OTEL_SAMPLE_RATE,
    OTEL_SERVICE_NAME,
)
from .pool import PoolSettings  # noqa: F401
from .presets import (  # noqa: F401
    ASPECT_RATIOS,
    MAX_IMAGE_BYTES,
    MAX_PROMPT_LEN,
    MODEL_PRESETS,
    apply_model,
)
from .provider import ProviderSettings  # noqa: F401
from .queue import QueueSettings  # noqa: F401
from .security import SecuritySettings  # noqa: F401
from .settings_core import Settings, get_settings, reset_settings, settings  # noqa: F401
from .solver import SolverSettings  # noqa: F401


def _pkg_attr(name: str):
    """运行时从 api.config 包命名空间读模块级常量（monkeypatch 读点）。

    与 `from api.config import HOST` 的区别：后者是 import 期副本，
    monkeypatch.setattr("api.config.HOST", v) 之后副本不变 → 测试假绿。
    本函数每次走 getattr(包模块)，因此 setattr 立即生效。

    未知名抛 AttributeError（不返回 None 掩盖拼写错误）。
    """
    return getattr(sys.modules[__name__], name)


def _mock_register(name: str, value) -> None:
    """测试钩子：在 api.config 包命名空间注册/覆盖常量（_pkg_attr 立即可读）。

    配合 _pkg_attr 使用；恢复原值只需再次 _mock_register(name, original)。
    """
    setattr(sys.modules[__name__], name, value)


# ── 兼容：`from api.config import config` 使 config 指代包模块本身 ──
config = sys.modules[__name__]

# ── 导出所有模块级变量名 ──────────────────────────────
# 程序化生成 __all__，覆盖所有非下划线开头的模块级名字（含子配置类、Settings、
# 工厂函数、constants 快照、presets re-export、config、_pkg_attr/_mock_register 由
# 显式追加保证可导出——它们供测试 import，故加入名单）。
__all__ = [name for name in globals() if not name.startswith("_")]
__all__ += ["_pkg_attr", "_mock_register"]
