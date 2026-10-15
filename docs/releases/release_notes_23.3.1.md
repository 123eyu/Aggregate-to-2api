# v23.3.1 — CI 转绿：三层级联失败逐个击破

**发布日期**：2026-10-16
**基线**：v23.3.0 (`b37f8af`)
**性质**：缺陷修复批（无新功能、无破坏性变更、无需迁移）

---

## 一句话

修掉 3 个让 CI **后端 job 持续红**的缺陷，**后端 job 已全步骤通过**；
同时把"CI 失败是级联的"这一事实搞清楚并记录。

---

## 背景：CI 已经红了一个多月

本批开工时的实测（GitHub Actions API）：

| 项 | 事实 |
|---|---|
| 总运行次数 | 462 |
| 最近 100 次 | CI **54 failure + 1 cancelled**、Deploy **45 failure** → **成功 0 次** |
| 最后一次 success | 2026-09-08 之前 |

**CI 的失败是级联的** —— 前一步失败会让后续步骤 `[skip]`，
所以必须**逐层修、逐层看**：

| 提交 | 后端 job | 前端门禁 | 揭示/修复了什么 |
|---|---|---|---|
| 基线 | ❌ 单元测试 | ❌ Vitest | 起点：2 个 job 红 |
| `d1b8ae7` | ❌ 单元测试 | **✅** | DOM 泄漏修复在 CI 得到实证 |
| `26929d6` | ❌（`database is locked` 已消失） | ✅ | DB 隔离修复生效 |
| `f862ce6` | ⚠️ 单测 ✅，改由**集成测试**失败 | ✅ | shutdown 修复生效；集成步骤此前一直被 `[skip]` |
| `e55e8fb` | **✅ 全步骤通过** | ⚠️ 另一条 flake | **后端 job 转绿** |

---

## 本批修复

### P1 · `stop()` 冒泡异常，打断整个优雅关闭序列

`api/provider_probe.py` / `free_proxy_fetcher.py` / `proxy_tracer.py` 三处 `stop()` 都写成：

```python
self.task.cancel()
try:
    await self.task
except asyncio.CancelledError:      # ← 只捕 CancelledError
    pass
```

**`await task` 会重新抛出该任务的原始异常。** 任务以任何非 `CancelledError` 终止时，
异常直接冒泡出 `stop()`。

关键区别在**调用方式**：

- `ProviderProbeManager.stop()` 由 `api/lifespan.py:177` **直接 await**
  → 异常**打断整个优雅关闭序列**，其后的 DB flush / SSE 关闭 / provider 收尾
  / worker 停止 / 代理号池停止**全部被跳过**
- 另两处经 `shutdown_phase` 包装（`asyncio.wait` 从不取结果）→ 不致命，
  但留下 "Task exception was never retrieved" 噪声

CI 实证（run 38782001463 之前的 junit）：

```
api/lifespan.py:177: in lifespan
    await provider_probe.stop()
api/provider_probe.py:62: in stop
    await self._task
RuntimeError: Task ... attached to a different loop
```

**修法**：三处补 `except Exception` + `log.warning`。关闭路径必须容错 ——
后台任务的失败不该让整个关机流程失败。

### P1 · `conftest.py` 的 DB 隔离被外部注入绕过

```python
if "IF_DB_FILE" not in os.environ:      # ← 信任边界搞反了
    os.environ["IF_DB_FILE"] = tempfile.mktemp(suffix=".db")
```

它**信任外部注入**的 `IF_DB_FILE`。CI 工作流设了 `IF_DB_FILE: "data/test.db"`
（ci.yml:75）→ 本段整个跳过 → 测试落到**共享的文件库** → 写路径随后抛
`sqlite3.OperationalError: database is locked`（junit 指向 `ip_blocklist_store.add_or_update`）。

同一处也是「测试可污染真实库」风险的来源：宿主 shell / `.env` 里任何残留的
`IF_DB_FILE` 都会让测试直接读写真库。

**修法**：改**无条件**指向临时库；调试需要固定库文件时用**专用**变量
`IF_TEST_DB_FILE` 显式指定 —— 不与应用的 `IF_DB_FILE` 混用。

### P1 · `test_honor` 首页断言缺前置条件守卫

`test_index_linked_to_zanshang` 无条件断言 `GET /` == 200，但 `/` 是条件挂载：

```python
_LANDING_DIR = ... / "landing" / "dist"
if _LANDING_DIR.exists():          # ← 不构建就不挂载
    app.mount("/", ...)
```

后端 CI job 只装 Python 依赖、**不构建前端** → `landing/dist` 不存在 → 404。
本地开发机通常已 build 过，所以长期看不出来。

**修法**：加前置条件守卫，未构建时 skip 并写明原因
（沿用 `test_openapi_contract.py::test_landing_built_dist_version_matches_source` 的既有模式）。

---

## 验证

```
ruff check api/ tests/ scripts/          → All checks passed!

# 关闭容错（新增，含变异验证）
pytest tests/test_shutdown_task_robustness.py        → 7 passed
  └ 三处修复同时摘掉 → 3 用例全红 ✅ 有判别力
pytest + test_free_proxy_fetcher + test_proxy_tracer → 67 passed

# DB 隔离（模拟 CI 注入 IF_DB_FILE）
pytest tests/test_ip_blocklist.py                     → 28 passed
  └ data/ci_sim.db 未被创建 ✅ 证明覆盖生效
6 文件回归（含全部原 CI 失败文件）                      → 84 passed

# test_honor 两条路径都实跑
有 landing/dist                                        → 3 passed
移走 landing/dist（模拟后端 CI job）                    → 2 passed + 1 skipped（带明确理由）
```

**CI 侧实证**（GitHub Actions，`e55e8fb`）：后端 job
「单元测试」「启动 mock cf_solver 并运行集成测试」**全部 ✅**。

---

## 已知未闭环

**前端 vitest 的一条 flake**（非本批引入）：

`e55e8fb` 上报 `TestingLibraryElementError: Unable to find an element with the alt text: test prompt`
（DOM 显示 `gallery-album` 已渲染、计数「2 张」，且只有一个根 div —— 说明 cleanup 有效）。
`Gallery.test.tsx` 全部用例只 mock 1 项，而 `GalleryAlbum.test.tsx:67` 恰好渲染 2 项
→ 判为 `isolate:false` 下**跨文件 DOM 残留的残余症状**。

但它在 `d1b8ae7`/`26929d6`/`f862ce6` 三次 CI 运行中均为 ✅，且本机（Node 25）无法复现
→ 属 flake。**未在无法验证的前提下做投机修改。**

后续若稳定复现，优先怀疑 `Gallery.test.tsx` 的 `vi.useFakeTimers()` 与
`afterEach(cleanup)` 的执行顺序（假定时器期间 unmount 可能不完整）。

---

## 升级说明

无破坏性变更。无需迁移。版本全链 10 文件 + 双 dist 已同步至 23.3.1。
