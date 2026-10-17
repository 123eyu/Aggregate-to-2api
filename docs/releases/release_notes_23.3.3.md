# v23.3.3 — CI 长期 flake 根治 + 退役域名清理

**发布日期**：2026-10-17
**基线**：v23.3.2 (`8ae5018`)
**性质**：缺陷修复批（无破坏性变更、无需迁移）

---

## 一句话

根治了**持续制造 CI 噪声的唯一来源**（`test_ip_blocklist` 的 TOCTOU flake），
并清除了散布在代码/模板/落地页里指向**已退役域名**的引用。

---

## 修复 1：`test_ip_blocklist` 的 flake 根治（CI 噪声的唯一持续来源）

### 根因：store 把「是否已建表」记成**布尔标志**，而连接用的是**另一个属性**

`IPBlocklistStore` 用 `self._initialized`（布尔）判断表是否建过，
但 `_get_conn()` 连的是 `self._path`。**两者不绑定** —— 只要 `_path` 被改而
`_initialized` 仍为 `True`，写入就会落到**未建表的库**上：

```
sqlite3.OperationalError: no such table: ip_blocklist
```

触发路径有两条，**都与"有没有等后台任务"无关**：

1. `tests/test_ip_blocklist.py` 的 fixture 换 `_path` 做每用例隔离 ——
   但只要期间**任何**协程在旧路径上跑了 `init_schema()`（把标志置回 `True`），
   换库后的写入就会落到新空库；
2. `api/request_guard.py:438` 的 `_sync_blocklist_cache` 当时走**裸 `loop.create_task`**
    —— 裸 task 不被 `background._BACKGROUND_TASKS` 持有，所以即使调用方
   `await background.await_pending()` 也**看不见它**，等也等不到。

**本机确定性复现**（非碰运气，报错与 CI junit **逐字一致**）：

```python
await store._write_lock.acquire()               # 占住写锁
t = asyncio.create_task(store.add_or_update(...))
await asyncio.sleep(0)                          # 让它越过 init_schema、卡在锁上
store._path = <新空库>                           # 换库
store._write_lock.release()
await t    # → sqlite3.OperationalError: no such table: ip_blocklist
```

**两种症状是同一缺陷的两个落点**：时序稍差时表现为 `database is locked`。
CI junit 里两种都出现过 —— 此前一直被当作"随机网络问题"。

> 注：v23.3.3 的第一版修复（仅 `await_pending` 排空后台任务）**未中根因** ——
> CI 在该提交上仍复现 `no such table`。本版才是根治。

### 修法（在 store 内加固，而非依赖调用方守规矩）

- `_initialized`（布尔）→ **`_initialized_path`（路径快照）**：
  短路检查变成「当前 `_path` 是否正是已建表的那条路径」。路径一换，检查自然失效 → 重走建表。
- `init_schema()` **返回已建表的路径**，全部 8 个调用点改用它开连接
  （`conn = await self._get_conn(path)`）——「检查/建表用的路径」与「随后读写用的路径」
  是同一次读取，任何时刻换 `_path` 都不会让写入落到未建表的库上。
  `_get_conn(path=None)` 仍兼容无参调用。
- `api/request_guard.py:438` 裸 `create_task` → `background.spawn`
  （同文件 `_record_auto_block_violation` 早已改走 spawn，这是漏改的同类点）；
  顺带修掉「裸 task 可被 GC 静默回收 → 封禁缓存不同步」。
- `api/background.py` 新增 **`await_pending(timeout)`**：该模块此前只有
  `spawn` / `pending_count`，**缺"排空"入口**（先例：`sse_events.await_pending_sse_tasks`）。
  仍在 fixture 中用于**文件级隔离**（防在途写把上个用例的临时库写脏），
  但现在**不再是** no-such-table 的依赖项。
- fixture 里 `_initialized = False` → `_initialized_path = None`
  （前者在加固后已不是受控属性，会被当成普通实例属性静默创建，隔离形同失效）。
- 两处 docstring 改为**描述实际所做的事**。

### 回归覆盖

`tests/test_ip_blocklist.py::TestPathSwitchRobustness`（3 用例）：
直接换库自动建表 / **在途写跨越换库**（原 TOCTOU 时序）/ 切库数据互不串。
已做**变异验证**：把 `_initialized_path == path` 退回布尔语义 → 2/3 红
（第 3 个是防「修成始终用同一个库」的对照项，布尔语义下仍成立属预期）。

> 此前 v7.6 的 `test_auto_block_after_repeated_429` 只靠「显式先建表」绕开同一缺陷，
> 未根治；本次才是根因消除。

---

## 修复 2：清除指向已退役域名 `imagefree.tingfengai.art` 的行为性引用

**权威依据在仓库自身** —— `deploy/README.deploy.md:3-6` 明写该域名属「旧腾讯云 Docker 部署」，
**当前生产**为 `https://imagefree.hwhcie.bond`（Azure + systemd）；项目 `CLAUDE.md` 同述。
故这不是域名分叉待拍板，而是**行为性引用指向了死域名**。

| 位置 | 影响 |
|---|---|
| `api/geo_ip.py` | **生成的代理订阅链接指向已下线站点** —— 用户复制过去不可用（且原为硬编码） |
| `landing/src/components/SectionCode.vue` / `SectionFaq.vue` | 落地页**给用户看的 curl 示例**用死域名 |
| `README.md` | 接入方的 curl / `ANTHROPIC_BASE_URL` 示例 → 照抄必失败 |
| `deploy/.env.production.example` | **生产 CORS 模板**白名单到不再服务的域名 |
| `landing/index.html` / `sitemap.xml` / `robots.txt` | canonical / og / twitter / JSON-LD / 站点地图 → **SEO 与分享卡片失效** |
| `frontend/src/pages/ApiGuide.tsx` | 无 `window` 时的回退 base |
| `scripts/block_abuser.ps1` | 运维脚本默认 base → 打到死主机 |
| `deploy/docs/cloudflare-cdn.md` | CDN 指南（前置域名错） |

### 顺带消除硬编码：新增 `IF_PUBLIC_BASE_URL`

`IF_BASE_URL` 是**上游**（imagefree.net），不能复用为"自身公网地址"。
新增 `IF_PUBLIC_BASE_URL`（默认取当前生产域名）：
- `settings_core.py` 加字段（带 `validation_alias`）+ 取址 helper（**懒导入 config** 避循环依赖、去尾斜杠、取配置失败有兜底）
- `deploy/.env.example` / `.env.production.example` 同步
- **契约测试自动把关**：`TestEnvExampleSync`（双向一致）+ `TestEnvMappingContract`（无 alias 必登记）

### 有意**不改**的（历史记录）

`landing/public/release/*` 与 `docs/releases/archive/*`、`docs/reports/*`、`docs/prd/*`、
`docs/research/security-audit-v23.md` —— 其中「线上实锤（匿名 curl `https://imagefree.tingfengai.art`）」
等描述的是**当时确实发生**的验证。**改写会伪造历史**，故保持原样。

---

## 判定为「不做」的设计项（附理由）

| 项 | 判定 |
|---|---|
| `requests.status` 无 `CHECK` 约束 | **不做**：加约束需**表重建**（破坏性迁移），且当前**无实际缺陷** —— 状态值全部由代码写入并有白名单校验。收益 < 风险 |
| 删任务无级联清理（base64 / 幂等键 / DLQ / 向量） | **不做**：① base64 孤儿由 `clean_base64_files(TTL)` 按 mtime 兜底；② **幂等键指向已删任务**是唯一"用户可见"的，但 `IF_IDEMPOTENCY_ENABLED` **默认 `False`** → 默认配置下不可能发生；③ 向量孤儿已由 `/v1/gallery/similar` 的过滤兜住。属**设计权衡**而非缺陷 |

---

## 验证

```
ruff check api/ tests/ scripts/          → All checks passed!
ruff format --check                      → 3 files already formatted
pytest tests/test_background_tasks.py    → 5 passed（新增）
pytest tests/test_ip_blocklist.py        → 31 passed（含新增 TestPathSwitchRobustness 3 用例）
跨文件组合（test_request_guard*.py ×4 + test_ip_blocklist + test_auth_ip）
                                         → 130 passed
pytest tests/test_config_validate.py     → 25 passed（新字段过双向契约）
pytest tests/test_gallery_dedupe.py      → 14 passed
pytest tests/test_version_consistency.py → 5 passed
sync_version.py --check                  → 全链一致 23.3.3（10 文件）
_public_base_url() 实跑                   → 默认生产域名；设 env 后正确覆盖且去尾斜杠
npx tsc -b                               → exit 0
cd landing && npm run build              → 成功
node scripts/e2e_mobile_smoke.cjs        → 9 passed / 0 failed（真实 chromium）
CI run 38986559340 (5851c69)             → ✅ success（6/6 job；前一个提交 6cd7ac9 为 failure）
```

### 针对本修复的专项压测（原始 TOCTOU 时序，非碰运气）

```
in_flight（占住写锁 → 换库 → 放行）       → 300/300 ok
direct（直接换库后写入）                   → 300/300 ok
concurrent_mid_switch（120 协程并发中途换库）→ 120/120 ok
```

---

## 升级说明

无破坏性变更。新增可选配置 `IF_PUBLIC_BASE_URL`（不设则用默认生产域名）。
版本全链 10 文件 + 双 dist 已同步至 23.3.3。
