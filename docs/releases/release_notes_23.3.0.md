# v23.3.0 — 终局审计批：CI 真实性 + 静默失效修复

**发布日期**：2026-10-15
**基线**：v23.2.0 (`79a5374`)
**性质**：缺陷修复批（无新功能、无破坏性变更、无需迁移）

---

## 一句话

本批修掉 5 个真缺陷（含 2 个静默失效、1 个让整条 CI 前端门禁持续红的系统性缺陷），
并**发现 CI 已整体失败约一个月**这一此前无人注意到的事实。

---

## 本批修复

### P1 · `api/bg_tasks.py` — 定时清理循环每次中途抛异常，后半段从未执行

`_engine._queue_db` 中 `_engine` 是**模块**（`from .worker import engine`），
而 `_queue_db` 是 `Engine` 的**实例属性** → 每次必抛 `AttributeError`。

异常被外层 `except Exception` 吞成 `warning`，且因抛在 `try` 块**中部**，
**导致其后所有清理逻辑（DAG run TTL 清理、告警评估 `evaluate`）被长期跳过**。

- 修复：改从 `api.meta` 取 Engine 单例（与 lifespan 注入同一实例）+ 防御式 `getattr`
- 回归：`tests/test_db_retention.py` 3 用例（**AST 级断言**——字符串匹配会被改名绕过）

### P1 · 前端 `Vitest` 门禁持续红 — 测试套件系统性 DOM 泄漏

`frontend/vite.config.ts` 设了 `isolate: false`，并在注释中**声称**
「测试间通过 `src/test/setup.ts` 的 beforeEach 清理」——但该文件**从未有任何清理逻辑**。

CI 实证（annotations）多个测试文件同时报
`TestingLibraryElementError: Found multiple elements with role "button"/"dialog"/"combobox"`。

- 修复：`setup.ts` 显式注册 `afterEach(() => cleanup())`
- 配置注释改为与实现一致，并标注「`isolate:false` 与该 cleanup 是配套的，改一方须检查另一方」
- **⚠ 本地无法判别**：本机（Node 25）全套件 299 passed，且摘掉 cleanup 的变异测试本地也全绿 →
  复现不出 CI（Node 20）症状。**此修复需推送后重跑 CI 确认。**

### P1 · 覆盖率门槛文档与 CI 不一致（70 vs 80）

`ci.yml:53` / `deploy.yml:30` 为 `--cov-fail-under=80`，而开发文档写 **70**。
危害具体：**按文档自测 70% 通过 → 推 CI 撞 80% 意外失败**（根源是 v7.6 统一到 80 时文档未同步）。

- 修复 4 处（仅 `.claude/skills/` 权威副本；`.agents/` 为未入库旧镜像，不动）

### P2 · SSE / WebSocket 多订阅者场景误清回放缓冲

`sse_events.py:246` 与 `ws_events.py:125` 的连接收尾**无条件**调 `clear_task`。
同一任务被 2+ 客户端订阅时（多标签页、或重连旧连接尚未断开），先断开的一方会清掉
**共享**的事件缓冲 → 另一方之后用 `Last-Event-ID` 重连**拿不到任何历史，且不报错**（静默降级）。

- 修复：新增 `clear_task_if_idle`，把「判空」与「清理」放进**同一把锁**（避免 check-then-act 竞态）
- 回归 5 用例：行为 3 + **调用点契约 2**（后者必要——第一版只测方法不测调用点，变异测试证明它是伪测试）

### P2 · 环境变量映射契约的结构性盲区

既有校验用 **regex 扫源码文本**抓 `validation_alias="IF_X"` 字面量 →
**没有 alias 的字段根本不进集合**，故「字段存在但 env 永远读不到」这类缺陷对它完全不可见。
实证：`Settings.user_agent` 是 202 个字段中**唯一**漏挂 alias 的。

- 修复：新增 `TestEnvMappingContract`（运行时 `model_fields` 反射 + `NO_ENV_BY_DESIGN` 显式登记表，5 用例）
- 新增字段若忘记挂 alias → 测试立刻红，强制作者做显式决策

### P2 · `deploy/.env.example` 注释指向错误的修复文件

注释称「改 UA 需改 `api/config/http.py`」，但那里是**死副本**
（`HTTPSettings.from_settings()` 会无条件用 `s.user_agent` 覆盖）；
20 处生产代码实际消费的是 `config.USER_AGENT`（源自 `api/config/settings_core.py`）。
**照注释去改，等于白改一场。**

- 修复：注释重写，指明权威文件 + 4 处需同步的位置 + 契约测试位置

### P2 · skill 文档版本漂移

`SKILL.md` 写 v23.1.0，实际已是 v23.2.0（版本门禁只覆盖 10 个代码文件，**不含文档**）。

- 修复：版本修正 + 新增门禁 `test_dev_doc_version_not_drifted`（漂移即红，不做自动改写）

---

## 环境 / 基建改善

- **前端测试套件从"完全跑不起来"到 299/299**：根因是 `NODE_OPTIONS=--max-old-space-size=512`
  太小导致 vitest worker 起不来。设 `4096` 后 28 files / 299 tests 全绿（139s）。
  **排查顺序已固化进 skill：先堆内存 → 再路径 → 最后机器负载。**
- `.claude/skills/imagefree-workflow/SKILL.md` 新增「CI 现状」告警块 + 取 CI 失败原因的方法。

---

## 文档

- 新增 `docs/2026-10-15-audit-report.html`（上下文 / 直觉 / 变更 / 未闭环项 / **10 题测验**）
- `workflow_status.md` 重建为事实台账（含 9 项"伪问题"判定记录，避免重复劳动）
- `.wolf/memory.md` 追加本批 15 条可复用事实

---

## 验证（真实执行）

```
ruff check api/ tests/ scripts/          → All checks passed!
pytest tests/test_version_consistency.py → 5 passed
pytest tests/test_config_validate.py     → 25 passed
pytest tests/test_db_retention.py        → 16 passed
pytest tests/test_sse_events_unit.py     → 32 passed
pytest 受影响集合（5 文件）                → 83 passed, 1 skipped
frontend: NODE_OPTIONS=4096 npx vitest run → 28 files / 299 tests passed
frontend: npx tsc -b                       → exit 0
scripts/probe_route_methods.py             → 前端 31 路径全部存在，0 断链
scripts/e2e_mobile_smoke.cjs               → 9 passed / 0 failed（真实 chromium）
12 端点冒烟                                 → 全 200
```

**变异验证 5 组**：env 契约 / 文档版本门禁 / `bg_tasks` 回归 / SSE 调用点契约 **均有判别力**；
SSE 行为测试第一版**无**判别力 → 已补调用点契约。

---

## 已知未闭环（诚实披露）

| 项 | 原因 |
|---|---|
| 前端 CI 修复的确认 | 本机（Node 25）复现不出 CI（Node 20）症状，需推送后重跑 CI 确认 |
| 后端 CI 失败的具体原因 | 失败 job 仅给 `exit code 1`；日志下载需 admin 权限 |
| 全量覆盖率真实数字 | 本机全量被 `--timeout=120` 中断（`test_tryingopen.py::no_sleep`） |
| 线上部署 | 主机 `20.204.27.154` TCP 22/80/443/8100 全部超时（DNS 正常）；按挂机处理 |

**三项安全项：报告但未擅自修改**（属生产策略决策，需授权）：

1. `/v1/logs` + `/v1/logs/ws` 匿名可读实时日志 —— 代码 docstring 明写「v7.7.8 公益只读开放」，属**有意设计**
2. `public_keymask()` 经 `/v1/chat/auth/status` 回显 Key 前 12 字符（41%）—— 当前 `IF_API_KEYS` 为空故未触发
3. `POST /v1/agent/memory/observe` 未授权写入 —— 匿名可写 agent 记忆（投毒面）

---

## 升级说明

无破坏性变更。无需迁移。版本全链 10 文件 + 双 dist 已同步至 23.3.0。
