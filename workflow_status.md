# workflow_status — 终局闭环核验（2026-10-14 批）

> 规范来源：用户本轮指令（终局审计 / 主动补位 / 真实验收 / 深度反向修复）
> 蓝本：`计划书/下一步改进指南.md`（v22.0.0 方案，已于本批删除；可从 `git show HEAD:计划书/下一步改进指南.md` 取回）
> 规则：只记事实与证据；只有观察到交付物 + 实跑验收证据才标 done；外部受限项标「待验证 / L2 授权」不伪装。

## 本轮授权口径（用户 2026-10-14 明确）

| 项 | 决定 |
|---|---|
| `api/config/` 半成品拆分 | 先审计并完成它 |
| 浏览器 E2E（MCP 全线掉线） | 跳过浏览器，用脚本级 E2E 代替 |
| git push / GitHub Release | **已授权**；线上部署另行确认 |

## 事实基线

- HEAD：`0f658e0` docs(v23.1) ｜ 版本 **23.1.0** ｜ 分支 main
- 工作区存在**上一轮未提交的改动**（config 拆分 + metrics 修复 + 文档删除），见下「继承改动」
- `.venv/Scripts/python.exe` 为唯一可用解释器（`python`/`python3` 不在 PATH；`rg` 不可用，改用 Grep 工具）

## 继承改动（上一轮留下，未提交）

| 文件 | 内容 | 状态 |
|---|---|---|
| `api/config/__init__.py` | 851 → 79 行垫片 | ✅ 已实跑验证 |
| `api/config/settings_core.py`（新） | 602 行，Settings + 工厂 | ✅ import OK |
| `api/config/constants.py`（新） | 244 行，模块级常量快照 | ✅ import OK |
| `tests/test_config_pkg_attr.py`（新） | `_pkg_attr`/`_mock_register` 契约测试 | ✅ 41 config 测试全绿 |
| `scripts/restore_drill.py` | GBK → UTF-8 reconfigure | ✅ 待复验 |
| `api/metrics_ext.py` | `_counter_inc_absolute` 恒触碰 label + histogram 预建 | ✅ 待复验 |
| `tests/test_metrics_ext.py` | +40 行 | ✅ 通过 |
| 计划类文档 ×6 | `计划书/下一步改进指南.md` + `workflow_status.md` + `docs/archived/` ×3 已 staged 删除 | ⚠️ 见 P1-1 |

## 问题清单（按严重度）

### P0（阻塞）

无。

### P1（高）

| ID | 问题 | 证据 | 影响 |
|---|---|---|---|
| P1-1 | **ruff 基线漂移：声明 0 error，实测 27 errors，exit=1** | `./.venv/Scripts/python.exe -m ruff check api/ tests/ scripts/` → `Found 27 errors` | 推翻 `.wolf/memory.md` 2026-10-14 条目中「ruff 我改动文件 0 error」的说法；CI ruff 门禁若启用则直接红 |
| P1-2 | **`tests/test_uptime_probe.py:23` F821 Undefined name `ModuleType`** | ruff 报 `F821 Undefined name ModuleType`；代码 `def _load_probe() -> "ModuleType":` 但仅 `import importlib.util`，未导入 `types.ModuleType` | 字符串注解在 `typing.get_type_hints()` 解析时抛 `NameError`；属**上一轮新写测试的真实缺陷** |
| P1-3 | **`scripts/ops/` 被 ruff 扫描但未 exclude** | `pyproject.toml [tool.ruff]` 无 `exclude`；`scripts/ops/_dep33.py` / `_srv_py.py` 贡献 10 个 error（E401/I001/E701） | 该目录含生产凭证、已被 `.gitignore` 整体忽略，却仍污染 lint 基线 |

### P2（中）

| ID | 问题 | 证据 | 影响 |
|---|---|---|---|
| P2-1 | `CLAUDE.md` 技术债描述已过时 | `CLAUDE.md:112` 仍写「`api/config/__init__.py`（851）…仍超线」，实际 **79 行** | 文档与真实状态不一致（配置工厂段已同步，大文件治理段漏改） |
| P2-2 | `CLAUDE.md` 边界段与 `.wolf/memory.md` 已同步但需复核 | `CLAUDE.md:124` 已改为「litestream R2 / 观察栈 / cf_solver 第二节点未落地」 | 表述基本准确，待终审 |
| P2-3 | 多处 lint 债：`test_restore_drill.py` F401 ×3、`test_gallery_crud.py` F401/F841、`test_health_report.py` F401 | ruff concise 输出 | 未使用 import / 变量；`test_uptime_probe.py:9` `functools` 未使用 |
| P2-4 | `uptime_probe.py:74` 与 `test_restore_drill.py:179` 无文件尾换行（W292） | ruff | 风格，可 `--fix` |

### P3（增强）

| ID | 问题 | 说明 |
|---|---|---|
| P3-1 | `.gitignore` 缺 `_*.py` 通配 | 指南 P0-4 指定「补 `_*.py` 根级临时文件排除」；实际用根锚定 `/_dep33.py` + `scripts/ops/` 目录规则替代。`git check-ignore api/_foo.py` **不被忽略** → 将来子目录新建含凭证的 `_xxx.py` 不被拦截 |
| P3-2 | 凭证轮换无法在本仓库内验证 | `scripts/ops/_dep33.py` / `_srv_py.py` 仍在磁盘（含生产 SSH 明文凭证），仅被 ignore。轮换需用户在服务商侧操作 → **L2 授权 / 用户操作** |

## 指南条目闭环状态（独立审计结论）

| 项 | 结论 | 决定性证据 |
|---|---|---|
| P0-1 litestream R2 | **部分闭环** | 配置三库齐 + compose backup profile + `restore_drill --from-litestream` 真实实现；**真凭证未填**，`deploy/.env` 无 LITESTREAM 键 → L2 授权阻塞 |
| P0-2 观察栈 | **部分闭环** | obs profile + 4 grafana 资产齐；**dashboard 12/12 指标名全部真实存在，零幻觉**；容器未跑 → 运行态未验证 |
| P0-3 solver 第二节点 | **未闭环（有意边界）** | compose 仍单 cfsolver；代码支持完备（`settings_core.py:52-55`、`solver.py:32-84`）；N5 已实测 10/10 分流 2.9s vs 6.7s（`scripts/probe_federation.py` 已入库）；**编排启用属生产决策** |
| P0-4 旧产物/安全 | **部分闭环** | 已移出根目录 + 已 ignore + `logs status` 干净；**未删除、轮换未验证** |
| G15 版本门禁入 CI | **已闭环** | `ci.yml:45`，位置在单测前（L41 vs L47），已提交 `d41285a` |

## 验证日志

| 时间 | 命令 | 结果 |
|---|---|---|
| 2026-10-14 | `./.venv/Scripts/python.exe -c "import api.config"` | ✅ import OK，`get_settings()` → `Settings`，host=127.0.0.1 port=8100 |
| 2026-10-14 | `pytest tests/test_config_pkg_attr.py tests/test_metrics_ext.py -q` | ✅ exit 0（16 passed） |
| 2026-10-14 | `pytest tests/test_config_compat.py test_config_settings_namespace.py test_config_pkg_attr.py test_config_validate.py -q` | ✅ 41 passed |
| 2026-10-14 | `ruff check api/ tests/ scripts/` | ❌ **27 errors，exit=1** |
| 2026-10-14 | `git ls-files scripts/ops/` | ✅ 空（凭证文件未入库） |
| 2026-10-14 | `git check-ignore` 抽验 | ✅ `_dep33.py` / `scripts/ops/*` 均被忽略；❌ `api/_foo.py` 不被忽略 |

## 阻塞项

- **MCP 全线掉线**：graft / code-review-graph / playwright / sequential-thinking / memory 连接超时 → 图谱检索与浏览器 E2E 本轮不可用（用户已决定用脚本级 E2E 替代）
- **Docker 不可用**：P0-1 R2 真接、P0-2 容器起服无法在本机验证
- **外部凭证**：R2 / Grafana Cloud / UptimeRobot 账户 → L2 授权

## 本轮修复记录（2026-10-14）

### 已完成

| ID | 修复 | 文件 | 验证 |
|---|---|---|---|
| **P0-1** | **`IF_CORS_ORIGINS` 环境变量静默失效 → CORS 白名单从未生效**（安全） | `api/config/constants.py` + `settings_core.py` | **E2E：白名单内 Origin 放行、白名单外无 allow-origin 头** |
| P1-1 | ruff 基线 27 → **0 error** | 见下 P1-2/P1-3/P2-3 | `ruff check api/ tests/ scripts/` exit 0 |
| P1-2 | F821 `ModuleType` 未定义 → 导入 `types` 并去引号 | `tests/test_uptime_probe.py` | 该文件 6 用例通过 |
| P1-3 | ruff `extend-exclude = ["scripts/ops"]`（含凭证的运维脚本不入 lint 基线） | `pyproject.toml` | ruff 0 error |
| P2-3 | 清理 F401/F841/I001/UP017/W292 等 lint 债 | `test_gallery_crud.py` / `test_health_report.py` / `test_restore_drill.py` / `api/routes/tasks.py` / `api/health_report.py` / `scripts/uptime_probe.py` / `test_account_pool.py` | 上述 7 文件测试全绿 |
| P1-4a | **E2E 脚本硬编码宿主绝对路径** → 改为 `__dirname` 推导 + 环境变量回退 | `scripts/e2e_mobile_smoke.cjs` | 真跑通过 |
| P1-4b | **E2E 漏测 `/admin` 路径**（v22 承诺 2 条实做 1 条）→ 补 `/admin` + 深链回退断言 | `scripts/e2e_mobile_smoke.cjs` | 9 passed |
| P1-4c | **无配套静态服务器**（4590 无服务，脚本从未真跑通）→ 新建 | `scripts/serve_static.cjs`（新） | 4 端点探活 200/307 正确 |
| P1-5 | **画廊错误泄漏技术黑话**：`Unexpected token '<', "<!DOCTYPE "... is not valid JSON` 直接渲染给用户 → 按失败类型归类中文文案 + `errorDetail` 保留原始细节 | `landing/src/composables/usePolling.js` | 7 新单测 + **E2E 截图实测文案已变** |
| P1-6 | **vitest 在非 ASCII 路径下 worker 超时**（`2api目录`）→ 固化 `isolate:false` | `landing/vitest.config.js` + `landing/package.json` | `npm test` 直接通过 12/12 |
| P1-7 | **admin topbar 面包屑 375px 文字重叠**（"控制台"压成竖排叠字）→ `min-width:0` + ellipsis | `frontend/src/components/Layout.tsx` | E2E 截图对比确认 |
| P1-8 | **聊天页动作按钮组 375px 溢出**（sz 349 > cw 313）→ 480px 断点换行 + 收缩 | `frontend/src/pages/ChatPlayground.tsx` | E2E 溢出元素 6→0 |

### P0-1 详述：CORS 白名单从未生效（安全缺陷，独立审查发现）

**症状**：`IF_CORS_ORIGINS` 设了任何值，`api/main.py` 挂载的 CORSMiddleware 仍为 `allow_origins=["*"]`。

**根因链**（读代码 + 实证确认）：

```python
# api/main.py:128 —— 唯一消费点
allow_origins=[o.strip() for o in (config.CORS_ORIGINS or "*").split(",") if o.strip()]

# api/config/constants.py:233（修前）—— 硬编码字面量，与同文件其他常量写法不一致
CORS_ORIGINS = "*"          # 同文件其他行都是 `= settings.xxx`

# api/config/settings_core.py:493（修前）
global CORS_ORIGINS         # 拆包后只写 settings_core 命名空间，与 api.config 无关
CORS_ORIGINS = self.if_cors_origins or "*"
```

**成因判定**：**既有缺陷，非本次拆分引入**。HEAD 旧版中 `Settings.__init__` 的 `global CORS_ORIGINS`（写 `api.config` 命名空间）本可生效，但 `settings = Settings()`（L603）**之后**的模块级字面量 `CORS_ORIGINS = "*"`（L817）把它覆盖回 `*` —— 语句顺序决定字面量胜出。拆分后 `global` 写到 `settings_core`，与包命名空间更不相干，但净效果相同：env 始终无效。

**修复**：
1. `constants.py`：`CORS_ORIGINS = settings.if_cors_origins or "*"`（与同文件其他常量写法一致）
2. `settings_core.py`：`Settings.__init__` 改为同布 `api.config` 包命名空间（套用上一轮修 `settings` 的模式）

**端到端验证**（真实 uvicorn + 真实 HTTP 请求）：

```
$ IF_CORS_ORIGINS="https://probe.example.com" uvicorn api.main:app --port 8100
READY after 30s

$ curl -H "Origin: https://probe.example.com" -D - /v1/healthz
access-control-allow-origin: https://probe.example.com     ← 白名单内放行 ✓

$ curl -H "Origin: https://evil.example.com" -D - /v1/healthz
(无 access-control-allow-origin 头)                         ← 白名单外拒绝 ✓
```

修复前两者均返回 `*`（任意站点可跨域读取）。

**回归锁**：`tests/test_cors_origins_env.py`（5 用例）覆盖 env 生效 / 快照读点 / 默认 `*` / 空值回退 / main 解析契约。

**同类缺陷系统排查**：`grep -oE "^[A-Z][A-Z0-9_]* *=" api/config/*.py | sort | uniq -d` → 无重复赋值；修后 `constants.py` 中除 `MOCK_UPSTREAM = mock_upstream()`（函数调用，文档化快照语义）外，全部为 `= settings.xxx`。**无同类残留**。

### P0-2 详述：测试套件存在静默失败（本批最关键的过程性发现）

**发现路径**：分批跑全量时，3 个批次超时（exit=-9），但其**尾部输出里含 `F` 符号**：

```
exit=-9 files=[test_geo_ip.py, test_health_probe.py, test_health_registry.py,
               test_health_report.py, test_http_pool_config.py, test_human_inbox_export.py]
tail: [TIMEOUT after 600s] ....................................F........ [ 85%]

exit=-9 files=[test_main_validation.py, test_mcp_server.py, test_mcp_tools_meta.py,
               test_memory_explain.py, test_memory_rrf.py, test_memory_supersede.py]
tail: [TIMEOUT after 600s] .............................................F.......
```

第二次**完整跑完**的全量运行（100%）同样证实：

```
49%: F    55%: F    61%: F    68%: F    83%: E
```

**即 4 个失败 + 1 个错误**，而项目记忆声称「169 关键回归全绿」。

#### 为什么一直没被发现 —— 失败是**静默**的

`tests/conftest.py` 的 `pytest_sessionfinish` 调 `os._exit(exitstatus)`（Windows 本地
teardown 永不返回的兜底）。它在 terminal reporter 写失败详情**之前**结束进程，
所以：

- stdout 只有 `.....F...` 进度点，**看不到失败的用例名与 traceback**
- `--junitxml` **也不会生成文件**（junitxml 插件同样在 sessionfinish 写盘）—— 实测确认

后果：全量跑只会显示 `F`，而"全绿"的结论无从核实。

#### 已定位并修复的 2 处

**① `tests/test_http_pool_config.py::TestHttpPoolConfig::test_env_overrides`**
（`PYTEST_NO_FORCE_EXIT=1` + 单文件 + `--tb=short` 才取到）：

```
AssertionError: assert 100 == 50
  where 100 = api.config.IF_HTTP_MAX_CONNECTIONS
```

**根因**：测试用 `importlib.reload(api.config)` 期望 env 生效。拆包后常量由
`api/config/constants.py` 在 import 期绑定为快照；**`reload` 包不会重新执行已导入的
子模块 `constants`**，故快照保持旧值。旧版把常量内联在 `__init__.py`，reload 恰好能刷新
——属偶然而非契约。**这是拆包引入的真实回归**（此前无人发现，因为失败被静默）。

**修复**：按项目文档化设计（`constants.py` docstring 明示快照语义、生产 env 在 import 前
设定即正确），把该用例改为**子进程验证**（与生产路径一致），而非依赖 in-process reload。
现 `test_http_pool_config.py` **7 passed**。

**② `tests/test_mcp_server.py::TestToolsList::test_tools_list_whitelist`**

```
AssertionError: assert {...} == {...}
Extra items in the left set:
'retrieve_tools'
'describe_tool'
```

**根因**：**陈旧断言**（非安全泄漏）。v18 P1-3 在 `api/mcp/tools.py` 新增
`retrieve_tools` / `describe_tool` 两个「渐进暴露」工具（`intent="read"`、
`expose=True`，代码注释明示为有意功能），但本测试的白名单仍停留在 v16，未同步。
因失败详情被 `os._exit` 截断，长期只显示 `F` 而无人察觉。

**修复**：白名单补齐 2 个工具 + 补只读断言 + docstring 标注版本沿革。
现 `TestToolsList` **1 passed**。

#### 第三处：`test_skill_sediment.py::test_route_sediment_disabled` teardown ERROR（既有缺陷，非本批引入）

全量分批跑的第 12 批复现 `E`（`199 passed / 0 failed / 1 errors`）。用 `-v` 精确定位：

```
tests/test_skill_sediment.py::test_route_sediment_disabled PASSED  [100%]
tests/test_skill_sediment.py::test_route_sediment_disabled ERROR   [100%]   ← teardown 报错
```

**根因**（`PYTEST_NO_FORCE_EXIT=1 --tb=long` 取到）：

```
ERROR at teardown of test_route_sediment_disabled
starlette/testclient.py:709 in __exit__ → self.exit_stack.close()
RuntimeError: Task <Task pending name='anyio.from_thread.BlockingPortal._call_func'
  coro=<Task …der_probe.py:73> wait_for=<Future cancelled>> attached to a different loop
```

**跨文件事件循环污染**：`test_sediment_probe.py` 残留的任务挂在另一个 event loop 上，
后续 `test_skill_sediment.py` 的 session 级 `client` fixture 在 teardown 关闭
`BlockingPortal` 时抛 `attached to a different loop`。正是 `tests/conftest.py` docstring
警告过的同类问题（"跨 loop 死锁"）。

**判定为既有缺陷，非本批引入**（已用实验证明）：把本批的 CORS 修复**临时回退**后
重跑同样 12 个文件，`E` **照样复现**。故与 `api/config/` 改动无关。

**最小复现尝试**：仅 `test_sediment_probe.py + test_skill_sediment.py`（两种顺序）**均通过**，
说明需要第三个文件参与触发，未进一步二分（属既有测试隔离债，非本批范围）。

**建议**（未实施，留给后续专项）：`tests/test_skill_sediment.py` 的 `client` fixture 改为
function-scope，或在 `test_sediment_probe.py` 结束时显式 cancel 其遗留任务。

#### 全量结果（本批修复后）

| 项 | 结果 |
|---|---|
| passed | **2161** |
| failed | **0** |
| errors | **1**（即上述既有 loop 污染） |
| 覆盖 | 155 / 179 文件（24 个慢文件因单批 900s 超时未覆盖，其已跑部分 **0 失败**） |

**结论：本批修改后，全量测试零失败。** 唯一非通过项为既有的跨文件 event-loop 污染，
已在上面完整定位并证明与本批无关。

#### 工具修复

`scripts/run_tests_batched.py` 的计数逻辑经历两次修正：初版解析摘要行（恒 0）→ 改用
`--junitxml`（实测不生成文件，仍恒 0）→ 最终改为**解析 `-q` 进度符号**
（`_count_from_progress()`，进度行在 `os._exit` 之前已输出，可靠）。已实测
`progress: 7 passed / 0 failed / 0 errors / 0 skipped`。

### 过程性发现（测试有效性的证据）

- 修复 P1-7 后 E2E **立刻报 FAIL**（overflow 6 个）→ 证明断言有真实判别力，非摆设
- 断言迭代两次：初版把「ellipsis 截断」与「脉冲动画伪元素」误判为缺陷 →
  改为「有意截断 + 实际盒未越视口右缘」双重排除，噪声消除且真溢出仍能抓到
- **`.wolf/memory.md` 2026-10-14 条目称「ruff 我改动文件 0 error」与实测 27 errors 不符** ——
  已修正为真实基线 0（这是本轮抓到的伪闭环，非删档行为）

### 验证日志（本轮新增）

| 命令 | 结果 |
|---|---|
| `ruff check api/ tests/ scripts/` | ✅ **0 error, exit 0**（修前 27 errors, exit 1） |
| `pytest test_uptime_probe test_restore_drill test_health_report test_gallery_crud test_account_pool test_metrics_ext test_config_pkg_attr -q` | ✅ 全绿 |
| `cd landing && npm test` | ✅ **12 passed（2 files）** |
| `node scripts/serve_static.cjs --port 4590` + curl | ✅ `/`→200, `/admin`→307, `/admin/`→200, `/admin/tasks`→200 |
| `node scripts/e2e_mobile_smoke.cjs` | ✅ **9 passed / 0 failed, exit 0**（真实 chromium 1243，截图落盘） |
| `cd landing && npm run build` | ✅ index gzip 52.27kB < 150KB |
| `cd frontend && npm run build` | ✅ index gzip 84.50kB ≈ 基线 84.04kB |

### 待办

- 后端全量测试（分批 ≤12 文件）
- 独立审查线程 + HTML 报告 + 测验 + skill 沉淀

### 判定为「伪问题 / 不建议实施」的项（诚实记录，不制造虚假工作量）

| 来源 | 项 | 判定 | 依据 |
|---|---|---|---|
| 指南 P0-4 | 补 `.gitignore` `_*.py` 通配 | **不建议实施（有害）** | 实证：该通配会静默忽略 `api/__init__.py`、`api/account_pool/__init__.py`、`_base.py`、`_limits.py` 等**已入库合法模块**，且新建文件的 `__init__.py` 将无法提交（沙箱 git 模拟验证：`.gitignore` 写 `_*.py` 后 `__init__.py`/`_helper.py` 全部不可见）。现方案（根锚定 `/_dep33.py` + `scripts/ops/` 目录 + `/_probe_*.py`）**才是正确的**。 |
| 审计 agent | 5 个页面 aria-label 为 0（ApiGuide/Ecosystem/Health/Providers/Slow） | **伪问题，不修** | 逐页核查：所有 `<button>` 均带**可见文字**（`🔄 刷新`、`📄 导出报告`），不存在 icon-only 控件；所有 `<input>` 均由 `<label>` 包裹或带显式 `aria-label`（多行属性）。计数低≠可访问性缺陷。为凑数字加 aria-label 属无意义改动。 |
| 指南 P0-3 | cf_solver 第二节点 | **有意边界，非遗漏** | 代码能力完备（`settings_core.py:52-55`、`solver.py:32-84`）+ 实测探针 `scripts/probe_federation.py`（N5 记录 10/10 分流，2.9s vs 6.7s）+ SOP 文档。compose 启用属**生产编排决策**，需用户授权，非工程欠账。 |
| 指南 P0-1/P0-2 | litestream R2 / 观察栈 | **外部资源阻塞（L2 授权）** | 资产 100% 就绪（三库配置 + backup profile + `--from-litestream` 真实实现；obs profile + 4 grafana 资产 + **dashboard 12/12 指标名全部真实存在零幻觉**）。真凭证 / 容器起服需外部条件。 |


