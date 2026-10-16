"""P0-3: db/core.py 拆分兼容性测试。

验证目标：
1. `from api.db.core import DB, BatchWrite` 旧 import 路径仍可用（拆分后 DB 类由多 mixin 组合）
2. `from api.db.migrations import init_schema` 新迁移模块可导入
3. 迁移后关键表（requests/idempotency_keys/dead_letter_queue/cache_store/chat_usage）存在
4. DB 实例所有公开方法签名不变（create_request/get/claim_idempotency/push_dlq/save_cache_batch 等）
"""

from __future__ import annotations

import inspect

import pytest

from api.db.core import DB, BatchWrite
from api.db.migrations import init_schema


def _shared_kwargs() -> dict:
    return {
        "task_id": "t1",
        "prompt": "p",
        "aspect_ratio": "1:1",
        "download": False,
    }


def test_db_core_re_exports_db_and_batchwrite() -> None:
    """拆分后 core.py 仍 re-export DB 与 BatchWrite。"""
    assert DB is not None
    assert BatchWrite is not None
    # BatchWrite 仍持有 sql/params 两个字段
    bw = BatchWrite("SELECT 1", ())
    assert bw.sql == "SELECT 1"
    assert bw.params == ()


def test_migrations_module_exposes_init_schema() -> None:
    """migrations.py 暴露 init_schema 协程函数。"""
    assert callable(init_schema)
    assert inspect.iscoroutinefunction(init_schema)


def test_db_public_method_signatures_unchanged() -> None:
    """关键公开方法签名（含参数名）不得变——保护调用方。"""
    sig = inspect.signature(DB.create_request)
    params = list(sig.parameters)
    assert params == [
        "self",
        "task_id",
        "prompt",
        "aspect_ratio",
        "download",
        "type_",
        "model",
        "client_ip",
        "user_agent",
    ]

    sig2 = inspect.signature(DB.claim_idempotency)
    assert list(sig2.parameters) == ["self", "key", "task_id"]

    sig3 = inspect.signature(DB.mark_finished)
    assert list(sig3.parameters) == [
        "self",
        "task_id",
        "status",
        "image_url",
        "error",
        "duration_sec",
        "image_base64",
        "image_mime",
    ]

    sig4 = inspect.signature(DB.list_tasks)
    assert list(sig4.parameters) == ["self", "limit", "offset", "status", "model", "sort"]


@pytest.mark.asyncio
async def test_init_schema_creates_all_tables(tmp_path) -> None:
    """跑 init_schema 后，5 张关键表必须存在。"""
    import aiosqlite

    db_path = str(tmp_path / "compat.db")
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    import asyncio

    lock = asyncio.Lock()
    await init_schema(conn, lock)
    await conn.commit()

    cur = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = {row[0] for row in await cur.fetchall()}
    expected = {
        "requests",
        "idempotency_keys",
        "dead_letter_queue",
        "cache_store",
        "chat_usage",
    }
    missing = expected - tables
    assert not missing, f"迁移后缺表: {missing}"

    # 关键索引存在
    cur = await conn.execute("SELECT name FROM sqlite_master WHERE type='index' ORDER BY name")
    indexes = {row[0] for row in await cur.fetchall()}
    assert "idx_requests_created" in indexes
    assert "idx_idempotency_created" in indexes
    assert "idx_dlq_created" in indexes
    await conn.close()


@pytest.mark.asyncio
async def test_db_end_to_end_smoke(tmp_path, monkeypatch) -> None:
    """DB 实例经 mixin 拆分后，端到端创建→标记→查询→幂等→DLQ→缓存 全链路可用。"""
    monkeypatch.setenv("IF_DB_FILE", str(tmp_path / "smoke.db"))
    from api import config

    config.reset_settings()
    db = DB(str(tmp_path / "smoke.db"))
    await db._init_async(config.IF_DB_POOL_TIMEOUT)

    # 写
    await db.create_request("t1", "p", "1:1", False, type_="txt", model="default")
    await db.mark_started("t1")
    await db.mark_finished("t1", "completed", "http://x", None, 1.5, image_base64=None, image_mime=None)

    # 读
    row = await db.get("t1")
    assert row is not None
    assert row["id"] == "t1"
    assert row["status"] == "completed"

    # 幂等
    claimed = await db.claim_idempotency("k1", "t1")
    assert claimed == "t1"
    again = await db.claim_idempotency("k1", "t2")
    assert again == "t1"  # 已存在返回先前 task_id

    # DLQ
    await db.push_dlq("t1", "default", "boom", 3)
    dlq = await db.list_dlq()
    assert len(dlq) == 1
    assert dlq[0]["task_id"] == "t1"

    # 缓存
    await db.save_cache_batch([("ck", "cv", 60.0)])
    snap = await db.load_cache_snapshot()
    assert any(k == "ck" for k, _, _ in snap)

    await db.close()
    config.reset_settings()


# ── 2026-10-17 回归锁：并发初始化必须幂等（TOCTOU 竞态）─────────────────────
#
# 真缺陷：`_apply_request_migrations` 里 `PRAGMA table_info` 查列 → `ALTER TABLE ADD COLUMN`
# 之间是**非原子的 read-then-write**。两个进程/线程同时对**同一个全新空库**初始化时，
# 双方都读到「无此列」，各自 ALTER → 后者抛 `duplicate column name`，
# 异常经 lifespan 冒泡 → **该 worker 起不来**（多 worker / 多副本 / 并行 fixture 场景）。
#
# 本组用**真线程**并发（协程会排队，复现不出；实测线程版才稳定触发）。
# 双向对照（8 线程 × 1 轮，同一台机）：
#   修复前（原写法）→ 失败 2：`duplicate column name: client_ip` / `: type`
#   修复后（本代码）→ 失败 0
# 故 3 轮 × 8 线程在修复后稳定通过，且**足以在回归时抓到**（原写法单轮命中率约 25%）。


def _init_once(path: str, barrier, out: list[str], tag: str) -> None:
    """在独立线程 + 独立连接上跑一次建表+补列迁移。"""
    import asyncio

    import aiosqlite

    from api.db.migrations import _apply_request_migrations, _create_requests_table

    async def go() -> None:
        conn = await aiosqlite.connect(path, timeout=15, isolation_level=None)
        try:
            barrier.wait()  # 线程级同步：尽量同时冲进迁移
            await _create_requests_table(conn)
            await _apply_request_migrations(conn)
            out.append(f"{tag}:OK")
        except Exception as e:  # noqa: BLE001 — 任何异常都算失败，正是本测试要抓的
            out.append(f"{tag}:{type(e).__name__}:{e}")
        finally:
            await conn.close()

    asyncio.run(go())


def test_concurrent_schema_init_is_idempotent() -> None:
    """并发（真线程）对全新空库初始化，不得出现 duplicate column name。"""
    import os
    import tempfile
    import threading

    failures: list[str] = []
    rounds = 3
    workers = 8
    for _ in range(rounds):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(path)  # 全新空库（竞态只在空库上触发）
        try:
            barrier = threading.Barrier(workers)
            out: list[str] = []
            threads = [threading.Thread(target=_init_once, args=(path, barrier, out, f"t{i}")) for i in range(workers)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)
            failures += [o for o in out if not o.endswith(":OK")]
        finally:
            for suffix in ("", "-wal", "-shm"):
                try:
                    os.unlink(path + suffix)
                except OSError:
                    pass

    assert not failures, f"并发初始化非幂等（{rounds} 轮 × {workers} 线程）：{failures[:6]}"
