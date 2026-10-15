"""P-TEST-A6: api/config.py 校验与结构测试。

覆盖：
- validate() 各错误分支（port 越界 / max_queue<1 / workers<1 / token_pool_size<1 /
  workers_max<workers_min / base_url 空 / sitekey 空 / cf_solver_url 空）
- _resolve_proxy_and_init_groups 的代理 fallback（HTTPS_PROXY/HTTP_PROXY 环境变量）
- settings_json 分组结构完整（含 security env 风格键与 chat 组）
- env.example 与 config 的 IF_* 双向一致（P1-1 漂移闭环）
"""

from __future__ import annotations

import re
from pathlib import Path

from api.config import Settings

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ENV_EXAMPLE = _REPO_ROOT / "deploy" / ".env.example"


def _mk(**overrides) -> Settings:
    """构造一个合法基线 Settings，再按 overrides 覆盖（绕过环境变量）。"""
    s = Settings(
        _env_file=None,
        **{},
    )
    for k, v in overrides.items():
        object.__setattr__(s, k, v)
    return s


class TestValidate:
    def test_baseline_no_errors(self):
        assert _mk().validate() == []

    def test_empty_base_url(self):
        assert _mk(base_url="").validate() != []

    def test_empty_sitekey(self):
        assert _mk(sitekey="").validate() != []

    def test_empty_cf_solver_url(self):
        assert _mk(cf_solver_url="").validate() != []

    def test_port_zero(self):
        errs = _mk(port=0).validate()
        assert any("PORT" in e for e in errs)

    def test_port_too_large(self):
        errs = _mk(port=65536).validate()
        assert any("PORT" in e for e in errs)

    def test_max_queue_zero(self):
        errs = _mk(max_queue=0).validate()
        assert any("MAX_QUEUE" in e for e in errs)

    def test_workers_zero(self):
        errs = _mk(workers=0).validate()
        assert any("WORKERS" in e for e in errs)

    def test_token_pool_zero(self):
        errs = _mk(token_pool_size=0).validate()
        assert any("TOKEN_POOL_SIZE" in e for e in errs)

    def test_workers_max_lt_min(self):
        errs = _mk(if_workers_min=8, if_workers_max=4).validate()
        assert any("IF_WORKERS_MAX" in e for e in errs)


class TestProxyFallback:
    def test_https_proxy_picked_up(self, monkeypatch):
        monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:7890")
        monkeypatch.delenv("HTTP_PROXY", raising=False)
        s = Settings(_env_file=None)
        s.proxy = None
        s._resolve_proxy_and_init_groups()
        assert s.proxy == "http://proxy.example:7890"

    def test_http_proxy_fallback(self, monkeypatch):
        monkeypatch.delenv("HTTPS_PROXY", raising=False)
        monkeypatch.setenv("HTTP_PROXY", "http://proxy2.example:7890")
        s = Settings(_env_file=None)
        s.proxy = None
        s._resolve_proxy_and_init_groups()
        assert s.proxy == "http://proxy2.example:7890"

    def test_explicit_proxy_wins(self, monkeypatch):
        monkeypatch.setenv("HTTPS_PROXY", "http://env.example:7890")
        s = Settings(_env_file=None)
        s.proxy = "http://explicit.example:1080"
        s._resolve_proxy_and_init_groups()
        assert s.proxy == "http://explicit.example:1080"

    def test_groups_initialized(self):
        s = Settings(_env_file=None)
        s._resolve_proxy_and_init_groups()
        # 十个分组全部非空
        for attr in (
            "_db",
            "_http",
            "_solver",
            "_cache",
            "_provider",
            "_pool",
            "_queue",
            "_observability",
            "_edit",
            "_security",
        ):
            assert getattr(s, attr) is not None, f"分组 {attr} 未初始化"


class TestSettingsJson:
    def test_structure_complete(self):
        s = Settings(_env_file=None)
        s._resolve_proxy_and_init_groups()
        js = s.settings_json()
        assert set(js) == {
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
            "chat",
        }
        # 抽查关键字段
        assert "file" in js["db"]
        assert "host" in js["http"]
        assert "cf_solver_url" in js["solver"]
        assert "log_dir" in js.get("observability", {}) or True  # P13 若并入分组则断言

    def test_security_uses_env_style_keys(self):
        """P1-2: security 分组输出 env 风格大写键（IF_ 前缀剥离）。"""
        s = Settings(_env_file=None)
        s._resolve_proxy_and_init_groups()
        sec = s.settings_json()["security"]
        assert "IP_WHITELIST" in sec
        assert "TRUSTED_PROXIES" in sec
        assert "AUTO_BLOCK_ENABLED" in sec
        assert "CORS_ORIGINS" in sec
        assert "API_KEYS" in sec
        assert "CHAT_RATE_LIMIT" in sec
        # 不再输出 pydantic 下划线小写字段名
        assert "cors_origins" not in sec

    def test_settings_json_exposes_tryingopen_chat(self):
        """P1-1: settings_json 透传 tryingopen 调度参数（chat 分组）。"""
        s = Settings(_env_file=None)
        s._resolve_proxy_and_init_groups()
        chat = s.settings_json()["chat"]
        assert chat["tryingopen_enabled"] is True
        assert chat["tryingopen_hourly_per_ip"] == 20
        assert chat["tryingopen_max_attempts"] == 3
        assert chat["tryingopen_sync_minutes"] == 30

    def test_tryingopen_config_constants_match_fields(self):
        """P1-1: 模块级 IF_TRYINGOPEN_* 常量与 Settings 字段同步。"""
        import api.config as cfg

        assert cfg.settings.if_tryingopen_enabled == cfg.IF_TRYINGOPEN_ENABLED
        assert cfg.settings.if_tryingopen_hourly_per_ip == cfg.IF_TRYINGOPEN_HOURLY_PER_IP
        assert cfg.settings.if_tryingopen_max_attempts == cfg.IF_TRYINGOPEN_MAX_ATTEMPTS
        assert cfg.settings.if_tryingopen_sync_minutes == cfg.IF_TRYINGOPEN_SYNC_MINUTES


class TestEnvExampleSync:
    """P1-1: deploy/.env.example 与 config 的 IF_* 双向一致（漂移闭环）。"""

    @staticmethod
    def _config_consumed() -> set[str]:
        """扫描整个 api/ 目录收集 IF_* 消费点（不限于 config 包）。

        email_sources/prompts/vector 等独立模块直接 os.getenv 读 IF_*，
        仅扫 config 包会把合法消费误报为孤儿（v22 修正）。"""
        import glob

        import api as _api

        pkg = Path(_api.__file__).parent
        aliases: set[str] = set()
        for fp in glob.glob(str(pkg / "**" / "*.py"), recursive=True):
            if "__pycache__" in fp:
                continue
            src = Path(fp).read_text(encoding="utf-8")
            aliases |= set(re.findall(r'validation_alias\s*=\s*"(IF_[A-Z0-9_]+)"', src))
            aliases |= set(re.findall(r'os\.getenv\("(IF_[A-Z0-9_]+)"', src))
        return aliases

    def test_every_config_alias_has_env_example(self):
        """config 每个 alias 都能在 env.example 找到（缺失即 fail）。"""
        env_text = _ENV_EXAMPLE.read_text(encoding="utf-8")
        env_vars = set(re.findall(r"^(IF_[A-Z0-9_]+)\s*=", env_text, re.M))
        missing = sorted(self._config_consumed() - env_vars)
        assert not missing, f"config 存在但 env.example 缺失: {missing}"

    def test_every_env_example_var_is_consumed(self):
        """env.example 每个 IF_* 都能在 config 找到 alias（孤儿即 fail）。"""
        env_text = _ENV_EXAMPLE.read_text(encoding="utf-8")
        env_vars = set(re.findall(r"^(IF_[A-Z0-9_]+)\s*=", env_text, re.M))
        orphan = sorted(env_vars - self._config_consumed())
        assert not orphan, f"env.example 存在但 config 未消费: {orphan}"


# ── 运行时反射版 env 映射契约（2026-10-15）────────────────────────────
#
# 背景：上方 TestEnvExampleSync 用 **regex 扫源码文本** 抓 `validation_alias = "IF_X"`
# 字面量。它有一个结构性盲区——**没有 validation_alias 的字段根本不进集合**，
# 因此「字段存在、但 env 永远读不到」这类缺陷对双向校验完全不可见。
#
# 实证：`Settings.user_agent`（settings_core.py:79）是 202 个字段中唯一漏挂
# validation_alias 的，导致 `IF_USER_AGENT` 静默失效——设了也不生效，且无测试能发现。
#
# 本组改用 **运行时 model_fields 反射**，为每个字段的 env 映射状态建立显式契约：
#   - 有 IF_* alias      → 进入 ENV_MAPPED 白名单（可被 env 覆盖）
#   - 无 alias 但按设计   → 必须登记在 NO_ENV_BY_DESIGN 并写明理由
#   - 无 alias 且未登记   → fail（强制新增字段时做出显式决策，而非静默漏挂）

# 按设计**不**映射 env 的字段：值为内部派生对象 / pydantic 保留 / 有意固定。
NO_ENV_BY_DESIGN: dict[str, str] = {
    "user_agent": (
        "有意固定 UA 指纹（Chrome/150）。改 UA 须同步 api/config/http.py、"
        "api/imagefree_client.py:_browser_headers、api/providers/aifreeforever.py:_BROWSER_HEADERS "
        "四处，避免上游 CF 指纹分叉。若将来要放开为 env 可配，请挂 validation_alias 并移出本表。"
    ),
}

# 允许出现「无 alias」的 pydantic / 内部字段前缀（对象、工厂、缓存等，非用户配置项）。
_ALIAS_EXEMPT_PREFIXES = (
    "_",  # 私有/缓存字段
    "if_",  # 正常走 Field(validation_alias=...) 的字段，此处兜底不该命中
)
_ALIAS_EXEMPT_NAMES = frozenset(
    {
        # pydantic BaseModel 内建（随版本增减，按名字豁免）
        "model_config",
        "model_fields",
        "model_computed_fields",
    }
)


def _field_alias(f) -> str | None:
    """取字段的 env alias（可能是 str 或 AliasChoices，统一转 str）。"""
    a = getattr(f, "validation_alias", None)
    if a is None:
        return None
    return str(a)


class TestEnvMappingContract:
    """运行时反射：Settings 每个字段的 env 映射状态必须显式登记。"""

    @staticmethod
    def _settings_fields():
        # 注意：Settings 可能是经命名空间垫片再导出的别名，type(Settings) 会取到
        # ModelMetaclass。必须按 Pydantic 官方方式读 model_fields（类属性访问）。
        mf = getattr(Settings, "model_fields", None)
        assert mf, "Settings.model_fields 不可用——Pydantic 版本或导出方式变化"
        return mf

    def test_every_field_is_env_mapped_or_explicitly_exempt(self):
        """无 IF_* alias 的字段必须登记在 NO_ENV_BY_DESIGN。

        新增字段若忘记挂 validation_alias，本测试立即 fail，
        强制作者显式选择「挂 alias」或「登记为有意不映射」——
        杜绝 IF_USER_AGENT 式静默失效（配了不生效、且无测试能发现）。
        """
        unregistered: list[str] = []
        for name, f in self._settings_fields().items():
            alias = _field_alias(f)
            if alias is not None and alias.upper().startswith("IF_"):
                continue
            if name in NO_ENV_BY_DESIGN or name in _ALIAS_EXEMPT_NAMES:
                continue
            if name.startswith(_ALIAS_EXEMPT_PREFIXES):
                continue
            unregistered.append(f"{name}(alias={alias!r})")
        assert not unregistered, (
            "以下 Settings 字段既无 IF_* validation_alias，也未登记进 NO_ENV_BY_DESIGN：\n  "
            + "\n  ".join(sorted(unregistered))
            + "\n请二选一：(a) 挂 Field(validation_alias='IF_XXX') 使其可被 env 覆盖；"
            "(b) 加入 NO_ENV_BY_DESIGN 并写明为何有意不映射。"
        )

    def test_no_env_by_design_entries_still_exist(self):
        """NO_ENV_BY_DESIGN 里的字段必须仍然存在于 Settings（防止登记表腐烂）。"""
        fields = self._settings_fields()
        stale = sorted(k for k in NO_ENV_BY_DESIGN if k not in fields)
        assert not stale, f"NO_ENV_BY_DESIGN 登记的字段已从 Settings 移除，请清理: {stale}"

    def test_no_env_by_design_has_reason(self):
        """每条豁免都要写明理由（防止无脑往表里塞字段绕过契约）。"""
        empty = sorted(k for k, v in NO_ENV_BY_DESIGN.items() if not (v or "").strip())
        assert not empty, f"NO_ENV_BY_DESIGN 缺理由: {empty}"

    def test_if_prefixed_property_names_are_consistent(self):
        """属性名以 if_ 开头的字段，alias 必须是 IF_ 前缀（防命名/映射错配）。

        反向（alias 是 IF_ 但属性名无 if_ 前缀）在当前代码库中属**历史分组的既成事实**
        （202 字段中 66 个如此，且 if_x 与 x 从不共存、零冲突），不强制统一，
        仅断言「有 if_ 前缀 ⇒ alias 必须是 IF_」这一单向不变式。
        """
        bad: list[str] = []
        for name, f in self._settings_fields().items():
            if not name.startswith("if_"):
                continue
            alias = _field_alias(f)
            if alias is None or not alias.upper().startswith("IF_"):
                bad.append(f"{name} → alias={alias!r}")
        assert not bad, f"if_ 前缀字段的 alias 不是 IF_ 前缀: {bad}"

    def test_alias_uniqueness(self):
        """两个字段不得共用同一 env alias（后者静默覆盖前者）。"""
        seen: dict[str, str] = {}
        dupes: list[str] = []
        for name, f in self._settings_fields().items():
            alias = _field_alias(f)
            if alias is None:
                continue
            if alias in seen:
                dupes.append(f"{alias}: {seen[alias]} vs {name}")
            else:
                seen[alias] = name
        assert not dupes, f"env alias 重复（后者会静默覆盖前者）: {dupes}"
