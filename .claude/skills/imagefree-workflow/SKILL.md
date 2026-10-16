---
name: imagefree-workflow
description: 听风AI imagefree_api 项目开发工作流指南。涉及本仓库任何开发任务（改后端 api/、加提供商 providers/、改前端 frontend/src/、写测试 tests/、部署 deploy/）时先加载本技能，获取项目结构、开发/测试/部署流程与关键文件索引。Windows 环境，Python 3.11 + FastAPI + React。
---

# imagefree-workflow — 听风AI 项目开发指南

## 1. 项目概述

**听风AI（imagefree_api）是一个生产级 AI 图像生成 API 网关**，将多家上游 AI 图像服务（imagefree.net、aifreeforever.com、tryingopen.com 对话）聚合为统一的 OpenAI 风格 `/v1/*` 接口。nanobanana / fal.ai 已下线。

核心能力：

- **多提供商路由** — 按 `model` 参数自动路由到对应上游，自动降级/熔断（MAB-EWMA）
- **号池自动化** — 自动注册 + 每日签到，管理 1000+ 账号（生产 `IF_ACCOUNT_AUTO=0` 停用签到）
- **代理池轮换** — 住宅代理 + 免费代理双源，每 IP 递增冷却 + 24h 每日限额重置
- **高并发架构** — 有界优先级队列 + Worker 池（4-16 自适应）+ Turnstile token 预取，扛 270+ RPS
- **AI 工具门户 + 管理后台分离** — `/` 是 Vue3 门户（对话/生图/图生图/视频/PPT/Agent + 画廊）；`/admin` 是 React 站长后台（v20.3.0 门户重构）
- **智能体 DAG 编排 / MCP / 桌面版 / PWA** — 详见 README v21 小节

技术栈：Python 3.11+ / FastAPI / uvicorn / SQLite(aiosqlite) / httpx / pydantic-v2 / React 19 + Vite 6 + TS / Vue3 landing。
当前版本 v23.3.2（改动前先核对 pyproject.toml 实际版本，**版本全链一致性由 `tests/test_version_consistency.py` + `scripts/sync_version.py --check` 门禁**；注意门禁只覆盖 10 个代码/配置文件，**不含本 SKILL.md**，改版本时需手工同步此处——现已由 `test_dev_doc_version_not_drifted` 兜住）。

> **v7.7.4+ 鉴权契约**（必读）：
> - 生图 `/v1/generate*`、聊天 `/v1/chat/*`、`/v1/messages`：**公益开放不限 Key**（仅 per-IP 限速防刷）。
> - 管理面写操作（封禁/解封、DLQ 清空/重试、日志 WS、priority=0 队列、**画廊软删**）：**保留管理 Key 鉴权**（`IF_ADMIN_KEYS`，`check_admin_key`；画廊删 scope="gallery-delete"）。
> - 生产真实 IP：**线上 systemd 原生部署（20.204.27.154，无 Docker）**，nginx 443 → :8100；`IF_TRUSTED_PROXIES=127.0.0.1,::1`（同机反代够用；若改云 LB 私网反代需显式加入）。
> - 版本 bump：`python scripts/sync_version.py --set X.Y.Z`（10 文件 + e2e_v12 契约；v23 起含 landing/index.html softwareVersion）→ frontend/landing `npm run build`（dist 重建）→ `pytest tests/test_version_consistency.py -q` 全绿。
> - v22/v23 工具集：`scripts/uptime_probe.py`（拨测模拟）、`scripts/restore_drill.py --from-litestream`（恢复演练）、`scripts/e2e_mobile_smoke.cjs`（移动端冒烟，**须配 `scripts/serve_static.cjs`**，见 §4.2）、`scripts/probe_federation.py`（solver 双节点联邦实测）、`scripts/probe_stress.py`（极限压测，v23.1）、`landing` vitest 基建（`cd landing && npm test`）。
> - 2026-10-14 新增工具：`scripts/serve_static.cjs`（静态预览服务，复刻 landing/admin 挂载语义）、`scripts/run_tests_batched.py`（分批测试，规避宿主 kill + 断点续跑）。
> - v23 部署原生化：观察栈/litestream 一律走 `deploy/systemd/`（prometheus/node_exporter/grafana/litestream 独立 unit + install_observability.sh），**不再用 docker compose**。
> - v23 安全基线：`/v1/logs/ws` 广播已脱敏（复用 log_buffer._redact）；`redis://` 与 webhook URL 日志只记 host:path；chat/DAG 限流走受信代理解析真实 IP；cancel 已补 per-IP 限流。
> - health-report 采集降级：email_pool 源 import 走 run_in_executor+wait_for 限时（IF_SSE_HEARTBEAT_INTERVAL 心跳可配、IF_SSE_MAX_CONNECTIONS 连接上限）。

线上演示：https://imagefree.hwhcie.bond （Azure，公益开放）

> **⚠ 交付口径：线上服务器访问途径**用户目前**未提供**（2026-10-16 明确：「服务器目前还没给你，
> 没办法线上更新」）。因此：
> - **一切交付以「本地真实 E2E」为准**，不要因「线上没验」而阻塞或降级其他工作。
> - **不要重复探测** `imagefree.hwhcie.bond` / `20.204.27.154` —— 它 TCP 22/80/443/8100
>   全超时（DNS 能解析），这是**未提供访问途径**，**不是缺陷、不列为阻塞待办**。
> - 「线上部署 / 生产热更新 / 线上 E2E」类要求 → 直接改做等价本地 E2E：
>   `node scripts/serve_static.cjs`（复刻 landing→`/` 与 frontend/dist→`/admin` 挂载语义）
>   + `node scripts/e2e_mobile_smoke.cjs`（**真实 chromium**）
>   + 本地 `uvicorn api.main:app --port 8100` + curl 端到端。
> - 同理不追：`deploy/systemd/` 原生部署落地、litestream R2、观察栈起服、cf_solver 第二节点
>   （均需线上/外部凭证）。
> - **解除条件**：用户明确给出服务器访问途径（SSH 端口/凭证/跳板机）后，本条作废。

> **⚠ CI 现状（2026-10-15 实测，动手前必读）**：GitHub Actions **已连续失败约一个月**——
> 最近 100 次运行中 **CI 54 failure + 1 cancelled、Deploy 45 failure，成功 0 次**
>（历史上 30 次 success 全在 2026-09-08 及更早）。**不要在"CI 是绿的"这个假设上做判断。**
>
> 最近一次 CI（sha `0c883c0`）逐 job：
> - ✅ 版本一致性门禁 / ruff / 前端 E2E+a11y+perf+resp
> - ❌ **后端单元测试**（ubuntu-latest，`exit code 1`；**Linux 上也失败**，故不是本机 Windows 问题）
> - ❌ **前端构建门禁 →「Vitest 测试」**（DOM 泄漏，见 §4.1；2026-10-15 已修，**待推送复验**）
>
> 取 CI 真实失败原因的方法（`gh` CLI 缺失时）：
> `curl --noproxy '*' --ssl-no-revoke https://api.github.com/repos/lza6/Aggregate-to-2api/actions/runs/<id>/jobs`
> 再用 `check-runs/<job_id>/annotations` 拿失败消息。
> **`--ssl-no-revoke` 必需**：本机 schannel 吊销检查离线，不加会报 `CRYPT_E_REVOCATION_OFFLINE`。
> job 日志下载需 admin 权限（会 403）。

## 2. 代码结构说明

```
imagefree-2ai/
├── api/                        # 后端源码（核心）
│   ├── main.py                 # 应用组装入口（<300 行：仅挂载路由/中间件/前端/生命周期）
│   ├── routes/                 # 路由层（端点定义在此，不在 main.py）
│   │   ├── health / tasks / generate / chat / admin/ / gallery / security
│   │   ├── agent_dag*（DAG 编排）/ agent_human / agent_skills_admin / mcp_admin
│   │   └── ecosystem / ppt / video
│   ├── config/                 # 分组配置包（pydantic-settings，IF_* 前缀；get_settings()/reset_settings() 工厂）
│   ├── worker/                 # 高并发引擎：优先级队列 + worker 池 + token 预取 + 健康探测
│   ├── db/                     # SQLite 持久化（aiosqlite）+ 0.2s 批量写合并 + 连接池 + ip_blocklist_store
│   ├── errors.py               # 分层错误码（CATEGORY.NNN）+ AppError
│   ├── providers/              # 多提供商适配器（**nanobanana/falai 已下线**）
│   │   ├── base.py             # Provider 抽象基类 + ModelSpec + GenerationResult
│   │   ├── registry.py         # 提供商注册、路由、健康检查
│   │   ├── imagefree.py        # imagefree.net（Turnstile token 认证）
│   │   ├── aifreeforever.py    # 每 IP 每日限额 → 每请求轮换代理
│   │   ├── tryingopen/         # 对话 / 智能体上游（包）
│   │   └── video_mock.py / video_provider.py
│   ├── turnstile_client.py     # cf_solver 客户端（:8001）
│   ├── solver_guard.py         # 熔断器 + 求解质量统计
│   ├── proxy_pool.py           # 住宅代理池 + 冷却策略
│   ├── free_proxy_fetcher.py   # 免费代理池抓取
│   ├── account_pool/           # 号池管理（**包**：_base/_constants/borrow/engine/fsm/pool/store 等）
│   ├── registerer/             # 自动注册（**包**：cf_solve/email_verify/flow/types）
│   ├── email_pool.py           # 邮箱池（单文件；多源适配器在同级 email_sources/）
│   ├── cache.py / retry_policy.py / base64_store.py / semaphore_manager.py
│   ├── audit.py / alerting.py / telemetry.py / metrics_ext.py / log_ws.py / log_buffer.py
│   ├── health.py / health_report.py / context.py / cache_warmup.py
│   ├── sse_events.py / ws_events.py   # 每任务 SSE 事件流 / WS 广播
│   ├── dispatch.py / dispatch_edit.py # 路由调度 / 图生图双层互斥
│   ├── adaptive_router.py      # MAB-EWMA 路由引擎（+ 熔断）
│   ├── lifespan.py             # 9 阶段优雅关闭
│   └── static/                 # 后端直出的静态页（honor.html 捐赠页 / slow.html / terms.html）
├── frontend/src/               # React 管理面板（Vite + TS）—— 挂载于 /admin
│   ├── App.tsx / main.tsx
│   ├── api/                    # API 封装**包**（core/misc/tasks/chat/agent/providers/security/index）
│   ├── pages/                  # 15 页：Dashboard / Tasks / Generate / ChatPlayground /
│   │                           #        Accounts / Providers / Health / Logs / Security /
│   │                           #        Slow / DLQ / Costs / Ecosystem / Agent / ApiGuide
│   ├── components/             # Layout / StatCard / Gallery / BarChart / CommandPalette 等
│   └── test/                   # vitest 单测（28 文件 / 301 用例）
├── landing/                    # Vue3 公开落地页（Vite）—— 挂载于 /
│   ├── src/                    # App.vue + components/ + composables/ + lib/ + styles/ + test/
│   └── dist/                   # 构建产物（.gitignore；**缺它则 `/` 返回 404**，见 §4）
├── tests/                      # 182 顶层 + 15 integration + 2 chaos + 3 performance
│   ├── test_*.py               # 单元测试（顶层）
│   ├── integration/            # 集成测试（全流程/熔断/DLQ/编辑流/限流/超时）
│   ├── chaos/                  # 故障注入
│   └── performance/            # 压测（benchmark / stress）
├── scripts/                    # 41 个运维/验证脚本
│   ├── e2e_validate.py / e2e_mobile_smoke.cjs / serve_static.cjs
│   ├── probe_stress.py / probe_route_methods.py / probe_federation.py
│   ├── run_tests_batched.py / sync_version.py / create_release.py
│   └── backup_db.py / restore_db.py / restore_drill.py / loadtest.py
├── deploy/                     # 生产部署资产
│   ├── docker-compose.yml / Dockerfile.api / Dockerfile.cfsolver
│   ├── cf_solver/              # Turnstile 求解服务（入口 boterdrop_wrapper.py，端口 8001）
│   ├── systemd/                # 线上原生部署（**线上无 Docker**）
│   ├── grafana/ / prometheus.yml / litestream.yml
│   └── .env.example / .env.production.example
├── data/                       # 运行时数据（*.db、imgs/、logs/）
├── docs/                       # SOP / PROVIDER_INTEGRATION_GUIDE / verification-log（验证台账）
│                               #   / releases/（含 archive/）/ research/ / verification-artifacts/
├── start.ps1 / start.bat       # Windows 一键启动
└── pyproject.toml              # pytest/ruff/mypy 配置
```

> **注**：上树已按 2026-10-16 的真实文件系统逐条核对过（原先存在 8 处失实路径：
> `api/providers/nanobanana.py`、`api/account_pool.py`、`api/registerer.py`、
> `api/docs.html`、`frontend/src/api.ts`、`scripts/inject_accounts.py`、
> `deploy/api/`、根 `cf_solver/` —— 均已在树上改正）。
> **改动目录结构时请同步更新本节**，否则下个会话会照错路径找文件。

### 代码流关键路径

1. **请求入口**：`POST /v1/generate` → `main.py:generate_sync` → 校验模型/比例 → SQLite 入库 → 入优先级队列 → 立即返回 task_id
2. **后台执行**：`api/worker/engine.py:Engine`（worker 池 4-16 自适应）→ 取队列 → 从 `TokenPoolManager` 取 token → 路由 provider → 上游调用 → `db.mark_finished`
3. **异步任务**：`/v1/generate/async` 立即返回 task_id，客户端轮询 `/v1/tasks/{id}`

## 3. 开发工作流

```
0. 读记忆与台账 → 验证: 见下方「第 0 步」——决定这次要重跑什么、能跳过什么
1. 理解现状     → 验证: 用 graft/codegraph 查符号、调用链，读相关测试
2. 规划         → 验证: 明确改动范围，列出影响文件
3. 实现         → 验证: 改动最小化（KISS / 不重构没坏的东西）
4. 测试         → 验证: pytest 全绿 + 相关测试通过
5. 审查         → 验证: 自审 checklist（错误处理/命名/不可变性）
6. 提交         → 验证: 约定式提交（feat/fix/refactor/docs/test/chore/perf/ci）
```

### 第 0 步（**强制，不可跳过**）：读记忆 → 判断时效性 → 再动代码

**这是本仓库效率的关键**：大量检查项已被验证过，盲目重跑既慢又挤占真正该找 bug 的精力。

**必读顺序：**

| # | 文件 | 读它来回答什么 |
|---|---|---|
| 1 | `docs/verification-log.md` | **「防重复测验协议」台账** —— 查你要改的模块是否近期已验、结论是什么。**尾部有本批记录** |
| 2 | `.wolf/memory.md` | 逐条踩坑与教训（含「本项目静态扫描噪声极大，只有实测可信」这类方法论） |
| 3 | `.wolf/cerebrum.md` | `## Do-Not-Repeat`（禁止重复的过去错误）+ `## Key Learnings` + `## User Preferences` |
| 4 | 本 SKILL.md 的 §4 测试指南 / §5 常见陷阱 | 环境级陷阱（vitest 堆内存、CI 现状等） |

**读完后的判断规则**（这是重点，不是走过场）：

- **台账里已验 + 代码未改** → **跳过重复验证**，把精力放到未验/已改区域
- **台账里已验但代码改过** → 旧记录**视为失效**，必须重跑该模块
- **记忆/台账里的描述与当前代码冲突** → **以代码为准**，并**当场更新那条记录**
  （本批抓到的真缺陷里有 3 个正是「文档/注释描述了一个不存在的实现」：
  `setup.ts` 声称的清理、`.env.example` 指错的修改文件、覆盖率门槛 70 vs 80）
- **记忆里提到某个文件/函数/开关** → **先确认它仍存在**再照做，不要照着过时记忆改代码

**改完代码后必须回写**（否则下次又会重复）：
1. `docs/verification-log.md` 追加一行（日期 + 范围 + 结果 + 证据）
2. `.wolf/memory.md` 追加一行（若产生了值得复用的新事实/踩坑）
3. 若改了架构/约定 → 同步 `CLAUDE.md` / 本 SKILL.md

### 规则

- **先思考再编码**：不假设，不隐藏困惑，展示权衡。
- **简洁优先**：最少代码解决问题，不做推测性工作。
- **精准修改**：只改必须改的，不重构没坏的东西；发现无关死代码只提一下，不要删。
- **组织方式**：按领域/功能组织（providers/、tests/integration/），多小文件优于大文件（文件 <800 行）。
- **参考文档**：改动前查 `docs/`、`graft/INDEX.md`、`.wolf/cerebrum.md`（含 Do-Not-Repeat 与 Key Learnings）。
- **结论必须有证据**：本仓库**静态扫描噪声极大**（本批三次静态推断全错）。
  「读代码推测」= 静态确认；「真跑命令看到输出」= 已验证。**别把前者说成后者**。

### 常见改动模式

- **新增提供商**：新建 `api/providers/<name>.py` 继承 `Provider` 基类 → 在 `api/providers/registry.py` 的 `bootstrap()` 注册 + 加模型前缀映射 → 加模型规格 → 写 `tests/test_providers*.py` 用例。
  （**旧的「同步到 `deploy/api/`」已废弃** —— 该目录不存在了。docker 构建直接 COPY `api/`。）
- **新增端点**：端点**定义在 `api/routes/<domain>.py`**（不是 `api/main.py`！）——
  该模块内 `router = APIRouter()` + `@router.get/post(...)` → 若是**新模块**，在
  `api/routes/__init__.py` 加一行 `api_router.include_router(<mod>.router)` →
  请求/响应模型放 `api/models.py` → 校验走 `errors.py` 的 `AppError`/`error_response` → 补测试。
  （`api/main.py` 只做组装：挂路由/中间件/前端/生命周期，**保持 <300 行**。）
- **新增配置项**：字段加在 **`api/config/settings_core.py` 的 `Settings` 类**（`api/config/__init__.py`
  只是垫片，**别往那里加**），用 `Field(default, validation_alias="IF_XXX")` → `deploy/.env.example`
  同步（`test_config_validate::TestEnvExampleSync` 会拦截缺失！）→ `Settings.validate()` 补校验。
  **注意**：`test_config_validate::TestEnvMappingContract` 会强制每个字段二选一 ——
  要么挂 `IF_*` alias，要么登记进 `NO_ENV_BY_DESIGN` 并写明为何有意不映射；
  **忘记挂 alias 会 fail**（历史真缺陷：`user_agent` 曾是 202 字段中唯一漏挂的）。
  分组子配置（`api/config/<group>.py`）需同步 `from_settings()` 工厂。
- **前端改动**：改 `frontend/src/` → `npm run build` 产出 `frontend/dist/` → 让后端 `docs.html` 载入（静态资源走 `api/static/`）。

## 4. 测试指南

```bash
# 全量单元测试（⚠ 见下方「分批」说明：180 文件单进程跑会被宿主 kill）
python -m pytest tests/ -q -m "not integration and not chaos and not slow"

# 分批跑（推荐，规避宿主 kill + 断点续跑）
./.venv/Scripts/python.exe scripts/run_tests_batched.py --batch-size 12

# 覆盖率（CI 门槛 80%，与 ci.yml / deploy.yml 一致）
python -m pytest tests/ -q --cov=api --cov-report=term --cov-fail-under=80

# 单文件
python -m pytest tests/test_worker_auto_scale.py -q
```

> **解释器**：Windows 上 `python`/`python3` **不在 PATH**，必须用 `./.venv/Scripts/python.exe`。
> **`rg` 不可用** —— 用 Grep 工具或 `grep`。
> **⚠ 本仓库 pytest 不打印 `N passed in Xs` 摘要行，`--junitxml` 也不会生成文件。**
> 输出只有 `.....  [100%]` 进度点。根因**不是** `-q`（标准 pytest `-q` 会打摘要）：
> 是本仓 `tests/conftest.py` 的 `pytest_sessionfinish` 调 `os._exit(exitstatus)`
> （Windows 本地 teardown 永不返回的兜底，CI 不触发），它在 terminal reporter **与
> junitxml 插件**写盘之前就结束进程。<br>
> **后果**：**测试失败时看不到失败用例名与 traceback** —— 只能看到 `F` 符号。
> 任何靠解析摘要文本取计数的脚本都会恒得 0。<br>
> **可行做法**：
> 1. **以 exit code 为准判成败**（`os._exit` 传的是真实状态码，可靠）；
> 2. **计数/定位失败用进度符号**：`-q` 的进度行实时输出，按 `.`/`F`/`E`/`s` 计数
>    （`scripts/run_tests_batched.py` 的 `_count_from_progress()` 即此实现）；
> 3. **只想看某一个文件的失败详情**：`PYTEST_NO_FORCE_EXIT=1 pytest <单个文件> --tb=short -rf`
>    —— 注意该环境变量会让 teardown 挂死，**必须配外部 `timeout`**，且只适合单文件/小集。
> 4. 想定位「哪个文件坏了」：用 `scripts/run_tests_batched.py --batch-size 1 --files a,b,c` 逐文件归因。

- 测试目录约定：单元测试放 `tests/test_*.py` 顶层；集成走 `tests/integration/`；故障注入 `tests/chaos/`；压测 `tests/performance/`（pytest-benchmark marker）。
- **宿主 kill 约束**：单次 pytest 进程跑全量（180 文件）存活过久会被宿主终止 → 用 `scripts/run_tests_batched.py` 分批（结果增量落盘 `data/batched_test_results.json`，`--resume` 续跑）。
- Mock E2E（零真实求解消耗）：`python scripts/e2e_validate.py --mode mock`
- 真实 E2E（需 cf_solver :8001 + 代理）：`python scripts/e2e_validate.py --mode real`
- **注意**：E2E 倾向于真实上游接口；本地开发善用 `--mode mock` 避免消耗上游额度。
- 新增功能必须有对应测试，TDD（先写测试 RED → 实现 GREEN → 重构 IMPROVE）。

### 4.1 前端测试（本轮踩坑修正）

```bash
# 管理面板（React/Vitest）—— 28 files / 299 tests
# ⚠ 必须提高 node 堆：默认/512MB 时 worker 起不来（见下方"堆内存陷阱"）
cd frontend && NODE_OPTIONS="--max-old-space-size=4096" npm test

# 门户（Vue/Vitest）—— 2 files / 13 tests
cd landing && npm test
```

> **⚠⚠ 头号陷阱：`NODE_OPTIONS=--max-old-space-size=512` 会让前端套件完全跑不起来**
> （2026-10-15 实证）。表现为 `[vitest-pool-runner]: Timeout waiting for worker to respond`
> 或 `Worker exited unexpectedly`，Duration 60s、`no tests`。
> 项目调优建议里的 **512 太小**；设成 `4096` 后 `frontend` 立刻 **28 files / 299 tests 全绿（139s）**。
> **排查顺序：先怀疑堆内存，再怀疑路径，最后才怀疑机器负载。**

> **⚠ vitest 在非 ASCII 路径下的坑（两个包都中招）**：本仓库位于 `Desktop/2api目录/...`。
> vitest 4 的**隔离 worker** 在含非 ASCII 的路径下启动会 60s 超时
> （`[vitest-pool-runner]: Timeout waiting for worker to respond`，
>  URL 中 `2api目录` → `2api%E7%9B%AE%E5%BD%95`）。
> - `frontend`：曾表现为 **28 个 worker 全挂、0 测试执行**（`npm test` 完全不可用）
> - `landing`：同样超时
>
> **已固化进配置**（无需再记参数）：
> - `frontend/vite.config.ts`：`isolate: false` + `pool: 'forks'` + `testTimeout/hookTimeout: 20000`
> - `landing/vitest.config.js`：`isolate: false` + `pool: 'threads'`
>
> **⚠ `isolate: false` 必须配「显式 cleanup」——两者是配套的，改一方必须同时检查另一方。**
> CI 实证（GitHub Actions run `38571665098` / `38569968598`）：多文件同时报
> `TestingLibraryElementError: Found multiple elements with role "button"/"dialog"/"combobox"` ——
> 根因是 `frontend/vite.config.ts` 注释**声称**"通过 `src/test/setup.ts` 的 beforeEach 清理"，
> 而该文件**从未有任何清理逻辑**。修法：`setup.ts` 显式 `afterEach(() => cleanup())`。
> `landing` **不需要**（每个用例显式 `wrapper.unmount()`，自管生命周期）。
>
> **注意**：关隔离后模块同进程加载，5s 默认超时不够（实测 setup 累计 177s、
> environment 811s），故一并放宽 `testTimeout`。
> `frontend` 用 `forks`（独立子进程各有独立堆）；
> **不要**写 `test.poolOptions`——vitest 4 已移除该字段（会打 DEPRECATED 警告并被忽略，
> 让人误以为配置已生效）。
>
> **⚠ 另有一层非配置因素：机器负载**。vitest 启动 worker 有 60s 内部超时，
> 当本机同时跑着大量其他 node/python 进程时会触发同样的
> `Timeout waiting for worker to respond` / `no tests` —— 此时**换 pool 无效**
> （threads 与 forks 都会失败），应先确认机器不饱和再重跑，不要误判成配置回归。
> 判据：用 `psutil` 按 CPU 排序列出 `python.exe`/`node.exe`，确认没有**遗留的长跑 pytest**
> （实测曾有一个 `pytest tests/ ... --junitxml=data/full_junit.xml` 跑了 ~10 小时、占满 1 核）。
> 注意区分：`D:\参考项目\...` 下的进程属**其他项目**，不要误杀。

### 4.2 移动端 / 视觉 E2E（本轮补齐真跑能力）

```bash
# 1) 先起静态预览服务（同时服务 landing + admin SPA，复刻 api/main.py 挂载语义）
node scripts/serve_static.cjs --port 4590

# 2) 真实 chromium 冒烟（375×667，覆盖 / 与 /admin 两条路径 + 深链回退）
node scripts/e2e_mobile_smoke.cjs
```

- 依赖：`frontend/node_modules/playwright-core` + `ms-playwright` chromium 缓存（路径自动探测，可用 `IF_CHROMIUM_EXE` / `IF_PLAYWRIGHT_CORE` 覆盖）。
- 产物：`docs/verification-artifacts/mobile-landing-375.png` / `mobile-admin-375.png`。
- **overflow 断言判据**（勿退回朴素计数）：仅当元素 `scrollWidth > clientWidth` **且** 无 `ellipsis`/`overflow-x: hidden|auto|scroll` **且** 其盒子实际越过视口右缘，才算缺陷。否则会把「省略号截断」和「`.tf-dot-pulse::after` 的 scale 脉冲动画」误报为溢出。


## 5. 部署指南

### 线上环境（腾讯云东京，公益开放）

```
imagefree.tingfengai.art ──> Caddy(Caddyfile) ──> api:8100 (Docker)
                                             └──> cfsolver:8001 (Docker，仅内网)
```

### 方式一：Docker Compose（生产推荐）

```bash
cd deploy
# 编辑 docker-compose.yml 按需配置（示例值已在文件中）
docker compose up -d --build
```

- `cfsolver` 服务不暴露公网端口，仅 compose 内网供 `api` 访问；`api` 通过 `depends_on: condition: service_healthy` 等待 solver 就绪。
- 数据卷 `./data:/app/data` 挂载 SQLite 与图片。
- 健康检查：`GET /v1/healthz` 返回 `status in (ok, degraded)` 视为健康。

### 方式二：本地/Windows 启动

```powershell
# PowerShell（推荐，含 .venv 自动检测）
.\start.ps1

# 或手动两步
python cf_solver/boterdrop_wrapper.py &   # cf_solver :8001
uvicorn api.main:app --host 0.0.0.0 --port 8100
```

### 部署前检查清单

- [ ] `pytest tests/ -q --cov=api --cov-fail-under=80` 通过
- [ ] `.env.example` 中新增的配置项已同步
- [ ] 后端改动已用 `python scripts/sync_deploy.py` 同步到 `deploy/api/`
- [ ] `docker compose build` 无报错（或至少 import 校验通过）
- [ ] 密钥/代理地址无硬编码（用 `IF_*` 环境变量）

## 6. 常见问题

| 问题 | 排查 |
|------|------|
| 生成任务一直 pending | 查 worker 是否运行；`GET /v1/healthz` 看 solver 质量；`GET /v1/tasks` 任务状态；查 `data/*.db` 或 `/v1/logs` |
| Turnstile 求解熔断（solver OPEN） | `GET /v1/healthz` 看 `solver` 段；连续失败达阈值后熔断自动恢复（`solver_guard.py`）；检查 cf_solver :8001 可达性 |
| 提供商倍率/限额（rate limited） | 查看熔断/降级是否触发；aifreeforever 需免费代理池（`IF_FREE_PROXY=1`）；minimaxh3/nanobanana 需号池 |
| 某 provider 突然不可用 | `GET /v1/providers` 看状态；registry 自动降级到可用 provider；确认上游面额/风控 |
| 重启后任务中断 | 持久化队列 → 重启后 `db.recover_stale_tasks` 续跑；死信入 `GET /v1/dead-letter-queue` |
| SQLite 锁/"database is locked" | 是否同时开了多进程写同一个 db；写走 `db.py` 批量写合并（0.2s 窗口）；`_create_conn` timeout 默认 5s |
| 前端改了不生效 | 重新 `npm run build`（dist 由后端托管）；确认静态路径指向 `frontend/dist` |
| Windows curl 走代理 https 报 SSL | `curl --ssl-no-revoke`；参考 memory 中 windows-curl-ssl-revoke |

## 7. 关键文件索引

| 关注点 | 文件 |
|--------|------|
| 全部 HTTP 端点 | `api/main.py` |
| 配置项（环境变量） | `api/config/__init__.py` + `deploy/.env.example` + `deploy/.env.production.example`（生产收紧） |
| 队列/worker/token 池 | `api/worker/engine.py` / `api/worker/token_pool.py` |
| SQLite/批量写/查询 | `api/db/core.py` |
| 错误码/异常 | `api/errors.py` |
| 提供商抽象与注册 | `api/providers/base.py`、`api/providers/registry.py` |
| 上游客户端（imagefree） | `api/imagefree_client.py`、`api/providers/imagefree.py` |
| Turnstile 求解与熔断 | `api/turnstile_client.py`、`api/solver_guard.py` |
| 代理池 | `api/proxy_pool.py`、`api/free_proxy_fetcher.py` |
| 号池/注册 | `api/account_pool.py`、`api/registerer.py`、`api/email_pool.py` |
| 缓存/文件分离 | `api/cache.py`、`api/base64_store.py` |
| 可观测性 | `api/telemetry.py`、`api/metrics_ext.py`、`api/alerting.py`、`api/audit.py`、`api/log_ws.py` |
| 前端仪表盘 | `frontend/src/App.tsx`、`frontend/src/pages/*`、`frontend/src/components/*` |
| 测试配置 | `pyproject.toml`（pytest asyncio_mode=auto） |
| 部署资产 | `deploy/docker-compose.yml` |
| 上线演示/文档 | `README.md`、`docs/`、`.wolf/memory.md` |
| 运行时数据 | `data/*.db`、`data/imgs/` |

### 快速定位建议

- **结构性问题**（"X 是怎么工作的"、"改 X 会影响谁"）：优先 graft / codegraph 工具（本仓库已索引），比 grep+read 少一个数量级 token，且包含调用链与 file:line。
- **字面问题**（找某个字符串、统计出现位置）：用 Grep。
- **具体符号源码**：`graft ask --source` / codegraph node / Read 单文件对应行段。

## 附：imagefree-rules.md + 接入 SOP

- 代码规范、命名约定、错误处理模式、测试要求：[imagefree-rules.md](./imagefree-rules.md)
- **新增上游图像/对话生成提供商**：[new-provider-sop.md](./new-provider-sop.md)（7 步，每步带验收点）
- **新增任意功能/端点/页面/脚本**：[new-feature-sop.md](./new-feature-sop.md)（6 步 + 强制先思考后编码 + 验收清单）

> 新功能开发前先读这两个 SOP，避免遗漏鉴权/数据层/后台任务/无障碍/文档同步等接缝点。

## Do-Not-Repeat（v3.1.0 已验证，勿再盲目优化）

1. **SQLite WAL + 多读连接必须 `isolation_level=None`（autocommit）**。默认延迟事务会让 SELECT 钉死旧快照，round-robin 读池表现为「刚写入的任务随机 pending」。已在 `api/db/core.py:_create_conn`。
2. **批量写 flush 与 worker 读必须同一把锁**。`_ensure_flushed` 即使 buffer 为空也要 `async with lock`，否则 swap 后未 commit 的窗口会被 worker 读穿。
3. **禁止 `DB.__init__` 里 `asyncio.run`**。会把 aiosqlite 线程焊死在临时 loop，pytest 全绿后卡 shutdown。连接只在首次 `_ensure_initialized` 创建。
4. **测试污染三源**：全局单例直接赋值、`from x import CONST` 值拷贝、`os.environ.setdefault`。一律 monkeypatch 使用方模块。conftest 不得无条件 `del sys.modules['api*']`。
5. **不要为公益单机站引入 Redis/Kafka/分片**，除非有实测容量证据。现有 WAL + 连接池 + 0.2s 批量写是当前正确规模。

新增运维端点：`GET /v1/diagnostics`、`GET /v1/slow`、`GET /v1/slow/view`、`GET /v1/honor`、`GET /v1/terms/{sub}`。

last_verified: 2026-08-23 / 仓库版本 v3.1.0

## 12. 新增提供商接入 SOP（v7.3）

按 `docs/PROVIDER_INTEGRATION_GUIDE.md` 全流程执行，速查版：

1. **实现**：`api/providers/` 新建 `<name>.py`，继承 `Provider`（base.py），必实现 `generate`（async，返回 GenerationResult）+ `credits`（积分制）或健康检查；模型目录用 `ModelSpec` 声明。
2. **注册**：`api/providers/registry.py` `bootstrap()` 加实例 + 模型前缀映射（`<name>/`）。
3. **配置**：`api/config/__init__.py` 加 `IF_<NAME>_*` 字段 + `deploy/.env.example` 同步。
4. **免密型**（如 imagefree）不需要号池；**积分型**（needs_account=True）：`api/account_pool.py` 加 registerer 分支 + `api/registerer.py` 注册逻辑 + 邮箱源选择。
5. **测试**：`tests/test_providers_contract.py` 加契约用例（mock 上游，禁真实调用）；`test_providers_branches.py` 加分支用例。
6. **前端**：`frontend/src/api/providers.ts` 无需改（读 /v1/providers 自动展示）；needs_account 排序自动生效。
7. **文档**：`docs/PROVIDER_INTEGRATION_GUIDE.md` 若有新契约模式则补充。

## 13. 验证记录优先读取协议（防重复测验，v7.3）

**任何验证/测试/审计任务开始前，先读 `docs/verification-log.md`**：

1. 目标模块若近期已验证且代码未改 → **跳过重复验证**，引用记录即可。
2. 改动了某模块 → 在 verification-log 追加一行（日期/范围/结果/失效条件），使旧记录失效。
3. 「已知勿重跑结论」节长期有效（如 threading.Lock 审计、硬编码评估）——除非相关代码被改。
4. 本协议配合全局 memory/（跨会话）使用；进行中的任务状态写在 `.wolf/memory.md`，不另建 workflow_status 文件。

## 14. 会话收尾协议（v7.3）

重要改动落地后：

1. **docs/verification-log.md** 追加验证记录（进行中的任务状态写在 `.wolf/memory.md`）。
2. **持久记忆**：用户偏好/项目约定/踩坑写入全局 memory/（人读不到没关系，AI 下次会话优先读）。
