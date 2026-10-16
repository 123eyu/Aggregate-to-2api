# v23.3.2 — CI 首次全绿：flaky 根因根治 + 进度条降级覆盖修复

**发布日期**：2026-10-16
**基线**：v23.3.1 (`cf663ac`)
**性质**：缺陷修复批（无新功能、无破坏性变更、无需迁移）

---

## 一句话

**CI 六个 job 全部通过 —— 这是本仓库自 2026-09-08 以来第一次完整跑绿**
（此前连续 11 次 failure）。同时修掉一个用户可见缺陷（进度条每 2 秒被抹回「运行中」）。

```
CI run 38887120926 → success
[OK] 前端 E2E + 自动化审计（e2e-smoke + a11y + perf + resp）
[OK] 代码检查（ruff）
[OK] 前端版本一致性门禁
[OK] 前端管理面板门禁（tsc + vitest + build）   ← 此前长期为红
[OK] 测试 (3.11, ubuntu-latest)                  ← 此前长期为红
[OK] Docker 构建验证
```

---

## 修复 1（核心）：前端 flaky 的**根因**

### 机制

`isolate: false` 让**同一 worker 内的多个测试文件共享模块实例**，
而 `vi.mock` 的假模块是**按文件注册**的 —— 后跑文件里被缓存的组件闭包
仍指向**上一个文件遗留的 mock 实例**，本文件新注册的 mock 对它完全无效。

本机强制两文件同 worker 连跑的实测（`--no-file-parallelism`）：

| 顺序 | 结果 |
|---|---|
| `GalleryAlbum → Gallery` | `Gallery.test.tsx` **4 用例全红**：`Unable to find an element with the alt text: test prompt`（DOM 里其实是 GalleryAlbum 的 2 项数据） |
| `Gallery → GalleryAlbum` | `GalleryAlbum` **7 用例全红**：`Cannot read properties of undefined (reading 'total')` |

这两个文件是全仓库唯一「同一组件 + 同一 `vi.mock` 目标」的组合
（其余 26 文件不受影响：单 worker 全量实测 `2 failed | 26 passed`，失败仅此一对）。

**这就是「同一 commit 时红时绿」的机制**：文件→worker 的分配取决于哪个 worker 先空闲 ——
4 vCPU 的 runner 上两个 Gallery 文件偶尔落进同一 worker → 后跑者必红；
本机 16 vCPU 几乎不会同组，所以本地长期复现不到。

### 修法：`isolate: false` → `true`，配套 `maxWorkers: 2`

`isolate: true` 下每个文件都要重启 worker 环境，启动成本显著上升，
而 vitest worker 启动有 **60s 内部硬超时**、非 ASCII 路径（`2api目录`）下这段本就偏慢：

| 配置 | 结果 |
|---|---|
| 默认并发 + `isolate:true` | **28 errors / 0 tests**（全部 worker 启动超时，套件完全不可用） |
| `maxWorkers:2` + `isolate:true` | **28 files / 300 passed**（488s，稳定可跑） |

曾试过的替代方案「关掉 isolate」能让默认并发跑起来，但**那正是引入跨文件 mock 串味的原因** ——
所以**不关隔离**，改为降低并发让 worker 能在超时前起来。CI（ubuntu-latest，4 vCPU）
并发更低，此值同样安全。

---

## 修复 2：进度条每 2 秒被轮询抹回「运行中」（用户可见）

`useTaskProgress` 的轮询每 tick **无条件** `apply(mapStatusToDetail(t.status))`，
而 `GET /v1/tasks/{id}` 的响应（`TaskInfo`）**不含** `status_detail` / `progress`
—— 二者只存在于 SSE 事件负载。于是：

1. SSE 推 `solving/30` → 阶段徽章「求解中」+ 定值进度条 30
2. 2 秒后轮询返回 `processing` → 映射出 `{null,null}` → **被清回「运行中」+ 无定值进度条**

用户看到的就是**进度条每 2 秒跳一次**。

实证来源：`Tasks.test.tsx` 失败时的 DOM dump —— `aria-label="任务阶段：运行中"`
+ progressbar **无** `aria-valuenow`（即 SSE 已推过精确值，却被轮询打回粗粒度）。

**修法**：轮询的职责是「探测终态 + 无 SSE 时兜底」，不是用粗粒度信息覆盖精确信息

```ts
// 状态变了要更新；状态没变且映射不出更细的阶段 → 不动现有精确值
if (mapped.statusDetail === null && lastAppliedStatus === t.status) return;
```

**未做**（记录边界）：「刷新页面 / SSE 断开后只剩粗粒度阶段」是**精度限制而非错误**
（数据从未持久化）。要让刷新后也能看到阶段，需把 `status_detail`/`progress` 落库
并加进 `TaskInfo` —— 那是一次 API 契约变更（改 3 个发布点 + schema + 迁移），
属**独立决策项**，本批不做。

---

## 验证

```
npx tsc -b                                  → exit 0
NODE_OPTIONS=--max-old-space-size=4096 npx vitest run
  （CI 同款命令，不带任何 CLI 参数，完全读配置）
  → Test Files 28 passed | Tests 300 passed | 0 failed

pytest tests/test_shutdown_task_robustness.py tests/test_db_retention.py → 23 passed
pytest tests/test_version_consistency.py    → 5 passed
ruff check api/ tests/ scripts/             → All checks passed!

# CI 侧（决定性）
GitHub Actions run 38887120926 → success（6/6 job）
```

**变异验证**（新增用例的判别力）：把「进度条降级覆盖」的修复摘掉 →
**该用例单独失败、原 4 条照过**（`1 failed | 4 passed`）→ 精确命中。

---

## 顺带修复

- `tests/test_shutdown_task_robustness.py`：`_MANAGERS`/`_IDS` 被定义了两次（后者覆盖前者），
  删除重复。**测试语义与断言强度不变**。
- `.wolf/buglog.json` 按项目协议记入 bug-025（isolate 串味）/ bug-026（轮询覆盖）。

---

## 升级说明

无破坏性变更。无需迁移。版本全链 10 文件 + 双 dist 已同步至 23.3.2。
