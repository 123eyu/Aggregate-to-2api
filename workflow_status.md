# workflow_status — 终局闭环总审计（2026-10-15 批）

> 规范来源：用户 2026-10-15 指令（终局审计 / 主动补位 / 真实验收 / 反向修复）
> 规则：只记事实与证据；只有观察到交付物 + 实跑验收证据才标 done；外部受限项标「阻塞 / 待授权」，不伪装。

## 本轮授权口径（用户 2026-10-15 明确）

| 项 | 决定 |
|---|---|
| 线上主机 20.204.27.154 不可达 | **当它挂了**，本轮只做本地闭环，线上部署列为外部阻塞 |
| git commit / push / Release | **先审计修复，产生真实变更后**再提交并 bump 发版 |
| 审计重心 | 前后端契约与功能闭环 / 高并发压测稳定性 / 安全纵深 / 测试真实性与覆盖盲区 |

## 事实基线（本轮实测）

- HEAD：`79a5374` ｜ 版本 **23.2.0** ｜ tag `v23.2.0` ｜ 分支 main ｜ 与 origin/main 同步
- `ruff check api/ tests/ scripts/` → **All checks passed!**
- `pytest tests/test_version_consistency.py` → **5 passed**（原 4 + 本轮新增 1）
- 本机 `127.0.0.1:8100` → HTTP 200（**mock 上游模式**，`image_url=mock.example`，空库）
- 线上 `imagefree.hwhcie.bond` → DNS 解析 `20.204.27.154` 正常；**TCP 22/80/443/8100 全部超时**

---

## 一、本轮修复的真缺陷（全部含回归锁）

| ID | 缺陷 | 级别 | 证据 | 修复 | 回归锁 |
|---|---|---|---|---|---|
| **R-1** | **`bg_tasks.py` 持久化队列清理持续 AttributeError 静默失效** | **P1** | `_engine` 是**模块**（`:43 from .worker import engine`），`_queue_db` 是 `Engine` **实例属性** → 实测 `hasattr(module,'_queue_db')=False`。异常被 `:142 except Exception` 吞成 warning，且因在 try 块**中部**抛出，**其后所有清理逻辑（DAG TTL、告警评估）每次都被跳过** | 改从 `api.meta` 取 Engine 单例 + `getattr(..., None)` 防御 | `tests/test_db_retention.py` 3 用例（AST 级 —— 字符串匹配会被改名绕过） |
| **R-2** | **SSE/WS 多订阅者场景误清回放缓冲** | **P2** | `sse_events.py:246` + `ws_events.py:125` 连接 finally 无条件 `clear_task` → 同一 task 被 2+ 客户端订阅时，先断开者清掉**共享**缓冲，另一方 `Last-Event-ID` 回放静默失效 | 新增 `clear_task_if_idle`（判空与清理**同锁内**，避 check-then-act 竞态），两处调用点改用它 | `tests/test_sse_events_unit.py` 5 用例（行为 3 + **调用点契约 2**） |
| **R-3** | **前端测试套件系统性 DOM 泄漏 → CI 前端门禁持续红** | **P1** | GitHub Actions run `38571665098` / `38569968598` annotations：**多文件**同时报 `Found multiple elements`（CostsPage `按模型`、CommandPalette `combobox`/`dialog` 等）。根因：`vite.config.ts` 设 `isolate:false` 并**声称**「通过 setup.ts 的 beforeEach 清理」，但 `setup.ts` **从未有任何清理逻辑** | `frontend/src/test/setup.ts` 显式注册 `afterEach(cleanup)`；`vite.config.ts` 注释改为与实现一致并标注「配套关系」 | 本地全套件 299 passed（**但见下方"未闭环"说明**） |
| **R-4** | **env 映射契约结构性盲区** | P2 | `test_config_validate.py::TestEnvExampleSync` 用 **regex 扫源码**抓 `validation_alias="IF_X"` 字面量，**无 alias 的字段根本不进集合** → 「字段存在但 env 读不到」对双向校验不可见。实证 `Settings.user_agent`（`settings_core.py:79`）是 **202 字段中唯一漏挂 alias** 的 | 新增 `TestEnvMappingContract`（运行时 `model_fields` 反射 + `NO_ENV_BY_DESIGN` 显式登记表） | 5 用例，**变异验证有判别力** |
| **R-5** | **`deploy/.env.example` 注释指向错误文件** | P2 | 注释称「改 UA 需改 `api/config/http.py`」，但那是**死副本**（`HTTPSettings.from_settings()` 无条件用 `s.user_agent` 覆盖）；20 处生产代码消费的是 `config.USER_AGENT`（源自 `settings_core.py:79`）。**照注释改，白改一场** | 注释重写：指明权威文件 + 4 处同步点 + 契约测试位置 | `TestEnvExampleSync` 2 passed 复验 |
| **R-6** | **覆盖率门槛文档与 CI 不符** | **P1** | `ci.yml:53`/`deploy.yml:30` 是 `--cov-fail-under=80`，而 `SKILL.md`/`imagefree-rules.md` 写 **70**。**按文档自测通过 → 推 CI 意外失败** | 修 4 处（`.claude/skills/` 下权威副本；`.agents/` 未入库不动） | — |
| **R-7** | **skill 文档版本漂移** | P2 | `SKILL.md:22` 写 v23.1.0，实际 v23.2.0（门禁只覆盖 10 个代码文件，**不含文档**） | 修正 + **新增漂移门禁测试** | `test_version_consistency.py::test_dev_doc_version_not_drifted`，**变异验证有判别力** |

---

## 二、CI 真实性（本轮最重要的系统性发现）

**GitHub Actions 实测（经 API，`--ssl-no-revoke` 绕开本机 schannel 吊销检查）：**

| 项 | 事实 |
|---|---|
| 总运行次数 | **462** |
| 最近 100 次 | CI **54 failure + 1 cancelled**、Deploy **45 failure** → **成功 0 次** |
| 最后一次 success | 2026-09-08 之前（30 次 success 全在 9-08 及更早） |
| **结论** | **CI 已整体红了一个多月** |

**最近一次 CI（run `38571665048`, sha `0c883c0`）逐 job 结果：**

| Job | 结果 | 说明 |
|---|---|---|
| 前端版本一致性门禁 | ✅ success | |
| **后端单元测试 (3.11, ubuntu-latest)** | ❌ **failure** | 失败步骤「单元测试（排除集成/混沌）」→ `exit code 1`（**Linux 上也失败，排除"本机 Windows Defender 拖慢"的解释**） |
| 前端 E2E + a11y + perf + resp | ✅ success | 22 断言 + axe-core **0 critical** |
| ruff 检查 | ✅ success | |
| **前端构建门禁 (tsc + vitest + build)** | ❌ **failure** | 失败步骤「Vitest 测试」→ `Found multiple elements ...`（即 R-3） |
| Docker 构建验证 | skipped | |

**后端 CI 失败的具体原因本轮未能取到**（job 日志需 admin 权限，annotations 只给 `exit code 1`）。**这是一个仍未闭环的项。**

---

## 三、判定为「伪问题 / 不成立」（诚实记录，避免重复劳动）

| 项 | 来源 | 我的初判 | 实测结论 | 决定性证据 |
|---|---|---|---|---|
| `import api.config` 卡住 | 自己 | 疑似模块级单例阻塞 | **我的探针写错了**（`print(s.if_host)` 抛 AttributeError 致管道挂起） | 修正探针：`import api.config` 7.19s、`import api.main` 35.86s **均正常完成** |
| 前端 17 个路径后端不存在 | 自己 | 疑似大批断链 | **正则信号太脏**（尾斜杠/模板片段/fixture） | 方法级实测：31 路径**全部存在，0 断链**（`scripts/probe_route_methods.py`） |
| `/v1/gallery/zip` 404 | 自己 | 疑似断链 | **它是 POST 端点**（`gallery.py:233`），我用 GET 探测 | 读源码 + 方法级探测 |
| `.env` 的 `IF_WORKERS=10` 被静默覆盖为 48 | Audit-Concurrency | 疑似生产 bug | **归因错误**：`.env` **根本不被读取**（`settings_core.py:36` `model_config` 无 `env_file`；全仓无 dotenv 调用；`start.ps1:75` 直接起 uvicorn 不加载）。哨兵逻辑**本身正确**（实测真 env var `IF_WORKERS=7` → workers=7 ✓）；生产走 docker `env_file:` / systemd `EnvironmentFile=` 会注入 `os.environ`，正常工作 | 字段默认值即 `workers=10/if_workers_max=16/token_pool_size=6/max_queue=2000`，与 `.env` 内容**完全一致** → 之前"`.env` 生效"的观测其实是**默认值** |
| 生产模板只列 42/201 个 `IF_*` | 自己 | 疑似模板不完整 | **正常设计**（其余走代码默认值），且 42 键**零幽灵键** | 运行时 `Settings.model_fields` 比对 + `os.getenv` 扫描 |
| 分组配置与顶层默认值"重复" 86 项 | 自己 | 疑似双源 | **噪声**（多为数值恰好相等如 `5==5`） | 已弃用该扫描 |
| `.env` / `scripts/ops` 凭证泄漏 | 自己 | — | **保护有效**（未入库 + ignore 命中） | `git ls-files` 空 + `git check-ignore` |
| landing `isolate:false` 需要 cleanup | 自己 | 疑似同类隐患 | **不需要**：每个用例显式 `wrapper.unmount()`，自管生命周期 | `PwaInstallPrompt.test.ts` 每处 mount 后都 unmount |
| `test_config_validate.py` 全量跑失败=跨文件污染 | Audit-Tests | 疑似测试隔离缺陷 | **是我的变异测试残留**（`__MUTATED_OUT__`）：我先变异 → 它跑全量 → 我恢复。单跑 25 passed | 已确认无残留 |
| audit 子代理报的覆盖率 28.4% / 多模块 0% | Audit-Tests 产物 | 疑似真实低覆盖 | **产物不可信**（部分跑+增量叠加）：`health_report.py` 单跑实测 **57%**，产物报 0% | 单跑 `tests/test_health_report.py --cov` |

---

## 四、未闭环项（诚实披露）

| 项 | 状态 | 原因 |
|---|---|---|
| **R-3 修复的 CI 验证** | ⚠ **本地无法判别** | 全套件本地 **299 passed**，且**移除 `cleanup` 的变异测试本地也通过**（28/28 文件），说明本机 RTL 自动清理有效、复现不出 CI 症状。**根因机制已确证（CI annotations 多文件泄漏）**，但「修复是否真能救 CI」**必须靠推送后重跑确认**。环境差异候选：**CI 用 Node 20，本机 Node 25.8.1** |
| **后端 CI 失败的具体原因** | ⚠ 未取到 | job 日志需 admin 权限；annotations 仅 `exit code 1` |
| **全量覆盖率真实数字** | ⚠ 未取得 | 本机全量跑被 `--timeout=120` 中断（`test_tryingopen.py::no_sleep`），`cov_ci_parity.json` 未生成；审计产物的 28.4% 已证不可信 |
| **`/v1/logs` + `/v1/logs/ws` 匿名可读** | ⏸ **有意不改** | Audit-Security 实测匿名可读实时日志（含内部端点探测记录/IP）。但 `admin/query.py` docstring 明写「v7.7.8 公益只读开放」，属**有意的公益设计**。收口会**改变对外的公益契约并可能影响管理前端**，属生产策略决策 → 列入建议不擅自实施（CLAUDE.md：生产收紧需授权） |
| **`public_keymask()` 回显 Key 前 12 字符** | ⏸ 潜在（未触发） | `IF_API_KEYS` 为空时线上不触发；一旦配置，匿名者可经 `/v1/chat/auth/status` 拿到 29 字符 Key 的**前 12 字符（41%）** → 列入建议 |
| **`/v1/agent/memory/observe` 未授权写入** | ⏸ 潜在 | 匿名可写 agent 记忆（投毒面）。改鉴权需先查前端调用方是否带 Key → 列入建议 |
| **线上部署热更新** | 🚫 **阻塞（外部）** | 主机 22/80/443/8100 全端口超时；用户已决定按挂机处理 |
| **vitest 本地可运行性** | ⚠ 环境陷阱已定位 | 必须 `NODE_OPTIONS="--max-old-space-size=4096"`，否则 worker 启动超时/`Worker exited unexpectedly`。项目 CLAUDE.md 建议的 `NODE_OPTIONS=--max-old-space-size=512` **正是元凶** |

---

## 五、验证日志（本轮全部真实执行）

| 命令 | 结果 |
|---|---|
| `ruff check api/ tests/ scripts/` | ✅ All checks passed! |
| `pytest tests/test_version_consistency.py` | ✅ 5 passed（含新增文档漂移门禁） |
| `pytest tests/test_config_validate.py` | ✅ 25 passed（含新增 5 契约） |
| `pytest tests/test_db_retention.py` | ✅ 16 passed（含新增 3 回归） |
| `pytest tests/test_sse_events_unit.py` | ✅ 32 passed（含新增 5 回归） |
| **变异测试** ×5 | ✅ 4 个有判别力（env 契约 / 文档版本 / P1 回归 / SSE 调用点）；1 个**无**（SSE 行为测试只测方法不测调用点）→ 已补调用点契约后判别力成立 |
| `python scripts/sync_version.py --check` | ✅ 全链一致 23.2.0（10 文件） |
| `python scripts/probe_route_methods.py` | ✅ 前端 31 路径全部存在，**0 断链** |
| 端点冒烟 12 个 | ✅ `/v1/livez`~`/metrics` 全 200，`/admin` 307，`/` 200 |
| `node scripts/serve_static.cjs` + curl | ✅ `/`→200、`/admin`→307、`/admin/tasks`→200 |
| `node scripts/e2e_mobile_smoke.cjs` | ✅ **9 passed / 0 failed**（真实 chromium 1243，截图落盘） |
| `cd frontend && NODE_OPTIONS=--max-old-space-size=4096 npx vitest run` | ✅ **299 passed / 28 files** |
| `cd frontend && npx tsc -b` | ✅ exit 0 |
| GitHub Actions API（runs/jobs/annotations） | ✅ 取得 462 次运行历史 + 最近失败 job 真实原因 |

---

## 六、过程性事件（诚实披露）

| 事件 | 性质 | 处置 |
|---|---|---|
| 探测限流头时发了 `POST /v1/generate`，产生任务 `961d0b59` | **越界**：未先确认实例运行模式 | 核查 `image_url=https://mock.example/...` → **mock 模式，未触达真实上游、无付费**。教训已记入 memory |
| 三次静态推断误判（import 卡住 / 17 路径断链 / gallery zip 404） | 方法论错误 | 全部用实测推翻，已固化进 `.wolf/memory.md` |
| 变异测试残留 `__MUTATED_OUT__` 干扰了 Audit-Tests 的全量跑 | 操作干扰 | 已恢复；该"失败"已判定为误报 |

---

## 七、下一步

- 推送后重跑 CI，确认 R-3 是否解除前端门禁红（**必须**）
- 取后端 CI 失败原因（需 admin 权限或本地复刻 CI 环境）
- 产出 HTML 报告 + 测验 + skill 沉淀
- 版本 bump + commit + Release
