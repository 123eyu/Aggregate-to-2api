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

### 根因：在途写跨越了 DB 路径切换（TOCTOU）

`add_or_update` 里 `init_schema()` 读 `_initialized`、`_get_conn()` 读 `_path`
—— **两者不是同一次读取**，中间还隔着写锁的 `await`。
而 `tests/test_ip_blocklist.py` 的 fixture 会**就地改共享单例的私有属性**做每用例隔离，
且它的 docstring **声称**「同时尝试等待在途 `_auto_block_ip` 后台任务」
—— **代码里没有任何等待动作**。

于是：

```
写锁被占（另一笔写在途）→ 在途任务卡在 acquire()
  → 此刻 fixture 翻路径：_path = 全新空库、_initialized = False
  → 放行 → _get_conn() 用新库 → INSERT → no such table: ip_blocklist
```

**本机确定性复现**（非碰运气，报错与 CI junit **逐字一致**）：

```python
await store._write_lock.acquire()               # 占住写锁
t = asyncio.create_task(store.add_or_update(...))
await asyncio.sleep(0)                          # 让它越过 init_schema、卡在锁上
store._path = <新空库>; store._initialized = False
store._write_lock.release()
await t    # → sqlite3.OperationalError: no such table: ip_blocklist
```

**两种症状是同一 TOCTOU 的两个落点**：时序稍差时表现为 `database is locked`。
CI junit 里两种都出现过 —— 此前一直被当作"随机网络问题"。

### 修法

- `api/background.py` 新增 **`await_pending(timeout)`** —— 等待在途后台任务结束。
  该模块此前只有 `spawn` / `pending_count`，**缺"排空"入口**，所以调用方想等也做不到
  （先例：`sse_events.await_pending_sse_tasks`）。
- fixture：换路径**前后各等一次**在途任务，确保没有任何写跨越路径切换点。
- docstring 改为**描述实际所做的事**。

### 残留（已在代码内记录，未加固）

`IPBlocklistStore` 自身的 TOCTOU **仍在**。**生产不受影响**（`_path` 在 import 期定死、
运行期不改）。已在 `init_schema` 的 docstring 写明：**若将来要支持运行期切库
（多租户等），必须先加固本类**（单次快照 `_path` + 在**同一连接**上确保表存在）。

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
pytest tests/test_background_tasks.py    → 5 passed（新增）
pytest tests/test_ip_blocklist.py        → 28 passed
pytest tests/test_config_validate.py     → 25 passed（新字段过双向契约）
pytest tests/test_gallery_dedupe.py      → 14 passed
pytest tests/test_version_consistency.py → 5 passed
_public_base_url() 实跑                   → 默认生产域名；设 env 后正确覆盖且去尾斜杠
npx tsc -b                               → exit 0
cd landing && npm run build              → 成功
node scripts/e2e_mobile_smoke.cjs        → 9 passed / 0 failed（真实 chromium）
CI run 38976132637                       → ✅ success
```

---

## 升级说明

无破坏性变更。新增可选配置 `IF_PUBLIC_BASE_URL`（不设则用默认生产域名）。
版本全链 10 文件 + 双 dist 已同步至 23.3.3。
