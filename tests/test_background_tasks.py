"""`api/background.py` 单测：spawn / pending_count / await_pending。

背景：本模块此前只有 `spawn` 与 `pending_count`，**缺「等待全部在途任务结束」的入口**
（`sse_events.py` 早有同类的 `await_pending_sse_tasks`）。缺了它，调用方想在
「切换共享单例状态」前排空在途写就做不到 —— `tests/test_ip_blocklist.py` 的
fixture docstring 曾**声称**做了这件事而实际没有，是 CI 上该文件长期 flake 的根因
（已实测复现 `no such table: ip_blocklist`，见该 fixture 与本模块 `await_pending` 的注释）。
"""

from __future__ import annotations

import asyncio

import pytest

from api import background


@pytest.fixture(autouse=True)
def _clean_pending():
    """用例前后都排空，避免跨用例残留任务影响 `pending_count`。"""
    yield
    for t in list(background._BACKGROUND_TASKS):
        t.cancel()


@pytest.mark.asyncio
async def test_await_pending_returns_zero_when_idle():
    """无在途任务时立即返回 0（不阻塞）。"""
    assert await background.await_pending(timeout=1.0) == 0


@pytest.mark.asyncio
async def test_pending_count_tracks_inflight():
    """spawn 出去的任务在完成前应被 pending_count 计入。"""
    started = asyncio.Event()

    async def _slow():
        started.set()
        await asyncio.sleep(0.05)

    t = background.spawn(_slow(), name="probe-slow")
    await started.wait()
    assert background.pending_count() >= 1
    await background.await_pending(timeout=2.0)
    assert t.done()
    assert background.pending_count() == 0


@pytest.mark.asyncio
async def test_await_pending_drains_and_returns_zero():
    """正常情况：等在途任务结束，返回「超时未完成数」= 0。"""
    done = []

    async def _quick():
        await asyncio.sleep(0.01)
        done.append(True)

    background.spawn(_quick(), name="probe-quick")
    still = await background.await_pending(timeout=2.0)
    assert still == 0
    assert done == [True]


@pytest.mark.asyncio
async def test_await_pending_reports_still_pending_on_timeout():
    """任务活得比 timeout 长 → 返回仍挂着的数量（>0），**不抛异常**。"""

    async def _very_slow():
        await asyncio.sleep(30)

    background.spawn(_very_slow(), name="probe-very-slow")
    still = await background.await_pending(timeout=0.05)
    assert still == 1


@pytest.mark.asyncio
async def test_spawn_records_exception_without_crashing_loop():
    """spawn 的任务抛异常时不应让事件循环崩（_done 回调记录之）。"""

    async def _boom():
        raise RuntimeError("probe boom")

    t = background.spawn(_boom(), name="probe-boom")
    await asyncio.sleep(0.05)
    assert t.done() and t.exception() is not None
    # 事件循环仍然可用
    assert await background.await_pending(timeout=1.0) == 0
