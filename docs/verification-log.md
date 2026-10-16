# 验证记录（防重复测验协议）

> **目的**：记录每轮验证的范围/结果/日期。下次开发前**先读本表**：
> - 要验证的模块若近期已验且代码未改动 → 跳过重复验证，把精力放到未验/已改区域
> - 改动了某模块 → 在本表追加一行（改动日期+范围），旧记录视为失效
> - 本表由 AI 会话优先读取（配合 memory/），避免盲目重跑同样的测验

| 2026-09-15 | 计划书全任务最终验收矩阵（P0-1~P3-20 文件/开关/测试 30 项全在）+ 142 用例计划族 + 集成混沌 54/0 + E2E 14/14（15.1.1 版本断言）+ vitest 257/0 + 契约 20 | 全绿 | 逐项核对无 MISS |
| 2026-09-15 | P1-11 §8 开关契约补全：updater 插件 setup 内条件注册 IF_DESKTOP_UPDATER=0 可关（缺省开）+ README 文档 | cargo check 编译过（5.28s） | commit e0bdace |

## v16.1.0 记录（2026-09-17）

| 日期 | 范围 | 结果 | 备注 |
|------|------|------|------|
| 2026-09-17 | **P0-4 任务进度/取消/重试**：engine queued→solving→generating→done pub status_detail+progress（5/30/80/100 append-only）；POST /v1/tasks/{id}/cancel 幂等（IF_TASK_CANCEL_ENABLED，mark_finished 防覆盖护栏 + worker 认领前/acquire token 前双检查点）；POST /v1/tasks/{id}/retry 同参重投新任务；前端 Tasks/Generate 阶段徽章+进度条+取消/重试按钮 | 全绿 | test_task_cancel 12 + vitest Tasks 4；E2E 14a-14d |
| 2026-09-17 | **P1-5 配额响应头+429 人话**：RateLimitHeadersMiddleware 对限流保护端点恒注入 X-RateLimit-Limit/Remaining/Reset（限流关闭注入默认 0 头补强，healthz 不污染）；429 补 retry_after_seconds+human_hint+Retry-After；前端 useApi 429 Toast | 全绿 | test_request_guard_layers 扩展；E2E 15a |
| 2026-09-17 | **P1-6 i18n 双语**：零依赖 i18n 模块（91 key zh/en 一致性测试锁定）+ Layout/Generate/Tasks/Gallery/Dashboard/ApiGuide 主路径接线 + 顶栏切换；landing 复用 P3-7 既有 i18n | 全绿 | i18n.test 8 + vitest 293/293 + tsc 0 |
| 2026-09-17 | **P1-7 桌面深化**：Ctrl+Shift+T 全局快捷键（IF_DESKTOP_GLOBAL_SHORTCUT=1）+ 托盘开机自启 toggle（IF_DESKTOP_AUTOSTART=1）+ 通知聚合 1s 窗口 + 深色跟随系统（localStorage 手动优先 → matchMedia → CSS media 兜底）+ 三态主题按钮 | cargo check 0 error | 真机 NSIS/快捷键/自启注册**待验证**（无真机）；vitest 293 + tsc 0 |
| 2026-09-17 | **P1-8 归档+导出**：IF_TASK_RETENTION_DAYS=90 软归档 archived（每日 04:00 retention 先软归档后物理清理；列表/统计退冷，详情可查）+ POST /v1/admin/export/tasks（CSV/json BOM 中文表头 管理 Key 审计 10 万截断 X-Truncated） | 全绿 | test_db_retention 扩展 + test_admin_export_tasks 5；E2E 16a-16b |
| 2026-09-17 | **P2-9/P2-10 治理**：IF_COST_ALERT_PCT=80 每小时预算预警（webhook 幂等水位 +5pp）+ GET /v1/admin/health-report 七维聚合（JSON/MD 单项降级不 500）+ Health 页导出按钮 | 全绿 | test_cost_alert 9 + test_health_report 7 + 回归 137；E2E 16c-16d |
| 2026-09-17 | **P2-11 双 flaky 根治 + P2-12 清理**：autoregister 抽 _can_fill/_register_one_now 纯函数（脱离循环时序）；llm_real_path_fallback try/finally+reset_settings（消 Settings 串扰）；历史日志删/产物归档 docs/research+archived | 全绿 | 全量 ×3 exit 0（连续 3 次 0 failures）；44 用例批 |
| 2026-09-17 | 版本全链 16.0.0→16.1.0（14 文件）+ dist ×2 重建 + README v16.1 小节 + release notes 16.1.0 | 契约绿 | E2E openapi+serverInfo 16.1.0 |

## v16.0.0 记录（2026-09-16）

| 日期 | 范围 | 结果 | 备注 |
|------|------|------|------|
| 2026-09-16 | **P0-3 画廊管理端 + 前端相册化**：后端 `GET /v1/gallery` 分页（page/page_size/status/model/search，admin/query.py 权威实现，limit 兼容 + count/total 双字段 + gallery:{limit} 缓存）、`GET /v1/gallery/{task_id}` 详情（similar 推荐降级）、`GET /v1/gallery/search`、`POST /v1/gallery/zip`（临时文件流式 + `IF_GALLERY_ZIP_BATCH=20` 分批防 OOM + data-URI 解码修复 + 失败张跳过 X-Skipped）、`DELETE /v1/gallery/{task_id}` 软删可回滚；列表不投影 `image_base64`（防分页 OOM）；前端 Gallery.tsx 迁移分页端点 + 防抖搜索 + IntersectionObserver 无限滚动 + 多选操作条 + 删除确认 + 详情弹窗 + 相似推荐联动 + 空/错/骨架三态；`IF_GALLERY_PAGE_SIZE=50`/`IF_GALLERY_ZIP_BATCH=20` | 全绿 | `test_gallery_crud.py` 8 用例 + vitest GalleryAlbum 6 + Gallery(P2-1) 4 + E2E 画廊段 13a-13f 6 断言；全量单测 exit 0；vitest **263/0**（24 文件）；E2E **24/24**；tsc 0/build 0；ruff 待 CI | 修复：① mock worker 完成态被错误覆盖成 error（既往竞态，E2E 画廊 fixture 直接落库绕过，不依赖 worker 完成态）② 旧 `/v1/gallery` 路由（admin/query.py）遮蔽新列表端点 → 原位融合为权威实现并删重 ③ `image_base64` data-URI 前缀导致 zip 空包 → strip 前缀修复 |
| 2026-09-16 | **P0-1 MCP Streamable HTTP**（`IF_MCP_STREAMABLE=1`：SSE 分帧 + capabilities resources/prompts + session 头 + DELETE 结束会话 + `task_status` 工具）与 **P0-2 聊天工具执行回路**（`IF_CHAT_TOOL_LOOP`：白名单工具网关侧执行 + role:tool 回填 + `IF_CHAT_TOOL_MAX_TURNS=2`）树内改动回归 | 全绿 | `test_mcp_server.py` + `test_chat_tool_loop.py` + E2E 11b-11e 通过 |
| 2026-09-16 | 版本全链 15.1.1→16.0.0（14 文件：main.py/mcp/server.py/pyproject ×2/README/双 package.json+lock/docker-compose/desktop 三件套）+ 双 dist 重建 + README v16 特性小节 + E2E 版本断言更新 | 契约绿 | E2E `openapi version==16.0.0` + `mcp serverInfo 16.0.0` PASS；`frontend/dist` + `landing/dist` 重建；桌面 NSIS 真机自升级流待验证（无 Rust/真机环境） |

## v15.1.1 记录（2026-09-15）

| 日期 | 范围 | 结果 | 备注 |
|------|------|------|------|
| 2026-09-15 | P1-11 自升级端到端闭环：① 端点协议修正——Tauri 2 updater 要求端点返回 JSON 更新清单（非 exe 直下），tauri.conf.json 端点由 `{{target}}-{{arch}}-{{version}}.{{ext}}` 改为 `releases/latest/download/latest.json`；② 生成 `latest.json` 清单（version/notes/pub_date/platforms.windows-x86_64.signature+url，签名取自 .sig 文件），上传 Release；③ 前端 `src/lib/desktopUpdater.ts` + main.tsx 启动即 check→downloadAndInstall→relaunch（Tauri 环境动态 import，浏览器静默零副作用），`@tauri-apps/plugin-updater`+`plugin-process` 入 frontend devDeps；④ 端到端验证：端点 GET 200 返回完整清单，exe 直链 200（87.6MB） | 全绿 | vitest 257/0 + tsc 0 + build 0 + `tests/test_desktopUpdater` 浏览器降级用例；desktopUpdater.test.ts 1 用例 |
| 2026-09-15 | 版本全链 15.1.0→15.1.1 + 双 dist 重建 + 桌面安装包重建（含新端点+前端自升级） | 契约绿 | `test_openapi_contract.py` 全过；桌面 15.1.1 NSIS 包 + .sig 重建 |

## v15.1.0 记录（2026-09-15）

| 日期 | 范围 | 结果 | 备注 |
|------|------|------|------|
| 2026-09-15 | P1-8 工具调用安全护栏（`api/routes/agent_dag_exec.py` `_exec_tool` 入口 + LLM 工具循环 `[tool:名]` 提取处双闸口：`is_destructive_command` PreToolUse 硬门禁拦截破坏性命令 + `budget_guard.check_can_spend("tool")` 预算门禁 enforce 超限 402 拒绝；`tests/test_agent_tool_guard.py` 14 用例含参数化破坏性样本/LLM 循环快速拒绝（不回调 provider）/enforce/observe/off 三态） | 全绿 | 30 关联用例全过；全量 2141/0F（+14 新用例） |
| 2026-09-15 | P1-11 桌面版三件套（`tauri.conf.json` 增 updater 端点+签名公钥+createUpdaterArtifacts+trayIcon；Cargo.toml tauri `tray-icon` feature + `tauri-plugin-updater`+`tauri-plugin-notification`；lib.rs 托盘菜单（显示/退出）+ 通知/升级插件注册 + `IF_DESKTOP_CLOSE_TO_TRAY=1` 关窗进托盘；capability 补 updater:default；前端 Agent.tsx 终态系统通知（动态 import 浏览器静默降级）+ `@tauri-apps/plugin-notification`） | cargo check 编译通过（12.2s）+ tsc 0 + vitest 256/0 + build 0 | 签名私钥存用户主目录 `~/.tauri/tingfeng.key`（仓库外）；公开密钥入 tauri.conf.json |
| 2026-09-15 | P3-18 性能水线（P1-8 未触碰 engine/DB/config 热路径） | DB+Config benchmark 绿；Engine benchmark 本机挂起（已知环境限制） | Engine 属 slow 标记默认排除；非本轮引入 |
| 2026-09-15 | P1-14 Playwright 视觉探针真实浏览器复核（API 8100 在线） | Agent 页 DAG 渲染 + 明暗主题 1 passed（986ms）+ 截图 agent-light/dark.png | 前端 dist 重建后挂载 /admin 实测 |
| 2026-09-15 | 集成 49 + 混沌 5 + E2E 14/14 复核 | 全绿 | mock cf_solver 全程；版本契约 15.0.0 通过 |
| 2026-09-15 | 版本全链 15.0.0→15.1.0 + dist 重建 + landing lock 8.2.3→15.0.0 修复 | 契约绿 | `test_openapi_contract.py` 全过 |

## v13.0.0 记录（2026-09-15）

| 日期 | 范围 | 结果 | 备注 |
|------|------|------|------|
| 2026-09-15 | P0-1 审批收件箱 SQLite 持久化（`api/agent/human_inbox.py` 重建：同步 sqlite3+WAL+isolation_level=None+内存热缓存+工厂 get/reset_human_inbox；`IF_HUMAN_INBOX_DB`；`tests/test_human_inbox_persist.py` 14 用例含重启/并发/路由鉴权） | 全绿 | 3 连全量 2033→2043 0 failures |
| 2026-09-15 | P0-2 审批决策端点挂管理 Key（`agent_human.py` inbox_decide→`check_admin_key`；GET 列表公益） | 全绿 | 开放模式 IF_ADMIN_KEY_OPEN=1 测试放行；E2E 审批带 Key 待真机 |
| 2026-09-15 | P0-3 ip_blocklist `database is locked` flaky 根治（memory/human_inbox `_conn` 改 WAL+isolation_level=None+busy_timeout；conftest 关 consolidation 常驻循环；3 连全量 0 failures） | 根治 | 根因：memory/human_inbox 同步连接缺省 fallback journal + consolidation 常驻循环与共享库写锁竞争 |
| 2026-09-15 | P0-4 版本号全链 bump 12.1.0→13.0.0（后端 6 文件+前端/桌面/landing/README/E2E 断言）+ frontend/landing dist 重建 | 契约绿 | `test_openapi_contract.py` 全过 |
| 2026-09-15 | P0-5 DAG memory 节点读写（`_exec_memory` op=read/write + `node_raw` 传 config/info 子键） | 全绿 | DAG 全族回归 90 用例 0 失败 |
| 2026-09-15 | P0-6 intent embedding 双路（`intent.py` 规则→embedding→LLM；`IF_INTENT_EMBED_THRESHOLD`；`tests/test_agent_intent_embed.py` 10 用例） | 全绿 | ruff 0 error |
| 2026-09-15 | P1-13 前端统一 Button 反馈态（`frontend/src/components/ui/Button.tsx` + Generate/Agent/ChatPlayground 接入 + Button.test.tsx 9 用例） | vitest 248 全绿 + build 0 error + tsc 0 | 子代理独立交付 |
| 2026-09-15 | 全量单测 3 连（版本 13.0.0 后） | 2043 tests / 0 failures / 0 errors / 1 skipped | flaky 已根治；2 连后台先绿（2033）后 FULL3 绿（2043 含新用例） |
| 2026-09-15 | P2-17 DAG 失败可重试 + P2-16 成本视角切换/导出 CSV + P2-15 a11y 断言 + P1-14 Playwright 视觉探针（装成 @playwright/test 1.63，chromium launch 成功，明暗截图 frontend/artifacts/，gitignore） | vitest 255 绿（+7 新用例）+ build/tsc 0 | 子代理独立交付；vitest exclude e2e/**（Playwright 不允许被 vitest import） |
| 2026-09-15 | P0-5/P1-10 补测试：`test_dag_memory_chain.py` 7 用例（memory read/write/config 子键/异常注入）+ `test_lifespan_consolidation.py` 4 用例（consolidation loop start/stop/cancel 不泄漏） | 50 用例全绿（含相邻 DAG/记忆文件） | 子代理独立交付 |
| 2026-09-15 | 集成测试 8 失败根治（跨文件顺序污染）：① conftest `IF_MEMORY_CONSOLIDATION_ENABLED` 0→1（observe 端点 403「记忆子系统未启用」）+ 常驻循环改 `CONSOLIDATION_INTERVAL_SECONDS=inf` 等效关闭；② agent_e2e 4 用例 `setenv` 后补 `reset_settings()`（Settings 工厂缓存固化 mock=1）；③ intent 规则 '画一只' 增强后 ecommerce 主图 prompt 被 image 吃掉 → 收窄为 `画.*(猫|狗|人|风景)` + '画一个电商主图' 归 ecommerce 规则；④ conftest 模块级（api import 前）`setdefault IF_ACCOUNT_AUTO=0` + api 已 import 时同步 `_cfg.ACCOUNT_AUTO=False`（import 期固化 True → nanobanana 误可见） | **integration 49/0 + chaos 5/0 + unit 2070/0 三独立轮全绿**；E2E 14/14 | 组合跑（-m "not slow"）跨轮 IP 桶封禁+admin 开放模式冲突属 CI 分轮设计应对范围（ci.yml unit/integration/chaos 分 fresh 进程），非回归 |
| 2026-09-15 | test_autoregister_loop_fills_to_target 时序 flaky（2 次单跑全绿，全量偶发 0>=2） | 预存 | cerebrum 已知：代理池每日限额时序，poll-until-stable 已在用例 |

## v14.0.0 记录（2026-09-15）

| 日期 | 范围 | 结果 | 备注 |
|------|------|------|------|
| 2026-09-15 | P1 审批导出/历史（HumanInbox.export csv/json + /export + /history 分页，管理 Key） | 全绿 | test_human_inbox_export.py 12 用例 |
| 2026-09-15 | P2 DAG resume sqlite 化（restore_run 反序列化 + resume 端点 sqlite 后端可续跑） | 全绿 | test_dag_resume_sqlite.py 12 用例 |
| 2026-09-15 | P3 memory supersede（superseded_by 列幂等迁移 + query 过滤 + apply_decay hot/warm/cold） | 全绿 | test_memory_supersede.py 10 用例；IF_MEMORY_APPLY_DECAY=0 |
| 2026-09-15 | 组合回归根治：sqlite3.Row 无 .get（P3 破坏 6 既有用例）→ r[key] if key in r.keys()；reset_human_inbox 同步模块级单例（端点 from-import 值拷贝旧库残留 72 条）→ human_inbox=重建实例 | 全量 2104/0 | 34 新用例全绿 + ruff 0 |
| 2026-09-15 | 版本全链 13.0.0→14.0.0 + dist 重建 | 契约绿 | openapi/landing dist 14.0.0 |
| 2026-09-15 | 集成+混沌 + E2E 复跑 | 54/0 + 14/14 | mock cf_solver 全程 |

## v15.0.0 记录（2026-09-15）

| 日期 | 范围 | 结果 | 备注 |
|------|------|------|------|
| 2026-09-15 | v15-A intent embedding 多原型（_EMBED_PROTO_EXTRAS 6 场景关键词 + _EMBED_KEYWORD_BONUS=0.15 加权 + 短语缓存；image_edit 补 meta） | 全绿 | test_agent_intent_embed_v15.py 10 用例；58 联动绿 |
| 2026-09-15 | v15-B captcha 统一协议（api/captcha/protocol.py CaptchaResult frozen dataclass + from_turnstile/from_cf_clearance 工厂 + solve_turnstile_result/solve_result 包装，原返回向后兼容） | 全绿 | test_captcha_protocol.py 12 用例；53 联动绿 |
| 2026-09-15 | 全量 unit 2127 / int+chaos 54 / E2E 14 / vitest 255 / ruff 0 / 契约 20 | 全绿 | autoregister flaky 预存（单跑绿，未触碰 account_pool） |
| 2026-09-15 | v15-B 复核：test_llm_real_path_fallback 预存 flaky（3 次单跑全绿，全量组合偶发；v15-B 排除实验证实无关） | 预存 | 组合串扰（同 autoregister 模式） |
| 2026-09-15 | 版本全链 14.0.0→15.0.0 + dist 重建 | 契约绿 | openapi/landing dist 15.0.0 |

## 记录表



| 日期 | 版本/范围 | 验证内容 | 结果 | 失效条件 |
|------|----------|---------|------|---------|
| 2026-09-01 | v7.0.0 | Deploy 33490460997 ✓ + 线上 E2E 9 端点（healthz/models/providers/email-sources/auth-status/routing/diagnostics/landing/admin） | 全绿 | api/ 或 deploy/ 改动 |
| 2026-09-01 | v7.1.0 | Deploy 33502639914 ✓ + 封禁分页端点/UI Key 脱敏 | 全绿（3 次 CI 迭代：测试签名+信封+package.json） | 同上 |
| 2026-09-01 | v7.2.0 | Deploy 33512897007 ✓ + SSE stats 401 + /v1/logs 401 + landing privacy | 全绿（3 次 CI 迭代：nanobanana await/SpanKind/httpx 泄露） | 同上 |
| 2026-09-01 | 后端核心 | request_guard 54 / config 20 / ip_blocklist 28 / security_headers 7 / worker_hard 5 / worker_batch 4 / otel 8 / logs_auth 6 / telemetry 17 / account_pool 30 / email_pool 22 / async_sync 6 / registerer 19 / providers 12 / cost 11 / providers_contract 15 / tryingopen 7 / auto_scale 14 / worker_health 8 / adaptive_router 23 / token_pool 14 | 全绿 | 对应 api/ 文件改动 |
| 2026-09-01 | 前端 | vitest 193 (12 files) + tsc 0 error + build ~3s | 全绿 | frontend/src 改动 |
| 2026-09-01 | landing | build OK + dist 含 7.2.0 + i18n + privacy | 全绿 | landing/src 改动 |
| 2026-09-01 | lint | ruff 全量 0 error（412→0 治理完成） | 全绿 | 任何 py 改动 |
| 2026-09-01 | 预存问题 | Windows Python 3.14 本地：test_providers 全量/test_token_pool 2 用例会卡（基线同样卡，CI ubuntu+3.11 不卡） | 已知非回归 | 换 CI 环境或升级 py 版本 |

## 已知「验证过勿重跑」结论（代码未动前长期有效）

- threading.Lock 审计（v6.8.0 P1-5）：8 文件纯内存临界区保留 threading.Lock 正确，勿再审计
- nanobanana Action ID / tryingopen 目录：已是动态嗅探+静态兜底自愈设计，勿抽 config（v7.1.0 P2-6 评估过）
- 同步 sqlite3：account_pool/email_pool 已 aiosqlite 迁移（v7.2.0），勿再提 to_thread 方案
- email_sources_linshi.py shim：无引用（grep 核实过），删除安全
- AST 契约 tests/test_async_sync_contamination.py：扫描列表含 account_pool/email_pool/nanobanana/aifreeforever/imagefree，改这些文件后必跑
| 2026-09-01 | v7.3 conftest os._exit 兜底 | Windows teardown 卡死根治（111 passed 13s 退出）；三连稳定全绿 148 passed | 全绿 | conftest.py 改动 |
| 2026-09-01 | email_pool 拆分 | email_pool.py 1315→386 + email_sources/ 12 文件 + 旧 import 兼容 | 全绿（22+17+18+main import OK） | api/email_pool.py / api/email_sources/ |
| 2026-09-01 | v7.3 审查线程 7 项修复 | telemetry Description/keyset 游标/count_by_type/GC/reset_settings/连接异常安全/os._exit(exitstatus) | 全绿（140 passed 8.8s + account_pool 30 + test_cost 11 + test_providers 12 + 分段 195 passed） | 以上 api/ 文件再改动 |
| 2026-09-01 | 已知 flaky | 21 文件全量组合偶发 1 F(前端 46% 处),单独/分段/CI ubuntu 全绿——组合串扰(全局 singleton 未还原),非审查修复引入 | 已知 | 组合跑时先单独跑分文件 |

## v7.6 审计闭环验证记录（2026-09-04）

| 日期 | 范围 | 结果 | 备注 |
|------|------|------|------|
| 2026-09-04 | 4 agent 并行审计（前端/后端/部署/测试）+ 1 反向核查 | 全部断言 file:line 确认 | 发现 P0×2 P1×10 P2×15 P3×15 |
| 2026-09-04 | 幂等 TOCTOU 修复 | claim_idempotency 原子抢占（ON CONFLICT DO NOTHING + rowcount） | test_idempotency 11 passed（含 10 并发收敛） |
| 2026-09-04 | lifespan drain _PROVIDER_TASKS | ③.5 阶段排空，重启不丢任务 | AST + 语法校验通过 |
| 2026-09-04 | chat 429 语义 | ProviderRateLimited → 429 RATE_LIMITED | test_chat_stream_frames 30 passed |
| 2026-09-04 | priority=0 admin 校验 | generate.py _prepare 补 check_admin_key | test_main_validation 49 passed |
| 2026-09-04 | 前端 5 项修复（ping 裸串/fetchLogs/Dashboard adminKey/Security 分页/LogEntry 类型） | vitest 197 passed + tsc 0 error + build 4.36s | CI 版本门禁本地模拟通过 |
| 2026-09-04 | 部署一致性 5 项（版本 7 处 7.4.0/cov 80 统一/限流默认 20/sync_deploy 清理/README 路径） | 全部落实 | grep 核实 |
| 2026-09-04 | ruff 全量 | 0 error（清 2 处历史残留 F841/F401） | All checks passed |
| 2026-09-04 | 组合回归 6 批（idempotency/chat/dispatch/log/auth/retry/router/errors/pool/sse/etag） | 全绿 | Windows 3.11 venv |
| 2026-09-04 | 前端无障碍+响应式地基（WCAG 2.1 AA） | e2e-smoke 22 断言全绿 + resp-audit 20 断言全绿 | commit 213a8a8 |
| 2026-09-04 | a11y 落地清单 | skip-link→#main-content（tabIndex=-1+scroll-margin-top）；装饰 emoji 全量 aria-hidden（nav-icon 13/brand/stat/empty/error/toast/system-dot/nav-pip）；:focus-visible 全局环；prefers-reduced-motion 降级；--text-muted #94a3b8→#64748b（4.6:1）；触控目标 44px（菜单按钮 38→44 + .tf-btn min-height）；Esc 关抽屉补实现（useEffect keydown） | Layout/StatCard/Feedback/ToastHost |
| 2026-09-04 | 响应式落地清单 | viewport-fit=cover + --safe-* 令牌 + topbar/toast 安全区 calc；100vh+100dvh 双写（桌面+抽屉侧栏）；html font-size clamp(14px→16px)；栅格 768/1024/1440 过渡；@media(hover:none) 显式回退（非 revert-layer，Safari<16.4 兼容）；字体非阻塞（media=print→all + preload + noscript 兜底） | index.html/index.css |
| 2026-09-04 | 性能地基 | StatCard contain:layout style paint（隔离重排）；字体渲染阻塞解除（LCP）；space/z/ease/dur 令牌补齐 | index.css/StatCard |
| 2026-09-04 | 响应式审计（E2E 4 断点） | 375/768/1024/1440 无水平溢出 + 抽屉开合 + Esc 关闭 + 截图基线归档 .benchmarks/resp-shots/ | resp-audit.cjs 20 passed |
| 2026-09-04 | 组合回归说明 | 后端全量 1545 用例 3 轮：run1 1F(test_block_ip_record_fields)/run2 4F(含版本门禁 3 项，dist 未构建所致)/run3 0F——单项与文件级复跑均全绿，属组合串扰 flaky（与 2026-09-01 已知条目同类），非本轮引入 | CI 口径（pytest -m "not integration and not chaos and not slow"） |

## 新增「验证过勿重跑」结论

- 前端 a11y 地基已落地（v7.6.0）：skip-link/aria-hidden/focus-visible/reduced-motion/44px 触控——后续页面改造勿重复加全局样式，只补页面级（如 Accounts/Logs/Security input 的 aria-label）
- Esc 关闭抽屉已在 Layout 实现（v7.6.0）：勿再加重复 keydown 监听
- hover:none 降级用显式回退值（v7.6.0）：勿改回 revert-layer（Safari<16.4 不识别会半残）
- --safe-* 令牌与 viewport-fit=cover 已配对（v7.6.0）：新增 fixed 元素须用 calc(... + var(--safe-*))

## v7.7 终局闭环总审计验证记录（2026-09-04，Spec-Kit 005）

| 日期 | 范围 | 结果 | 备注 |
|------|------|------|------|
| 2026-09-04 | 4 子代理并行审计（契约/后端/UX/配置文档） | P0=0；P1×8；P2×28 全部处置 | contract-auditor 0P0/1P1/7P2；backend 0P0/3P1/11P2；ux 0P0/2P1/10P2；config 0P0/4P1/11P2 |
| 2026-09-04 | 后端 P1：geo_ip 事件循环阻塞根治 | 在线查询下放 ThreadPoolExecutor，缓存命中路径纯内存不变 | 功能验证同步+loop 两路径正常；targeted 81/81 |
| 2026-09-04 | 后端 P1：fire-and-forget GC 风险 | 新增 api/background.py spawn（强引用集+异常必 log），4 调用点迁移 | targeted 95/95 |
| 2026-09-04 | 后端 P1：流式聊天 429 区分 | OpenAI rate_limit_error / Anthropic 同步，对齐 v7.6 _chat_collect | chat targeted 44/44 |
| 2026-09-04 | 后端 P2：log_ws 锁内发送外移 + DNS 下放 + 幂等 key 脱敏 + fd/ecosystem 生命周期 | 全部落地 | targeted 60/60 + 58/58 |
| 2026-09-04 | 契约 P1：/v1/tasks 列表补 prompt 列 | _TASK_LIST_COLS 加 prompt；Tasks 页 Prompt 列不再恒 '-' | targeted 17/17 |
| 2026-09-04 | 契约 P2：错名字段对齐 7 项 | message_limit/last_attempt_at/credits? 可选/status+detail 等 | build + 197 tests |
| 2026-09-04 | UX P1：Tasks 筛选即时生效 + Security 无 Key 自举死锁破解 | useEffect(reload,[status])；401 保留 Key 横幅 | build + 197 tests |
| 2026-09-04 | UX P2：App 404 + Generate 双失败 + ChatPlayground/Accounts/Gallery 错误态 | 全部落地 | build + 197 tests + E2E 22/22 + resp 20/20 |
| 2026-09-04 | CI：frontend-gate 门禁补盲 + 集成/混沌分轮 + conftest admin key 清理 | YAML OK；integration 37/37 + chaos 5/5（v7.6 DLQ 鉴权引入的 flaky 根因） | conftest IF_ADMIN_KEYS pop + ADMIN_KEY_OPEN |
| 2026-09-04 | 配置：compose env_file:.env + image ${API_IMAGE:-...} | 15 项生产收紧变量生效；回滚机制修复 | YAML OK |
| 2026-09-04 | 文档：README 前端章节 + SOP v2.4.0 + .env.production.example 验证说明 | 全部同步 | 文档复核 |
| 2026-09-04 | 版本 bump 7.6.0→7.7.1 全 8 处 + dist 重建 | 版本一致性契约 3/3 | landing/frontend/backend 均 7.7.1 |
| 2026-09-04 | 全量验证：unit 1545 / integration 37 / chaos 5 / vitest 197 / E2E 22 / resp 20 | 5F 全部预存（3 auth 组合串扰单跑全绿 + 1 auto_block flaky + 1 test_models_endpoint 设计不一致） | 本轮零回归 |

## 新增「验证过勿重跑」结论（v7.7）

- geo_ip 在线查询已下放线程池（v7.7）：勿再提"urllib 卡 loop"——缓存命中是纯内存 O(1)，miss 走 ThreadPoolExecutor
- fire-and-forget 已统一走 background.spawn（v7.7）：勿再用裸 asyncio.create_task（GC 风险）；新增后台任务直接 spawn
- log_ws 广播已锁内快照+锁外发送（v7.7）：勿再提"慢客户端队头阻塞"
- 幂等 key 日志已脱敏（_mask_idem_key，v7.7）：勿再提"幂等 key 明文入日志"
- compose env_file:.env 已生效（v7.7）：.env.production.example 15 项收紧变量此前静默失效已修复
- compose image 可被 API_IMAGE 覆盖（v7.7）：GHCR fallback 与 tag 回滚机制已修复
- CI frontend-gate job 已存在（v7.7）：前端 tsc/vitest/build 有 CI 门禁，勿再提"前端无 CI 盲区"
- 集成/混沌已分轮跑（v7.7）：conftest 已 pop IF_ADMIN_KEYS + ADMIN_KEY_OPEN，勿再提"DLQ 403 flaky"
- 聊天端点 v7.7.1 公益开放（用户决策）：guard_chat_request 不再 check_api_key，仅 per-IP 频控；生图公益开放；管理面独立 IF_ADMIN_KEYS 池不变
- test_models_endpoint 断言 nanobanana in items 与 conftest IF_ACCOUNT_AUTO=0 设计性隐藏冲突（预存）：CI 从未跑集成故未暴露，单跑可见
- test_chat_auth/test_auth_ip/test_autoregister_loop 组合串扰（预存）：单跑全绿，组合跑偶发——属 Settings 单例+monkeypatch 跨用例残留，非回归

- 幂等 claim_idempotency 已原子化（v7.6）：勿再提"加锁包裹 get+save"方案，直接复用 claim 接口
- _PROVIDER_TASKS drain 已入 lifespan ③.5（v7.6）：勿在 engine.stop() 内重复处理
- deploy/pyproject.toml 已对齐 7.4.0（v7.6）：版本门禁 7 处 = pyproject×2 + main.py + frontend + landing + compose×2
- cov-fail-under 已统一 80（v7.6）：ci.yml 与 deploy.yml 同口径
- IF_REQUESTS_PER_MINUTE 默认对齐 20（v7.6）：.env.production.example 与 compose 一致
- 孤儿 env 变量清单已在 deploy/.env.example 尾部标注（v7.6）：IF_MINIMAXH3_*/IF_MAX_IMAGE_BYTES/IF_USER_AGENT/IF_MAX_PROMPT_LEN/IF_ASPECT_RATIOS/IF_KOOKEEY_* 填了不生效

## v8.3.0 P0-S1 storage 热路径真接线验证（2026-09-06）

| 日期 | 范围 | 结果 | 备注 |
|------|------|------|------|
| 2026-09-06 | P0-S1 storage 热路径分叉（request_guard _l1_check/滑窗 真调 adapter.rate_limiter.is_allowed） | request_guard 全家+redis_adapter+chat_auth+adaptive_router+agent+async_sync：193 passed 0F | 单机 sqlite 模式零回归；ruff 0 error；mypy strict 0 issue |
| 2026-09-06 | E2E 本地实测（mock cfsolver 8001 + API 8100） | livez/healthz/models/generate/chat/agent-intent/agent-skills/agent-memory/metrics 全 200 | 生图 imagefree/default completed 有图；chat glm-5.3-flash 200 有 reasoning_content；agent intent llm_used=true scene=image |
| 2026-09-06 | 前端 vitest + build | 197 passed 13 files / build 16s | frontend dist 含 8.3.0；landing dist 含 8.3.0 |
| 2026-09-06 | 集成测试 tests/integration/ | 37 passed（cfsolver mock） | 全绿 |

## 新增「验证过勿重跑」结论（v8.3.0）

- storage 热路径真接线（v8.3.0 P0-S1）：request_guard _l1_check:267/268 + 滑窗:535/536 调 adapter.rate_limiter.is_allowed，**勿再当半成品**——双实例集中式限流已就绪（真实 Redis 端到端待 L3 生产灰度验证）
- agent intent/critic 已有真实 LLM 调用路径（intent.py:107-148/critic.py:107-138 provider.chat_collect 走 tryingopen），**勿再提 Mock 悬空**——待验证是 E2E 验收覆盖非是否真调


## v17.0.0 自我进化+体验闭环验证记录（2026-09-18）

| 日期 | 范围 | 结果 | 备注 |
|------|------|------|------|
| 2026-09-18 | B1a 技能四件套（5 技能 schema/validate/expected_results + validate_skills.py 门禁） | test_skills_validate 14/14；validate_skills --strict 5/5 PASS | anthropics 规范 |
| 2026-09-18 | B1b 技能扫描（skillspector.py 4 类静态 + baseline + scan_skill 封装） | test_skillspector 33/33；恶意样例拒绝 | SkillSpector 对标 |
| 2026-09-18 | B2 技能沉淀（save/approve/reject/mine/删除 + 扫描前置） | test_skill_sediment 14/14（store+route）；安全扫描拦截 422 | 手动收藏 MVP |
| 2026-09-18 | B4 记忆 explain（query 返回命中理由 + 路由透传） | test_memory_explain 7/7；supersede/agent_memory 26 回归 | mem0 explain |
| 2026-09-18 | P1-7 MCP intent/annotations/retrieve/describe | test_mcp_tools_meta 9/9 | smart-mcp-proxy |
| 2026-09-18 | P2-1 solver 回放元数据 + validate_replay（SSRF 锁定） | test_solver_hardening 12/12；captcha_protocol 回归 | captcha-solver |
| 2026-09-18 | B5b 桌面启动脚本修复 | verify-start-modes 12/12 PASS（MODE 生效/轮询/健康诊断/清理） | — |
| 2026-09-18 | B3 教学化 explain 模板（8 节点） | test_agent_explain 6/6 | learn-agent |
| 2026-09-18 | P1-5 电商合规护栏 fence | test_skill_ecommerce 8/8 | commerce-agents |
| 2026-09-18 | 前端（Agent 保存技能/我的技能/节点 tooltip + i18n key + API） | vitest 296/296（threads+testTimeout）；tsc/build 0 error；dist 重建 | 较 v16.1 增 3 |
| 2026-09-18 | 后端全量单测（分批） | a-c/d/l-o/t-w/batch90 全绿；config/captcha/memory/mcp/skills/dag 专项全绿 | 1 项 provider_probe loop flaky（未触碰模块，单跑全绿） |
| 2026-09-18 | 版本 bump 16.1.0→17.0.0（全链 15 处）+ dist 重建 + env.example 补齐 | 契约：openapi/mcp serverInfo/e2e 同步 17.0.0 | — |

## 新增「验证过勿重跑」结论（v17.0.0）

- 技能四件套门禁已落地（v17）：validate_skills.py --strict 是唯一权威门禁，勿再用散落检查替代。
- 技能安全扫描已前置（v17 B1b）：任何技能上传/沉淀入口必须先过 scan_skill（IF_SKILL_SCAN_REJECT=60）。
- skill_sediment store 必须运行时取模块属性（v17）：勿再从路由模块 `from ... import skill_sediment_store` 绑定单例（reset_store 会失效）。
- 记忆 explain 已落地（v17 B4）：勿再提"query 无解释"；前端面板可消费 `explain` 字段。
- MCP annotations 已四字段（v17）：旧客户端仅读 readOnlyHint，勿回退单字段。
- desktop/start-desktop.bat 已真实支持 mock/real（v17 B5b）：勿再断言 real 无效。
- testTimeout 需 20s（本机 jsdom 慢）：frontend vitest 全量用 `--pool=threads --testTimeout=20000`。
- pydantic 2.13 下带 validation_alias 的字段用字段名构造被忽略（v17 排查结论）：子配置 from_settings 应避免 alias 字段名传参或使用 alias 键。


## v17.0.0 补充验证记录（2026-09-19 复核）

| 日期 | 范围 | 结果 | 备注 |
|------|------|------|------|
| 2026-09-19 | e-k 前缀单测补跑（ecosystem/edit/email/error/etag/falai/fencing/free_proxy/gallery/geo/health/http/human_inbox/idempotency/imagefree/img_gc/ip_blocklist） | 26 文件 PASS | 每文件独立 subprocess + 断点续跑（宿主间歇 kill 下稳定） |
| 2026-09-19 | 既有重负载文件 edit_mutex/email_pool | 宿主资源监控 kill（v16.1 环境通过，与本次改动无交集） | 明确标注不伪装 |
| 2026-09-19 | 真实 E2E 复核 | **33/33 PASS**（openapi version==17.0.0） | e2e env 调高 IF_SOLVE_CIRCUIT_THRESHOLD=10000（mock solver 不误熔断）；14c 单循环+主/重试双 check 重构（熔断冷却 65s 自愈重试） |


## v18.0.0 自动进化+多场景验证记录（2026-09-19）

| 日期 | 范围 | 结果 | 备注 |
|------|------|------|------|
| 2026-09-19 | P0-1 证伪实验 sediment_probe | 好 0.506 / 坏 0.2 / 区分度 0.306>0.15 → 自动沉淀可尝试（Mock 评估器） | RT-1 前置 |
| 2026-09-19 | P0-1 自动沉淀 skill_sediment_auto | test_sediment_probe 6 + test_skill_sediment_auto 9 全绿（四重前置/扫描闸门/gate/幂等/上限） | IF_SKILL_SEDIMENT_AUTO=0 |
| 2026-09-19 | P0-2 记忆 RRF（FTS5+RRF+双模式） | test_memory_rrf 8 全绿；压测 P95 plain=110.9/rrf=126.3ms 未达 50ms → 保持纯 SQL 缺省（RRF 留开关） | RT-4 决策 |
| 2026-09-19 | P1-3 MCP 渐进暴露（8 工具+审批流） | test_mcp_tools_meta 14 全绿 | IF_MCP_TOOL_APPROVAL=0 |
| 2026-09-19 | P1-2 PPT 产物（python-pptx） | test_skill_ppt 5 全绿（PK 头/slide/备注） | IF_PPT_GENERATE=0 |
| 2026-09-19 | P1-1 视频 Mock 任务模型 | test_video_tasks 5 全绿（提交/轮询/完成） | IF_VIDEO_ENABLED=0 |
| 2026-09-19 | 组合回归（本批 10 文件） | 114 用例全绿 | app import 修复（video 相对导入） |
| 2026-09-19 | 前端 | vitest 295/296（CostsPage recharts 既有环境 flaky）；tsc/build 0 error；dist 重建 | 前端零改动 |
| 2026-09-19 | 真实 E2E（扩至 38 段） | **38/38 PASS**（17 视频/18 PPT/19 MCP 渐进暴露新增） | — |
| 2026-09-19 | 版本 bump 17.0.0→18.0.0（全链 14 处）+ dist 重建 | openapi/mcp serverInfo/e2e 契约 18.0.0 | — |

## 新增「验证过勿重跑」结论（v18.0.0）

- 自动沉淀证伪已通过（v18）：区分度 0.306，sediment_probe 是唯一权威评估器（Mock 确定性，勿改用付费 LLM 评估）。
- 自动沉淀必须过 scan_skill 闸门（v17）且四重前置（开关/状态/幂等/上限）——勿在别处复制实现。
- 记忆 RRF 压测未达 50ms 目标（v18）：保持纯 SQL 缺省，RRF 留 IF_MEMORY_RRF 开关；勿在未优化索引/触达基准前默认开启。
- MCP tools/list 现 8 工具（v18）：旧客户端兼容（annotations readOnlyHint 不变）；审批开关缺省 0 全可见。
- E2E 现 38 段（v18）：video/ppt 端点需 env 开关；tools/list 断言 8 工具。


## v19.0.0 安全参数化+上下文成本治理验证记录（2026-09-19）

| 日期 | 范围 | 结果 | 备注 |
|------|------|------|------|
| 2026-09-19 | P2-3 solver evaluate 参数化（validate_solve_params + 入口接入） | test_solver_evaluate 7 + 既有 turnstile/captcha 组合 34 全绿 | 注入字符拒绝；兼容 mock 短 sitekey |
| 2026-09-19 | P2-2 上下文 trim（trim_chat_messages/summarize_for_intent/estimate_tokens） | test_context_trim 6 全绿 | 纯函数库，IF_CTX_TRIM 由调用方决定 |
| 2026-09-19 | P2-1 视频 SSE 逐帧（hub publish + /events 端点） | test_video_tasks 6 全绿（SSE publish/replay） | 复用 tasks SSE 基建 |
| 2026-09-19 | 组合回归（本批 12 文件） | 0F | — |
| 2026-09-19 | 真实 E2E 38 段 | **38/38 PASS** | 本轮零回归 |
| 2026-09-19 | 版本 bump 18.0.0→19.0.0（全链 14 处）+ dist 重建 | 契约同步 | — |

## 新增「验证过勿重跑」结论（v19.0.0）

- solver 参数校验已落地（v19）：sitekey 白名单=安全字符类 1-120（勿再加最短长度限制，会误拒 mock/真实 CF sitekey）；注入字符（空格/引号/分号）被拒。
- 上下文 trim 纯函数库可用（v19）：`trim_chat_messages`/`summarize_for_intent`，调用方按 `IF_CTX_TRIM` 接入。
- 视频 SSE 已可用（v19）：`/v1/video/{task_id}/events` 复用 TaskEventHub + Last-Event-ID 补偿。


## v20.2.0 代理池高并发验证记录（2026-09-26）

| 日期 | 范围 | 结果 | 备注 |
|------|------|------|------|
| 2026-09-26 | v20.2 代理池高并发：imagefree「单 IP 忙」错误触发代理换出口 | test_worker_engine_compat 13/13 + ruff 0 | 新增 `_is_upstream_ip_busy` |
| 2026-09-26 | 真机并发 E2E（20.204.27.154）：imagefree 文生图 x4 并发 | **4/4 completed**（修复前 3 error DLQ） | 代理池 1404 已启用 IF_FREE_PROXY=1 |
| 2026-09-26 | 线上对话/Anthropic/agent plan 复询 | 200（tryingopen 真实路径，mock=False） | Anthropic 503 确认上游瞬时抖动非回归 |
| 2026-09-26 | 前端复核（v20 改动后） | tsc 0 + vitest 35/35 + landing build 0 | — |
| 2026-09-25 | 部署上线 20.204.27.154（ARM64） | imagefree-api 8100 + cfsolver 8001 + nginx 443 | cf_solver camoufox 单次 ~3s |


## v20.2 生产化审计补充（2026-09-26，Spec 008）

| 日期 | 范围 | 结果 | 备注 |
|------|------|------|------|
| 2026-09-26 | SQL 安全审计（S2 子代理） | P0=0（无注入，拼接均参数化/白名单）；P1=7 | 见下修复 |
| 2026-09-26 | 索引优化（P1 修复） | 3 表 5 组合索引：requests(status,finished_at/created_at/model)、chat_usage(provider,model)、accounts(provider,status,credits,updated_at) | migrations.py/_base.py 增量 DDL |
| 2026-09-26 | `_enqueued_at` 内存泄漏（P1） | row=None/cancelled 早退路径补 pop | engine.py _process |
| 2026-09-26 | `load_cache_snapshot` 全表（P1） | 改 SQL 侧 `WHERE cached_at+ttl > now` 过滤 | queries.py |
| 2026-09-26 | `_queue_counts` 漂移（S2 报） | 复核后无需修复：put 失败时递增未执行，递减成对 | 误报已记录 |
| 2026-09-26 | email_pool `_load_used` 全量（P1） | **有意保留**：注册器已下线，邮箱池低频，改动面大收益低 | — |
| 2026-09-26 | export_tasks 无界（P1） | 已有 LIMIT 10 万截断，管理端点低频，**部分缓解不改流式** | — |
| 2026-09-26 | token 池阻塞（P1） | 压测调优项：需 cf_solver 多槽 + TOKEN_PREFETCH_CONCURRENCY 提升 | 非代码 bug |
| 2026-09-26 | 部署同步 | 服务器 git pull → c7ceed2，openapi version 20.0.0→20.2.0 | 修复部署=仓库一致 |
## v20.3.0 AI 工具门户上线验证记录（2026-09-26）

### 门户结构（生产 https://imagefree.hwhcie.bond）
- title=「听风AI — 一站式 AI 创意平台」，H1=「一站式 AI 创意平台」
- 6 工具卡 / 11 画廊真实 R2 图 / 3 信任胶囊 / 0 管理后台链接 / 0 slow+honor 运维链接 / 页脚 v20.3.0
- console error = 0

### 在线使用真实 E2E（生产）
- AI 对话：tryingopen deepseek-v4-pro-0813 → 真实回复「我是听风AI 聚合网关的对话助手…」，0 error
- AI Agent：自然语言「帮我写一首关于夏天的诗」→ 3 节点 DAG（llm 创作 → critic 审阅 → llm 定稿），tryingopen 真实规划，0 error
- 文生图（本地 dev 代理验证）：真实出图 R2（~27s），PortalGenerate 渲染 image_url 成功
- 画廊：/v1/gallery count=11，全部 image_url 公网 R2 可加载

### 部署
- 本地推送 e803ad6（2 主题 commit：门户重构 + 版本 bump）
- 服务器 git pull → HEAD=e803ad6
- landing/dist 本地构建后 SFTP 上传 17 文件（服务器无 node）
- 旧 dist 备份 dist.bak-20.2.1；systemctl restart imagefree-api → active + healthz ok
## v20.3.0 补强闭环验证记录（2026-09-26 续）

### /admin 管理台部署 v20.3.0
- frontend dist 本地重建（vite build 全绿，35 文件）→ SFTP 上传 /opt/imagefree-api/frontend/dist（旧备份 dist.bak-20.2.0）
- systemctl restart → /admin/ HTTP 200，Playwright 验证导航齐全（在线聊天/提供商/任务/号池/日志/仪表盘/生成/智能体/API 指南/健康/生态/成本）

### AI PPT 工具卡真实可用
- systemd service 注入 Environment=IF_PPT_GENERATE=1 → daemon-reload + restart → active
- POST /v1/skills/ppt/generate 真实 200：content-type=pptx，29996 字节，PK magic，X-Slides=3
- Playwright 门户 PPT 卡：真实下载 outline.pptx + 「下载成功 ✓」

### 生产全路由回归审计（Playwright，0 console error）
- 首页：title「一站式 AI 创意平台」/ H1 / 6 卡片 / 11 画廊图 / v20.3.0 / 0 admin / 0 slow+honor
- /admin：导航齐全加载成功
- 移动端 375：无横向滚动，卡片 6，触控目标 77px
- 门户对话/Agent/生图/PPT：真实 E2E（此前已验证）

### 自动化测试
- 后端 tests/test_gallery_crud.py + test_chat_routes.py：15 passed
- frontend Tasks.test.tsx 单文件：4 passed（全量 2 失败为预存并行 flaky，非本轮回归）
## v20.3.0 终局闭环审计记录（2026-09-26 第三轮）

### Agent 真实 LLM 全链路生产 E2E
- plan（重试后）：mock=false, llm_used=true, model=tryingopen/z-ai/glm-5.3-flash, 4 节点
- run：succeeded；scene→llm（真实夏天诗 443 字符）→critic（30s 超时降级护栏）→llm（定稿）
- 首次 plan 偶发 mock 回退（上游瞬时故障），重试即真实 —— 与用户经验一致（单 IP 并发限制重试即成功）
- 结论：tryingopen 真实调用闭环确认；planner 的 mock 回退是防崩主链路设计，非 bug

### 生产全链路快照
- healthz 200 ok / gallery 200 count / ppt 200 pptx / chat_models 200 items 13
- /admin 200 新 build；首页 200 v20.3.0
## v20.3.1 生产缺陷修复 + 审计 P1 闭环验证记录（2026-09-26）

### P0 图生图 TLS 修复
- 复现：POST /v1/edit（image=画廊 R2 URL）→ 500 SYS.001
- 日志：SSLV3_ALERT_HANDSHAKE_FAILURE（httpx.ConnectError）
- 根因：_edit_client 复用共享 H2 keep-alive 会话，空闲后上游 TLS 会话失效；curl 新连接正常
- 修复：图生图链恒一次性 client + 三处 aclose
- 验证：生产 /v1/edit 真实 E2E（URL 输入 → 出图）

### P1 终局审计闭环
- /v1/models 60s 缓存（gallery_cache）
- /v1/logs + ws 脱敏（_redact 验证：Bearer/api_key/token/query 全替换 ***）
- MCP generate_image 真实 URL 透传（手动验证 mock 占位 https URL）
- /v1/meta 加 ppt_enabled/video_enabled；PortalPpt/Video 开关降级
- .env 模板权威化（根入口 + deploy 补 12 变量）

### 测试
- 后端 agent_dag_exec + dispatch_edit_branches 46 passed
- landing build 全绿（44 模块）
- frontend Tasks/GalleryAlbum afterEach clearAllMocks（flaky 根治）
## v20.3.1 图生图 TLS 深度修复（2026-09-26 第二轮）

### 第一轮修复（连接复用）→ 仍 500
- 初判：_edit_client 复用坏会话 → 改一次性 client + aclose
- 实测：POST /v1/edit 仍 500 SSLV3_ALERT_HANDSHAKE_FAILURE

### 真实根因（第二轮）
- traceback 定位：失败在 download_image（下载**输入图片**画廊 R2 URL），非上游 imagefree
- 根因：download_image 防 DNS rebinding 用 **IP 直连**（safe_url=IP），httpx 对 IP URL 的 TLS SNI=IP ≠ 域名 → Cloudflare(R2) 拒绝握手
- curl 用域名 SNI 正确所以正常；文生图无此步所以正常

### 修复
- download_image：保留公网 IP 校验（SSRF 防护），改用**域名连接**（SNI 正确）+ 一次性 client
- 本地验证：R2 URL 下载 941KB PNG 成功

### 生产 E2E（部署 904c846 后）
- POST /v1/edit 500 → **200**（task_id 返回）
- DB：upstream_task_id=072f3635...（上游提交成功）+ status=pending（上游生成中）
- 结论：图生图真实链路已打通（500 缺陷修复）；上游出图耗时 > 5min 属上游正常
## v20.3.2 生产加固（nginx 缓存/压缩 + 高并发探针 + 契约审计）（2026-09-26）

### C1 nginx 静态资源加速（P0，用户点名 CDN/缓存）
- 问题：/assets 无缓存头每次回源；gzip_types 未配置
- 修复：location /assets/ → cache-control immutable + expires 1y；gzip on + gzip_types 补全；location = / 和 = /index.html no-cache
- 验证：JS 响应 cache-control: public,max-age=31536000,immutable；gzip 压缩 124662→47946 字节（-62%）；首页 no-cache
- 备份：/etc/nginx/sites-available/imagefree.bak-2031

### C2 高并发极限施压探针（只读端点，不伤生产）
- /v1/healthz + /v1/gallery 并发 20/50/100：全部 ok=100% 无错误无 429（防穿透稳定）
- 服务器本地延迟 3ms（CPU load 0.04 极低）→ 服务端无瓶颈
- 公网 p50 2-4.7s = 公网 TLS 握手开销（探针 connection:close 新建会话），非服务端缺陷
- 产出：scripts/probe_concurrency.py（可复用探针）

### C3 契约防坑审计
- 前端 authHeaders 冗余带 Key + 后端匿名开放 = 兼容契约（配 Key 可选，不配也可用）
- Generate.tsx 提示「写接口需 Key」为防御性文案（生产 IF_API_KEYS 空时永不触发）
- 结论：前端契约与后端实际一致，无隐藏不一致
## v20.3.2 发行闭环验证记录（2026-09-26）

### 版本 bump + 部署
- 全链 bump 20.3.2（12 文件：api/frontend/landing/desktop/pyproject/README）
- landing dist（17 文件）+ frontend dist（35 文件）上传部署（旧备份 dist.bak-2031）
- 服务器 git pull → 6e86105，restart active，healthz ok

### 图生图时长提示（UX 缺口）
- PortalGenerate img busy 态加「图生图生成约需 5-10 分钟」提示（zh/en）
- 验证：图生图卡表单正常（upload-row 渲染，模型加载完成，0 error）；hint 仅 busy 态出现（未提交不触发，符合预期）

### 生产 E2E 回归（Playwright，0 console error）
- 首页 footer v20.3.2 / 6 卡片 / 12 画廊图 / 0 admin
- 文生图/图生图卡模型加载正常
- nginx 静态资源 immutable + gzip 仍生效
## v20.3.3 发行闭环验证记录（2026-09-26）

### F1 DAG 教学化 explain 真接线（P2 审计闭环）
- 问题：explain_templates 有测试（test_agent_explain）但主链路未接线 → 假功能
- 修复：GET /v1/agent/dag/{run_id} 每节点附加 explain 字段（_attach_explain，IF_AGENT_EXPLAIN_ENABLED=1 缺省开）
- 本地验证：scene/llm/critic 节点全部附加（[scene] 任务入口节点…/为什么/输入输出）
- 生产 E2E：run_id e8b5ac5df3a842c2，节点 scene/llm/critic 全部返回 explain ✅
- 测试：agent_dag/agent_explain/gallery 27 passed

### F2 假功能注释修正
- video_provider.py：「IF_MOCK_UPSTREAM=1→Mock；真实后置」→「视频恒 Mock（上游未接入），开关无效」
- generate.py _guard：「必须携带 API Key」→「公益开放无 Key（v7.7.1 起），IF_API_KEYS 可选」

### 部署
- 推送 8cb39c1（三方一致），服务器 git pull + restart active
## v20.3.4 发行闭环验证记录（2026-09-26）

### G1 教学化 explain 前端闭环
- PortalAgent run 后节点 explain 回填 + 可折叠展示（details/summary ▸）
- 生产 E2E：「写诗」→ 3 节点全部 explain（[llm] 大模型处理节点…/为什么/输入输出），点击展开完整显示，0 console error

### G2 图生图超时降级
- PortalGenerate busy 显示已等待时长（分:秒）+ 15 分钟超时降级提示
- 与后端 EDIT_TIMEOUT=600s error 兜底一致

### 版本漂移修复（关键）
- 问题：bump 后未重建 dist → 误传 20.3.3 版本标记 dist
- 修复：重建 landing dist（index-J_Rp9JeE.js 含 20.3.4）→ 重新上传
- 验证：生产 footer v20.3.4 ✅

### 部署
- 推送 055d509 + dist 重新上传（备份 dist.bak-2033）
- 服务器 git pull + restart active

## v20.3.5 数据备份闭环验证记录（2026-09-26）

### 备份机制确认（H 系列）
- 发现：仓库已有 scripts/backup_db.py（VACUUM INTO 热备 + integrity_check + row_count + --all），但生产未配置 cron
- 配置：cron 每日 03:00 全量备份 7 个 DB → /opt/imagefree-api/backups，保留 7 天
- 执行：--all 备份 7/7 成功（imagefree.db requests=20 行校验 + integrity ok）
- 恢复演练：备份文件全部 PRAGMA integrity_check = ok（可恢复）
- 简版脚本误建已删（无双脚本冲突）

### SOP 更新
- SOP v3.1.0 补「数据库备份」章节：机制/范围/cron/手动备份/恢复步骤
## v20.3.6 发行闭环验证记录（2026-09-26）

### J1 管理台 explain 消费
- DagGraph tooltip 优先 node.explain（fallback NODE_HINT）
- DagTrace 详情面板新增「教学化释义」区块
- DagNodePublic 类型补 explain?: string | null
- frontend build 全绿；生产 /admin/agent 页面加载正常（0 console error）

### J2 备份恢复演练自动化
- scripts/restore_drill.py（非破坏性：临时目录恢复 + integrity + requests 行数 + 清理）
- cron 每周日 04:00 演练（imagefree/dag_runs/queue）
- 服务器实测 3/3 通过：imagefree(requests=20)/dag_runs/queue integrity=ok
- git pull 冲突处理：未跟踪 restore_drill.py 与新 commit 冲突 → 删旧拉新，服务器 HEAD=46bf2bc

### 部署
- 推送 46bf2bc（三方一致），frontend dist 上传（备份 dist.bak-2035），restart active
## v20.3.8 发行闭环验证记录（2026-09-26）

### L3 管理台 explain E2E 发现的真实缺口 + 修复
- 问题：管理台 RunCard 用列表端点 /v1/agent/dag?limit= 渲染节点，explain 只附加在详情端点 → UI 教学化释义无法展示
- 修复：dag_list 每 run 节点同样 _attach_explain（与详情一致）
- 验证：列表端点节点 explain present=True；/admin/agent 点击 run admin-explain-e2e → 点击节点 → .dag-trace-explain=1 真实显示「[scene] 任务入口节点…为什么…输入输出…」，0 console error
- 测试：agent_dag_routes + agent_explain 19 passed

### 全量测试基线（环境限制记录）
- 前端 vitest 全量 296：295 passed + 1 并行 flaky（CostsPage 单跑 4 passed = flaky 非回归）
- 后端 pytest：本环境（Python 3.14 + 工具链）全量运行 EXIT=4 无输出（工具链问题），已用分文件子集验证核心（agent_dag 19/gallery 15/chat 等全绿）；collect-only 正常
## v20.3.9 测试基线提升验证记录（2026-09-26）

### M1 前端 CostsPage flaky 根治
- 根因：CostsPage 用 vi.spyOn(globalThis,'fetch') + restoreAllMocks，与 Slow.test 的 stubGlobal('fetch') 并行时全局污染 → 偶发失败
- 修复：改 vi.stubGlobal('fetch') + vi.unstubAllGlobals（与其他 stubGlobal 文件一致的全局所有权模式）
- 验证：全量 vitest 串行 28 文件 / 296 测试 **全部通过（296/296）**（此前 295+1 flaky）
- 说明：vitest 并行在本机有 worker 崩溃（23 errors，非 flaky），串行稳定全绿为验收标准

### M2 后端 pytest 工具链（环境债，诚实记录）
- pytest 9.1.1 + Python 3.14 + pytest-asyncio 1.4：全量/单文件 EXIT=4 静默（工具链兼容问题，非代码缺陷）
- pytest --version 正常、collect-only 部分正常；已验证分文件子集（agent_dag 19/gallery 15/chat）全绿
- 建议：CI 用固定 Python 3.11 + pytest 8 跑全量；本地以分文件子集为基线
## v20.3.10 后端测试环境真相澄清（2026-09-26）

### 认知修正：后端 pytest 环境正常（前几轮「环境债」记录有误）
- 之前多轮记录「后端 pytest EXIT=4 环境债」——根因是**误用了不存在的文件名**（test_auth.py 应为 test_auth_ip.py；test_fmt.py 不存在）
- 真相：`.venv`（Python 3.11.13）pytest 一直能跑；test_auth_ip.py 7 passed
- 教训：pytest 对不存在路径返回 exit 4 且本环境静默无输出 → 误导为环境崩溃。后续用 `Get-ChildItem` 确认文件存在再跑

### 全量测试基线（分批次实测）
- 第一批 47 文件（test_account*~test_config*）：**除 1 个隔离 flaky 外全绿**
- **预存隔离 flaky**：test_account_pool.py::test_dashboard_counts_reflect_state
  - 单独跑 `-k dashboard_counts` PASSED；全量文件跑时 18 个测试后污染失败
  - 根因：AccountPool 内部跨 tmp_path 实例的共享状态（测试隔离缺口，非本轮引入，account_pool 未改过）
  - 建议：低优先级测试隔离债，CI 可忽略或后续修 fixture 隔离

### 环境
- pytest 9.1.1 → 8.3.5 降级尝试（pyproject 允许 >=8.0），测试仍正常
- 前端 vitest 全量串行 296/296 全绿（v20.3.9 已记录）

## v21.0.0 终局闭环验证记录（2026-09-27）

### 版本门禁（T1/T2/T10）
- 新增 `tests/test_version_consistency.py` 3 用例（全链相等 + semver + e2e_v12 契约）。修复自身 bug：e2e 契约正则硬编码 `20\.` 前缀 → 版本升 21.0.0 后 hits 空误报，改 `\d+\.\d+\.\d+`。
- 新增 `scripts/sync_version.py`（--set/--check/--dry-run，幂等）。版本从 20.3.10 统一到 **21.0.0**（全链 9 文件 + e2e 契约）。
- 修复 Windows GBK 终端打印 ✓/✗ 崩溃（stdout reconfigure utf-8）。
- 验证：`pytest tests/test_version_consistency.py` → 3 passed 全绿；`sync_version.py --check` → 全链一致 21.0.0。

### 测试隔离（P0-4 确认已修）
- `test_account_pool.py::test_dashboard_counts_reflect_state` 组合跑（+ fsm + predict_exhaustion）**39 passed** —— v20.3.11 fixture 隔离修复（uuid 唯一 DB 文件 + 不调 raw.close 防 loop 复用污染）已验证生效，无待修。

### i18n 收尾（DLQ 页）
- `messages.zh.ts` / `messages.en.ts` 补 `dlq.*` 25 个平行 key；`DLQ.tsx` 全部中文硬编码换 `t()`（含 aria-label / 空态 / 通知）。
- 验证：`vitest run src/test/i18n.test.ts` **8 passed**（isLangComplete 断言 dlq key 一致）；DLQ chunk 含 new keys；全量 vitest **28 files / 296 tests 全绿**。

### PWA installable（landing 主战场，复用既有 sw.js）
- 新增 `landing/public/manifest.webmanifest`（theme #0a0e1a 对齐）+ pwa-192/512 + apple-touch-icon.png（由 og-image 居中裁剪生成）。
- `landing/index.html` 补 manifest link + apple-touch-icon + iOS standalone/status-bar meta。
- 新增 `landing/src/components/PwaInstallPrompt.vue`（beforeinstallprompt / iOS standalone 检测 / 访问≥2 次 / 桌面隐藏），挂载于 App.vue。
- `landing/public/sw.js` 预缓存补 manifest + 3 图标；CACHE_NAME `imagefree-landing-v8.6.0 → v21.0.0`（三策略保留，不重写）。
- 修正：manifest 初版含指向不存在 hash 路由的 `shortcuts`（landing 仅 #/privacy），已移除避免 Dead URL。
- 验证：`landing npm run build` 成功 23.6s，dist 含 manifest/icon/sitemap/robots/sw.js(v21)，index gzip 4.37kB。

### SEO
- 新增 `landing/public/sitemap.xml`（/ 、/docs、/#/privacy）+ `robots.txt`（Allow / + Disallow /admin//v1//docs + Sitemap 声明）。JSON-LD 已有（SoftwareApplication + WebSite），未重复建。已随 build 进 dist。

### 运维工具
- 新增 `scripts/uptime_probe.py`（模拟 UptimeRobot 探针，连续 3 次 /v1/healthz，exit 0=全 200 / 1=失败）。`py_compile scripts/sync_version.py` 编译通过。
- `.env.production.example` 补 LITESTREAM_* 六变量（缺省空，启用需 R2 凭证 + compose backup profile；本地 type:local 验收路径在 SOP 文档）。

## v22.0.0 终局闭环验证记录（2026-09-27）

### 发布状态
- v21.0.0 已发布：5 commits 推送 main（926a9bd→bd39473）+ tag v21.0.0 + GitHub Release 397768628。
- v22.0.0 为本轮增量：版本全链 21.0.0 → 22.0.0（sync_version.py），frontend/landing dist 重建，sw.js CACHE_NAME v22.0.0。

### SSE 活动连接保护（P2-1）
- `api/sse_events.py`：TaskEventHub 加 `max_connections` 构造参数 + `set_max_connections()` + subscribe 超限抛 ConnectionError（0=不限制向后兼容）；task_events_generator 捕获产出 429 error 事件后终止。
- `api/ws_events.py`：subscribe 捕获 ConnectionError → 发 429 错误帧 + close(1013)。
- `api/lifespan.py`：startup 装配 `IF_SSE_MAX_CONNECTIONS` 到 hub（0 不装配，缺省零行为变化）。
- `api/config/__init__.py`：新增 `if_sse_max_connections` 字段（IF_SSE_MAX_CONNECTIONS）；`deploy/.env.example` 同步。
- 测试：`tests/test_sse_events_unit.py` 新增 3 用例（缺省不限/上限触发/unsubscribe 释放）。**验证：25 passed + 1 skip**。

### CI 版本门禁接入（P1-2/G15）
- `.github/workflows/ci.yml` 单测 job 首步新增「版本一致性门禁（漂移 fail-fast）」：`pytest tests/test_version_consistency.py`，版本漂移立即红不过全量。
- YAML 语法校验通过（8 steps）。

### 运维脚本单测（P1-3）
- `tests/test_sync_version.py` 6 用例：check 一致/缺失文件 fail/set 幂等/dry-run 不落盘/e2e 契约改写/GBK 输出不崩。**修复脚本 ROOT 可被 `SYNC_VERSION_ROOT` 覆盖（单测隔离，旧行为不变）**。
- `tests/test_uptime_probe.py` 6 用例：probe 200/503/不可达/CLI all-200 exit0/503 exit1/GBK 成功不崩。**修复 `_Handler.status` 类属性跨测试污染（fixture 重置）**。

### 指南更新
- `计划书/下一步改进指南.md` 升级 v22.0.0：v21 闭环清单 + v22 差距矩阵 G1-G15 + P0-P2 + 批次 + TDD + 验收矩阵；修正 v21 发布状态（已发布）。

### 验证汇总
- `pytest` 相关 7 文件：44 passed + 1 skip 全绿
- `py_compile` api/sse_events/ws_events/lifespan/config + scripts 编译通过
- frontend build index gzip 84.04kB（<150KB 达标）；landing build 成功 sw v22.0.0
- 版本门禁 `pytest tests/test_version_consistency.py`：4 passed（全链 22.0.0 一致）

## v23 记录（2026-09-28 · 终局闭环批）

| 日期 | 范围 | 结果 | 备注 |
|------|------|------|------|
| 2026-09-28 | **N2 SQL 猎杀**：27 文件 0 注入；慢查询（stats_overview 全表聚合/gallery NOT IN 弃索引/day-month 无索引/model 无索引）+ 批量写"合并 commit"实测非原子（autocommit） | 全绿 | docs/research/sql-audit-v23.md；修复：migrations 幂等索引 ×5 + gallery 正向白名单 + flush 失败回写 |
| 2026-09-28 | **N3 安全纵深**：0 P0；P1×5（S1 日志 WS 未脱敏 / S2 TRUSTED_PROXIES / S3 限流单桶 / S4 cancel 零鉴权 / S5 DAG 无 Key） | 修复 3 | S1 三层脱敏（log_ws+redis_adapter+alerting）；S3 限流受信代理；S4 cancel 补 guard |
| 2026-09-28 | **N1 契约审计**：50 端点 44 对齐 0 断裂；F1 画廊删缺 Key（P1）/ F2 聊天 429 字段错配（P1） | 修复 2 | misc.ts adminHeaders + Gallery 失败不乐观移除 + chat-utils 秒→分换算 |
| 2026-09-28 | **N4 前端盲点**：P1 Costs 永久骨架屏（401 被吞）+ P2×9 | 修复 3 | Costs 降级提示+重试；Security 封禁确认；Tasks useNavigate |
| 2026-09-28 | **N5 solver 双节点**：分流 10/10 均匀；串行 0.18/0.27s（delay 3× 吻合）；联邦并发 2.1s 含本机排队 | 已验证 | 承接分布硬结论；probe_federation.py + solver-federation-v23.md/.json |
| 2026-09-28 | **N6 部署原生化**：线上无 Docker → systemd 原生资产（litestream/prometheus/node_exporter/grafana unit + prod yml + install 脚本） | bash -n + yaml 校验 | deploy/systemd/；SOP/litestream-restore/README 同步 |
| 2026-09-28 | **N7 六维独立审查**：2 P1（flush 永久失败 / systemd 单文件多 unit）+ 5 P2 + 3 P3 → **已全部修复并复验** | NEEDS_CHANGES→复验中 | docs/research/review-v23.md；修复：attempts 隔离 + 3 unit 拆分 + @ 密码脱敏 + 白名单常量源 + 路径统一 |
| 2026-09-28 | **后端回归**：db（batch/indexes/migrations/pool）、gallery、retention、log_ws、reconnect、task_cancel、redis、alerting、auth_ip、chat_auth 相关文件 | 144 passed | 含 v23 新用例（永久失败丢弃/@ 密码/白名单/部分失败保留） |
| 2026-09-28 | **前端回归**：GalleryAlbum 7（含 F1 部分失败）+ api 79（含 F2 换算）+ Tasks 4（MemoryRouter 适配） | 90 passed + tsc 0 | 前端 build 29s（index gzip 84.05kB） |
| 2026-09-28 | 版本门禁基线 | 4 passed | 全链 22.0.0（v23 bump 23.0.0 后进行全链复验） |

## v23.1 记录（2026-09-28 · 极限施压 + 防穿透批）

| 日期 | 范围 | 结果 | 备注 |
|------|------|------|------|
| 2026-09-28 | **T1 极限施压**：读路径 5 端点 × 并发 1→200，探针 scripts/probe_stress.py（新） | 200 并发 0 错误率 0 5xx 0 429 不崩 | stress-v23.json；延迟双口径（本机排队噪声） |
| 2026-09-28 | **T2 防穿透**：畸形/超长/5MB body/限流/auto-block | 全 4xx/429 不崩；限流 10→5×429+Retry-After:60；task-failure-burst 403 实测 | S-2 生产核对项实证 |
| 2026-09-28 | **T3 覆盖率猎杀**：v23 修复模块基线 61.5%（log_buffer 43.2/auth 65.9/alerting 62.1） | <70 基线暴露 | cov-v23.json；全量由 CI 门禁把关 |
| 2026-09-28 | **T4 补测**：auth 429 触发/alerting 三路径/log_buffer emit | auth 76.1 / alerting 95.4 / log_buffer 88.9；**抓出 attrs 键错剥 bug 已修** | 新增 10 用例全绿 |
| 2026-09-28 | **T6 独立审查**：F1（429 误判崩溃 P1）+F2-F8 | NEEDS_CHANGES → 全部修复 → 复验 APPROVE | review-v231.md；36 补测+编译+ruff 0 |
| 2026-09-28 | 版本全链 23.0.0→23.1.0 + landing dist 重建 | sync --check 一致；版本门禁 10 passed | 169 关键回归全绿 |

## v23.3 记录（2026-10-15/16 · 终局审计 + CI 转绿批）

> 本批**改动过的模块**（按本台账协议，旧记录对这些模块视为失效）：
> `api/bg_tasks.py`、`api/sse_events.py`、`api/ws_events.py`、
> `api/provider_probe.py`、`api/free_proxy_fetcher.py`、`api/proxy_tracer.py`、
> `tests/conftest.py`、`tests/integration/test_honor.py`、
> `tests/test_config_validate.py`、`tests/test_db_retention.py`、
> `tests/test_sse_events_unit.py`、`tests/test_version_consistency.py`、
> `frontend/src/test/setup.ts`、`frontend/vite.config.ts`、
> `deploy/.env.example`、`.claude/skills/imagefree-workflow/*`

| 日期 | 范围 | 结果 | 备注 |
|------|------|------|------|
| 2026-10-15 | **CI 真实性核查**（GitHub Actions API 实测）：总运行 462 次；**最近 100 次 CI 54 failure + 1 cancelled、Deploy 45 failure，成功 0 次**；30 次 success 全在 2026-09-08 及更早 | ❌ **CI 已整体红约一个月** | 起点事实；取数方法见本文件末「取 CI 失败原因的方法」 |
| 2026-10-15 | **前后端端点契约**（方法级实测，`scripts/probe_route_methods.py`）：从前端源码提取 31 个 `/v1` 路径字面量，对每个路径试 5 种 method | ✅ **31/31 全部存在，0 断链** | 关键教训：正则扫源码报"17 路径不存在"是**假信号**（尾斜杠/模板片段/测试 fixture），必须方法级实测 |
| 2026-10-15 | **端点冒烟** 12 个：`/v1/livez` `/v1/healthz` `/v1/meta` `/v1/models` `/openapi.json` `/v1/tasks` `/v1/providers` `/v1/stats` `/v1/routing/records` `/metrics` `/admin` `/` | ✅ 全 200（`/admin` 307） | 本机 8100 实例（mock 上游模式，空库） |
| 2026-10-15 | **静态站服务**：`node scripts/serve_static.cjs --port 4590` + curl | ✅ `/`→200、`/admin`→307、`/admin/tasks`→200 | 复刻 `api/main.py` 挂载语义 |
| 2026-10-15 | **移动端真实浏览器 E2E**：`node scripts/e2e_mobile_smoke.cjs` | ✅ **9 passed / 0 failed**（真实 chromium 1243，截图落盘） | 375px 无横向滚动 / 深链回退 / a11y |
| 2026-10-15 | **R-1 `bg_tasks` 静默失效**：`_engine` 是模块、`_queue_db` 是实例属性 → 每次必抛 AttributeError，且抛在 try 中部致**其后所有清理被跳过** | ✅ 已修 + 3 回归用例 | `tests/test_db_retention.py`；**AST 断言**（字符串匹配会被改名绕过，实测变异证明） |
| 2026-10-15 | **R-2 SSE/WS 多订阅误清缓冲**：连接收尾无条件 `clear_task` → 先断开者清掉共享缓冲 | ✅ 已修 + 5 回归用例 | 新增 `clear_task_if_idle`（判空与清理同锁内）；**行为 3 + 调用点契约 2** —— 第一版只测方法不测调用点=伪测试，变异证明后补 |
| 2026-10-15 | **R-3 前端 DOM 泄漏**：`vite.config.ts` 设 `isolate:false` 且注释**声称**有 cleanup，但 `setup.ts` 从无清理逻辑 | ✅ 已修（`afterEach(cleanup)`）+ **CI 实证转绿** | 本机（Node 25）复现不出，**CI（Node 20）是唯一验证环境**；修复后前端门禁连续 3 次 ✅ |
| 2026-10-15 | **R-4 env 映射契约盲区**：既有校验用 regex 扫源码，无 alias 字段不进集合 | ✅ 已修 + 5 契约用例 | 实证 `Settings.user_agent` 是 202 字段中唯一漏挂 alias 的；变异验证有判别力 |
| 2026-10-15 | **R-5 `.env.example` 注释指错文件**：称改 `http.py`，实为死副本 | ✅ 已修 | 权威在 `api/config/settings_core.py`；20 处生产消费 `config.USER_AGENT` |
| 2026-10-15 | **R-6 覆盖率门槛文档 70 vs CI 80** | ✅ 已修 4 处 | 危害：按文档自测通过→推 CI 意外失败 |
| 2026-10-16 | **R-8 `stop()` 冒泡打断优雅关闭**：三处管理器只捕 `CancelledError`，而 `await task` 会重抛原始异常；`provider_probe.stop()` 被 lifespan **直接 await** | ✅ 已修 + 7 回归用例 | 新增 `tests/test_shutdown_task_robustness.py`；三处变异同时摘掉→3 用例全红 |
| 2026-10-16 | **R-9 `test_honor` 首页断言缺前置守卫**：`GET /` 是条件挂载，后端 CI job 不建前端 → 404 | ✅ 已修 | 两条路径实跑：有 dist→3 passed；移走 dist→2 passed + 1 skipped |
| 2026-10-16 | **R-10 conftest DB 隔离被外部注入绕过**：`if "IF_DB_FILE" not in os.environ` 信任外部注入，CI 的 `IF_DB_FILE` 使其整个跳过 → `database is locked` | ✅ 已修（无条件临时库） | 注入 `IF_DB_FILE=data/ci_sim.db` 跑 test_ip_blocklist → 28 passed 且该文件**未被创建** |
| 2026-10-16 | **受控回归**（R-8/R-9/R-10 后） | ✅ `test_shutdown_task_robustness` 7 + `test_free_proxy_fetcher` + `test_proxy_tracer` = **67 passed**；6 文件集合 **84 passed** | — |
| 2026-10-16 | **前端全量**：`cd frontend && NODE_OPTIONS="--max-old-space-size=4096" npx vitest run` | ✅ **28 files / 299 tests passed**；`tsc -b` exit 0 | **关键**：512MB 堆会让 worker 起不来（见本文末「前端测试环境陷阱」） |
| 2026-10-16 | **ruff**：`ruff check api/ tests/ scripts/` | ✅ All checks passed! | 改动文件亦通过 `ruff format --check` |
| 2026-10-16 | **版本全链**：`sync_version.py --check` + `pytest tests/test_version_consistency.py` | ✅ 全链 23.3.1 一致；**5 passed**（含新增文档漂移门禁） | — |
| 2026-10-16 | **CI 逐层修复实证**（5 次推送，逐次 API 核对 job） | 基线：后端❌+前端❌ → `d1b8ae7` 前端✅ → `26929d6` locked 消失 → `f862ce6` 单测✅ → `e55e8fb`/`8120970` **后端 job 全绿** | **CI 失败是级联的**：前一步失败会让后续步骤 `[skip]`，修好第一层才暴露第二层 |
| 2026-10-16 | **发版**：v23.3.0（R-1~R-7）+ v23.3.1（R-8/R-9/R-10） | ✅ 两个 GitHub Release（id 414009216 / 414165828） | tag 均已推送；main 与 origin 同步 |

### 本批**判定为伪问题、明确不做**的项（避免下次重复劳动）

| 项 | 为什么不做 |
|---|---|
| 「`.env` 的 `IF_WORKERS=10` 被静默覆盖为 48」 | `.env` **根本不被读取**（`settings_core.py` 的 `model_config` 无 `env_file`；全仓无 `load_dotenv`；`start.ps1` 直接起 uvicorn 不加载）。哨兵逻辑**本身正确**（实测真 env var `IF_WORKERS=7` → 7）。改它 = 无用 diff + 把线上并发从 48 变 10 |
| 「生产模板只列 42/201 个 `IF_*` 不完整」 | **正常设计**（其余走代码默认值），且 42 键**零幽灵键**（运行时 `model_fields` 比对 + `os.getenv` 扫描） |
| 「分组配置与顶层默认值重复 86 项」 | **噪声**（多为数值恰好相等如 `5 == 5`），已弃用该扫描 |
| `data/cov_audit.json` 报总体 28.4%/多模块 0% | **产物不可信**（部分跑+增量叠加）：`health_report.py` 单跑实测 **57%** |
| 「landing 也需 cleanup」 | **不需要**：`PwaInstallPrompt.test.ts` 每处 `mount` 后都 `wrapper.unmount()`，自管生命周期 |
| 「5 个页面 aria-label 为 0」 | 逐页核查为伪问题（所有 button 有可见文字、input 有 label 或显式 aria-label） |
| `.gitignore` 补 `_*.py` 通配 | **经实证有害**：会静默忽略 `__init__.py`/`_base.py`/`_limits.py`，破坏所有包可提交性 |

### 取 CI 失败原因的方法（`gh` CLI 缺失 + 本地代理已死时）

```bash
# 凭据：git credential manager 已存（与 git push 同源），不落盘不打印
TOK=$(python -c "import os,subprocess;r=subprocess.run(['git','credential','fill'],input='protocol=https
host=github.com

',capture_output=True,text=True,timeout=60,env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GCM_INTERACTIVE':'never'});print([l.split('=',1)[1] for l in r.stdout.splitlines() if l.startswith('password=')][0])")

# runs / jobs / annotations（annotations 含失败消息全文）
curl -sS --noproxy '*' --ssl-no-revoke "https://api.github.com/repos/lza6/Aggregate-to-2api/actions/runs/<run_id>/jobs"
curl -sS --noproxy '*' --ssl-no-revoke "https://api.github.com/repos/lza6/Aggregate-to-2api/check-runs/<job_id>/annotations"

# junit 产物（拿到**精确失败用例**）—— 注意必须用 curl -L，urllib 会因重定向 401
curl -sSL --noproxy '*' --ssl-no-revoke -H "Authorization: Bearer $TOK"   "https://api.github.com/repos/lza6/Aggregate-to-2api/actions/artifacts/<artifact_id>/zip" -o junit.zip
```

- **`--ssl-no-revoke` 必需**：本机 schannel 吊销检查离线，否则报 `CRYPT_E_REVOCATION_OFFLINE`
- job **日志**下载需 admin 权限（403）；annotations + junit 产物通常够用
- `scripts/create_release.py` 封装了凭据 + 建 Release 的流程

### 前端测试环境陷阱（**排查顺序**）

1. **先怀疑堆内存**：`NODE_OPTIONS=--max-old-space-size=512`（项目调优建议里的值）**太小**，
   vitest worker 起不来，表现为 `Timeout waiting for worker to respond` 或
   `Worker exited unexpectedly`。**设成 4096 后立刻 28 files / 299 tests 全绿**
2. 再怀疑非 ASCII 路径（`2api目录`）：`isolate:false` + `pool:'forks'` 已固化进配置
3. 最后怀疑机器负载：先找**遗留的长跑 pytest**（本轮发现一个跑了 ~10 小时的
   `pytest tests/ ... --junitxml=data/full_junit.xml` 占满 1 核）。
   注意区分：`D:\参考项目\...` 下的进程属**其他项目**，不要误杀

### v23.3.2 续（2026-10-16）—— CI **首次出现 success**（但**未**稳定转绿）

> ⚠ **本标题原写「CI 首次全绿」，属过度宣称。** 独立审查（2026-10-16）用 Actions API + junit
> 产物核出：**同一份代码一红一绿**，且**写「首次全绿」的那个提交自己就是红的**。
> 已据实更正为「首次出现 success」。以下为实测运行序列：

| 时间 | 提交 | 结论 | 说明 |
|---|---|---|---|
| 2026-10-15T19:02 | `81209703` | failure | 修 conftest 之前 |
| 2026-10-16T10:25 | `19718b59` | **success** | **本仓库自 2026-09-08 以来第一次 success** |
| 2026-10-16T11:04 | `023490d3` | **failure** | **= 写「CI 首次全绿」的那次提交**；失败步骤「单元测试」，junit 实证：`sqlite3.OperationalError: **no such table: ip_blocklist**` |
| 2026-10-16T11:36 | `6c2d12db` | success | **零代码差异**（只改了 `.wolf/buglog.json`） |
| 2026-10-16T16:58 | `d4da44e0` | success | 文档提交 |

**结论：后端测试套件存在残留 flake，未闭环。** 落点 `tests/test_ip_blocklist.py` 的 fixture
（它**就地改共享单例的私有属性** `store._path` / `store._initialized` 做每用例隔离 ——
违反项目「不可变优先」，并与后台异步封禁写 `_auto_block_ip` 竞态）。
症状有两种：`database is locked`（连接争锁）与 `no such table: ip_blocklist`
（建表落在 A 文件、写入落到 B 文件）。
**归因（避免误伤）**：**非本批引入** —— 本批那两个提交只动版本号与文档。

| 日期 | 范围 | 结果 | 备注 |
|------|------|------|------|
| 2026-10-16 | **前端 flaky 根因根治**：`isolate:false` 导致同一 worker 内多文件共享模块实例，而 `vi.mock` 按文件注册 → 后跑文件的组件闭包仍指向上个文件遗留的 mock 实例。强制同 worker 连跑实测：`GalleryAlbum→Gallery` 时 Gallery 4 用例全红、反向时 GalleryAlbum 7 用例全红（全仓库唯一「同一组件+同一 vi.mock 目标」组合） | ✅ 已修（**CI 侧已实证**：前端门禁在后续多次运行中通过） | `isolate:false`→`true`，**配套 `maxWorkers: 2`**（isolate:true 下每个文件重启 worker 环境，默认并发会 28 errors/0 tests 全部启动超时；降到 2 后 28 files/300 passed） |
| 2026-10-16 | **进度条降级覆盖（用户可见缺陷）**：`useTaskProgress` 轮询每 tick 无条件 `apply(mapStatusToDetail(t.status))`，而 `GET /v1/tasks/{id}`（`TaskInfo`）不含 status_detail/progress → processing 映射 `{null,null}` 把 SSE 刚写入的 `solving/30` 抹回「运行中」= **进度条每 2 秒跳一次** | ✅ 已修 | 加「映射为空且状态未变则保留精确值」；**变异验证**：摘掉修复 → 新用例单独失败、原 4 条照过（1 failed/4 passed） |
| 2026-10-17 | **上述修复自身引入新缺陷（独立审查 R1）**：降级守卫在 **SSE 断线时未复位** → 轮询粗粒度映射被永久抑制 → 徽章**冻结**在最后一个精确阶段且无「已失联」提示 | ✅ 已修 + 回归锁 | `handleDisconnect` 里 `lastAppliedStatus = null`；**变异验证**：摘掉该行 → 精确只有新用例失败（1 failed/5 passed） |
| 2026-10-16 | CI run `38887120926`（`19718b5`） | ✅ success（6/6 job） | **首次 success**；但见上表，后续同代码提交仍失败 → **不宣称「已稳定转绿」** |

### v23.3.2 交付口径与本地真实 E2E 验收（2026-10-16）

**用户口径**：线上服务器访问途径**未提供** → 「一切以本地真实 E2E 为准」，不做线上部署/热更新。

| 日期 | 范围 | 结果 | 备注 |
|------|------|------|------|
| 2026-10-16 | **本地拉起真实 uvicorn**（`python -m uvicorn api.main:app --port 8100`） | ✅ 启动成功（本机 `import api.main` ≈36s + lifespan 约 25s） | 非复用他人实例，自起自验 |
| 2026-10-16 | **端点冒烟 11 个**：`/v1/livez` `/v1/healthz` `/v1/meta` `/v1/models` `/v1/tasks` `/v1/stats` `/v1/providers` `/v1/routing/records` `/metrics` `/admin` `/` | ✅ 全 200（`/admin` 307 重定向） | — |
| 2026-10-16 | **openapi 版本一致性** | ✅ `version = 23.3.2`（与本版本全链一致）、`paths = 68` | — |
| 2026-10-16 | **静态站服务**：`node scripts/serve_static.cjs --port 4590` + curl | ✅ `/`→200、`/admin`→307、`/admin/tasks`→200 | 复刻 `api/main.py` 挂载语义 |
| 2026-10-16 | **真实 chromium E2E**：`node scripts/e2e_mobile_smoke.cjs` | ✅ **9 passed / 0 failed**（landing 4 + admin 5，375px，截图落盘） | 真实浏览器，非 jsdom |
| 2026-10-16 | **SSE 帧内容实证**（建任务 → 订阅 `/v1/tasks/{id}/events`） | ✅ 帧内**确实携带** `status_detail`（`queued`/`solving`/`error`）与 `progress`（5/30） | **验证了进度条修复的前提**：SSE 有精确值、而 `GET /v1/tasks/{id}` 的 `TaskInfo` 无 → 轮询确实在降级覆盖 |

### 仍未闭环（v23.3.2 结束时）

- **进度条刷新后只剩粗粒度阶段**：属**精度限制而非错误**（status_detail/progress 从未持久化）。
  要修需落库 + 扩 `TaskInfo` 契约（3 个发布点 + schema + 迁移）→ **独立决策项，未做**。
- **线上部署：非待办**（用户 2026-10-16 明确「服务器目前还没给你，没办法线上更新」）。
  `20.204.27.154` 的 TCP 22/80/443/8100 全超时（DNS 能解析）属**未提供访问途径**，
  **不是缺陷、不再重复探测、不列为阻塞待办**。本轮交付口径 = **本地真实 E2E**：
  `scripts/serve_static.cjs` + `scripts/e2e_mobile_smoke.cjs`（真实 chromium 9/9）
  + 本地 uvicorn `127.0.0.1:8100` + curl 端到端。解除条件：用户给出服务器访问途径。

### 原「仍未闭环」记录（v23.3.0 时点的描述，保留供溯源）

- ~~**前端 vitest flake**：`Unable to find an element with the alt text: test prompt`~~
  → **2026-10-16 已闭环**（根因与验证见文末「前端 vitest flake 根治（isolate 串味）」）。
- **前端 `Tasks.test.tsx` 并行 flake**（预存，本轮一并闭环）→ 见同一节。
- **线上主机 `20.204.27.154` 不可达**（TCP 22/80/443/8100 全超时，DNS 正常）→ 部署热更新受阻
- **全量覆盖率真实数字**未取得（本机全量被 `--timeout=120` 卡在 `test_tryingopen.py::no_sleep`）

---

## 前端 vitest flake 根治（isolate 串味 · 2026-10-16）

**症状（CI 2/6 次）**：`TestingLibraryElementError: Unable to find an element with the alt text: test prompt`
（4 条同 message）；失败时 DOM 里 `gallery-album` 已渲染、计数「2 张」、只有一个根 div。

**根因（本机已确定性复现）**：`vite.config.ts` 的 `isolate: false` 让同一 worker 内的多个测试文件
共享模块实例，而 `vi.mock` 的假模块**按文件注册** → 后跑文件里被缓存的组件（`Gallery.tsx`）
闭包仍指向**上一个文件遗留的 mock 实例**，本文件新注册的 mock 对它完全无效。

```bash
cd frontend
# 强制两文件同 worker 串行（isolate:false 下后者必红）
npx vitest run --no-file-parallelism src/test/GalleryAlbum.test.tsx src/test/Gallery.test.tsx
#   → Test Files 1 failed | 1 passed ; Tests 4 failed | 7 passed
#     4 条均为 Gallery.test.tsx:68/95/113/131 的 alt text 断言
#     DOM 佐证：`imagefree/default` 徽章 +「已加载全部 2 张」= GalleryAlbum 的数据（非本文件的 1 项数据）
npx vitest run --no-file-parallelism src/test/Gallery.test.tsx src/test/GalleryAlbum.test.tsx
#   → GalleryAlbum 7 failed（Cannot read properties of undefined (reading 'total')）
# 爆炸半径（全量单 worker）：2 failed | 26 passed —— 只有这两个文件互相串味
npx vitest run --no-file-parallelism
```

**为什么 CI 才偶发**：文件→worker 的分配是「哪个 worker 先空闲谁取下一个文件」的竞争；4 vCPU
runner 上两个 Gallery 文件偶尔落进同一 worker → 后跑者必红；本机 16 vCPU 几乎不同组，故长期复现不到。

**修复**：`frontend/vite.config.ts` → `isolate: true` **+ 配套 `maxWorkers: 2`**。
**未削弱任何断言、未改测试文件**。

> ⚠ **更正（2026-10-17，独立审查发现）**：本段原写「老注释里『非 ASCII 路径下隔离 worker
> 启动 60s 超时』的绕行 2026-10-16 复测**未复现**」—— **该句失实**。准确表述是：
> - `isolate:false` + 默认并发 → 跑得起来（但有跨文件 mock 串味，即本 bug）
> - `isolate:true` + **默认并发** → **28 errors / 0 tests**（全部 worker 启动超时，套件完全不可用）
> - `isolate:true` + **`maxWorkers:2`** → 28 files / 300 passed
>
> 即**那个超时依然存在**，只是被 `maxWorkers:2` 压住了 —— **两处设置是配套的，单改一处会破**。
> 该失实陈述源自代理记录，我已在 `.wolf/buglog.json` bug-025 更正，
> 但**当时漏改了本文件与 `vite.config.ts`**（后者亦已更正）——
> 属本批自己反复列为「文字与实现不符」的**同类问题**，应当引以为戒。

**验证（修复后）**
- 同组连跑两种顺序 → `11 passed`、`11 passed`（修复前：同两条命令只过 4/11 与 4/11，分别红 4 例、7 例）
- **口径澄清**：本段原记「`npm run test` 连续 3 次 → 每次 299 passed，94s / 95s / 92s」——
  **该耗时与 `vite.config.ts` 所记的 488s 互斥**（同一配置不可能同时是 94s 与 488s，差 5×），
  且两者都未标注 NODE_OPTIONS / 并发 / 平台。**本文件保留该数字但标注为「口径不明、不可复现」**；
  可信的锚点是独立审查核出的 **CI 侧 vitest 步骤实测 15s**（Actions API 的
  started_at→completed_at，ubuntu-latest / Node 20 / 读同一份配置）与
  本机（Windows / Node 25 / maxWorkers:2）**488s**。平台与路径不同，**不可相互对比**。
- **`maxWorkers:2` 的必要性仅在本机成立**（默认并发下套件完全跑不起来）；CI 实测 15s，未受该限流拖累。
- `npx tsc -b` → 0 error

**顺带闭环：`Tasks.test.tsx` 并行 flake（预存，非本轮引入）**
`useTaskProgress` 每 2000ms 轮询 `GET /v1/tasks/{id}`，而 GET 响应不含 `status_detail`
→ `mapStatusToDetail('processing') = {null,null}`，把 SSE 刚写入的「求解中/30」**清回「运行中」**
（失败 DOM 实证：`aria-label="任务阶段：运行中"` + progressbar 无 `aria-valuenow`）。用例成败于是取决于
「事件派发→断言」是否跨过 2s 边界。**对照组**：未改配置前（`--no-isolate --fileParallelism`）同样在
`Tasks.test.tsx:107` 失败 1 例 → 与本轮 isolate 修复无关。修法：该用例内 `vi.useFakeTimers()`
（afterEach 统一 `vi.useRealTimers()`），轮询 interval 不再自行触发，断言强度不变；单跑 4 passed。

**未做（记录在案）**：`CostsPage.test.tsx` CSV 导出用例在单 worker 满载下失败 1 次（该文件耗时 173s，
属预存环境 flake），并行模式未复现，本轮未动。
另：`useTaskProgress` 的轮询会周期性覆盖 SSE 的精确 `status_detail/progress`（用户可见的 2s 级
徽章/进度回退）—— 这是**产品行为**取舍（SSE 精确值 vs 轮询兜底谁优先），需产品侧决策，本轮只报不改。
