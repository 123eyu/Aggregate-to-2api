# 新功能接入 SOP（v7.7 沉淀）

> 适用：往听风AI 网关新增任意功能（新端点/新页面/新配置/新脚本）。
> 前置阅读：`.claude/skills/imagefree-workflow/SKILL.md` + `new-provider-sop.md`。

## 工作流（强制先思考后编码）

0. **先读记忆与台账，判断时效性**（**强制，不可跳过**）：按序读
   `docs/verification-log.md`（防重复测验台账）→ `.wolf/memory.md` → `.wolf/cerebrum.md`
   （`Do-Not-Repeat` / `Key Learnings` / `User Preferences`）→ `SKILL.md` 的 §4/§5 陷阱章。
   判断规则：**已验 + 代码未改 → 跳过**；**已验但代码改过 → 旧记录失效，必须重跑**；
   **记忆与代码冲突 → 以代码为准并当场更新记录**；记忆提到的文件/开关 → **先确认仍存在**再照做。
   详细规则见 `SKILL.md` §3「第 0 步」。
1. **Spec-Kit 规范**（`.specify/specs/NNN-<feature>/`）：spec.md（FR/AC）→ plan.md（架构+依赖）→ tasks.md（节点+验收）。
2. **先查 graft 图谱**：`graft ask "<task>"` / `graft callers <sym>` 定位代码，再回退 grep/read。

## 新端点 6 步

### 1. 路由（api/routes/<domain>.py）
- `@router.get/post("/v1/<domain>/<action>")`，写操作加 `check_admin_key(request, scope="admin-<action>")`。
- 返回走 `error_response`/`JSONResponse`，错误码用 `ErrorCodes.<CATEGORY>.<NNN>`（见 api/errors.py）。
- **验收**：新增 `tests/test_<domain>.py` 覆盖 200/400/401/403/422 路径。

### 2. 鉴权边界
- 只读端点公开（/v1/stats、/v1/models、/v1/healthz）；写操作独立 `IF_ADMIN_KEYS` 池。
- 聊天端点 v7.7.1 公益开放（仅 per-IP 频控），生图公益开放。
- **验收**：`tests/test_auth_ip.py` + `tests/test_chat_auth.py` 全绿。

### 3. 数据层（api/db/）
- 新表走 `aiosqlite` + 连接池；列名白名单；值 `?` 参数化；0.2s 批量写合并。
- **所有 DDL（CREATE TABLE / CREATE INDEX / ALTER TABLE）集中在 `api/db/migrations.py`**
  —— 含加列（旧库兼容用 `PRAGMA table_info` 判存在再 `ALTER TABLE ADD COLUMN`，见
  `_apply_request_migrations`）。**不是** `db/core.py`（该文件只管连接池/批量写/WAL）。
  > 更正记录：本 SOP 原写「在 `db/core.py` 的 `_ensure_indexes` 加」——
  > 该函数**不存在**，且文件也错。2026-10-16 逐条核对后据实改为本处。
- **验收**：`tests/test_db_*.py` + `tests/test_async_sync_contamination.py`（AST 扫描）。

### 4. 后台任务
- fire-and-forget 用 `from api.background import spawn; spawn(coro, name="...")`（持强引用，防 GC）。
- 同步 I/O（DNS/urllib/file）用 `asyncio.to_thread` 下放。
- **验收**：`spawn` 返回的 task 在 `pending_count()` 可见，异常必 log.exception。

### 5. 前端（frontend/src/）
- 类型放 `api/<domain>.ts`，请求走 `apiFetch`（自带超时/错误规范化/取消）。
- 写操作 `adminHeaders()`；错误经 `ApiError` 抛出，UI 走 `ErrorRetry`/toast。
- 防重复提交：`disabled={loading}`；危险操作 `confirm()`；空态/错误态/骨架屏三态覆盖。
- 无障碍：input `aria-label`；装饰 emoji `aria-hidden`；`:focus-visible`；触控 ≥44px。
- **验收**（注意 3 个环境前提，见 SKILL.md §4）：
  ```bash
  cd frontend
  npx tsc -b                                             # 类型
  NODE_OPTIONS=--max-old-space-size=4096 npm run test     # vitest（512 会让 worker 起不来）
  npm run build
  # .cjs 审计需先起 preview 并提供 E2E_BASE（CI 即如此调用）：
  E2E_BASE=http://localhost:4510 node e2e-smoke.cjs
  E2E_BASE=http://localhost:4510 node a11y-audit.cjs
  E2E_BASE=http://localhost:4510 node resp-audit.cjs
  ```
  > `vitest` 的 `isolate:true` + `maxWorkers:2` 已固化在 `vite.config.ts`；
  > 若改动该文件，**两处必须一起改**（单改 `isolate:true` 会得到 28 errors / 0 tests）。

### 6. 文档 + CI + 发版
- `README.md` 端点表加行；`docs/SOP.md` 排查表加症状；`deploy/.env.example` 加新 `IF_*`
  （**注意**：新增配置字段必须挂 `Field(validation_alias="IF_XXX")`，否则
  `test_config_validate::TestEnvMappingContract` 会 fail —— 或显式登记进 `NO_ENV_BY_DESIGN` 并写明理由）。
- `ci.yml` 若新增 py 依赖或 lint 规则，同步 `ruff check api/ tests/ scripts/`。
- 版本 bump：`python scripts/sync_version.py --set X.Y.Z`
  （**全链 10 文件** + `scripts/e2e_v12.py` 契约）→ frontend/landing `npm run build`（dist 重建，
  防 `test_landing_built_dist_version_matches_source` 拦）→ `pytest tests/test_version_consistency.py -q` 全绿
  → `docs/verification-log.md` 追加 → 写 `docs/releases/release_notes_X.Y.Z.md`。
  > **文档版本漂移**：`sync_version` **不覆盖 `.claude/skills/`**，其中 `SKILL.md` 的
  > 「当前版本 vX.Y.Z」需**手工同步**（已由 `test_dev_doc_version_not_drifted` 兜住，漂移即红）。
- **发版**：`git tag -a vX.Y.Z -m "..."` + push tag；建 GitHub Release 用
  `./.venv/Scripts/python.exe scripts/create_release.py vX.Y.Z`（`gh` CLI 缺失时的通道）。
- **生产 E2E / 部署**：⚠ 线上服务器访问途径**用户尚未提供**（2026-10-16 明确）→
  **本轮及后续不做线上部署/热更新**，改做等价本地真实 E2E（见 SKILL.md 线上演示段的警示块）。
  不要因「线上没验」阻塞交付，也不要重复探测那台主机。

## 验收清单（每次必过）

- [ ] 后端 `pytest -m "not integration and not chaos and not slow"` 全绿（或仅预存 flaky）
- [ ] 集成 `pytest tests/integration/ -m "integration"` + `pytest -m "chaos"` 分轮全绿
- [ ] 前端 `cd frontend && npx tsc -b`（0 error）
      + `NODE_OPTIONS=--max-old-space-size=4096 npm run test` 全绿
      （**512MB 堆会让 vitest worker 起不来** → 表现为 `Timeout waiting for worker to respond` / `no tests`）
- [ ] E2E `cd frontend && E2E_BASE=<preview> node e2e-smoke.cjs`（22 断言）+ `resp-audit.cjs`（20 断言）全绿
- [ ] 版本一致性 `TestFrontendVersionConsistency` 3/3
- [ ] ruff `check api/ tests/ scripts/` 0 error
- [ ] 文档与实际一致（README 步骤可跑通、SOP 命令有效）
- [ ] **CI 到绿**（`gh` 缺失时用 GitHub API 查；`--ssl-no-revoke` 必需）。
      ⚠ 注意 **CI 失败是级联的**：前一步失败会让后续步骤 `[skip]`，
      所以「改一处没变绿」不等于「改错了」—— 要逐层看是哪一步在红。

## 红线（常驻）

- 付费 API 零真实调用（Mock/fixture 验证）
- 密钥 `IF_*` 环境变量，日志脱敏
- 同步 I/O 下放线程池
- 不可变优先；组件内联 `<style>` 迁 CSS Modules（Phase 2）
- 提交格式 `<type>: <description>`，归属全局禁用
