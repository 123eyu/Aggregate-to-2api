"""关闭路径容错回归（2026-10-16）。

真缺陷（CI junit 实证）：三个后台任务管理器的 `stop()` 里写的是

    self.task.cancel()
    try:
        await self.task
    except asyncio.CancelledError:      # ← 只捕 CancelledError
        pass

`await task` 会**重新抛出该任务的原始异常**。任务若以非 CancelledError 终止
（CI 里是跨事件循环的 `RuntimeError`），异常会冒泡出 `stop()`。

- `ProviderProbeManager.stop()` 被 `api/lifespan.py:177` **直接 await**
  → 异常打断整个优雅关闭序列（其后的 DB flush / SSE 关闭 / provider 收尾全部跳过）
- `FreeProxyFetcher.stop()` / `ProxyTracer.stop()` 经 `shutdown_phase` 包装
  → 异常虽被吞，但留下 "Task exception was never retrieved" 噪声

本组锁死「后台任务以任意异常终止时，stop() 都不得向外抛」这一契约。

风格：直接构造管理器 + 注入一个必然失败的任务，不依赖真实网络。
"""

from __future__ import annotations

import asyncio

import pytest

from api.free_proxy_fetcher import FreeProxyFetcher
from api.provider_probe import ProviderProbeManager
from api.proxy_tracer import ProxyTracer


async def _boom() -> None:
    """模拟后台循环以非 CancelledError 终止（如跨事件循环 RuntimeError）。"""
    raise RuntimeError("simulated background failure (cross-loop)")


async def _hang_until_cancelled() -> None:
    """正常长跑任务：被 cancel 时应以 CancelledError 结束。"""
    while True:
        await asyncio.sleep(3600)


# 三个管理器的构造签名不同：ProviderProbeManager() 无参；
# FreeProxyFetcher/ProxyTracer 需 pool（stop() 不使用它，传 None 即可）。
_MANAGERS = [
    (lambda: ProviderProbeManager(), "_task"),
    (lambda: FreeProxyFetcher(None), "task"),
    (lambda: ProxyTracer(None), "task"),
]
_IDS = ["provider_probe", "free_proxy_fetcher", "proxy_tracer"]


@pytest.mark.parametrize("make,task_attr", _MANAGERS, ids=_IDS)
@pytest.mark.asyncio
async def test_stop_tolerates_task_that_failed_with_non_cancelled_error(make, task_attr):
    """任务以 RuntimeError 终止后调 stop()，不得抛异常（原缺陷会冒泡）。"""
    mgr = make()
    t = asyncio.create_task(_boom())
    setattr(mgr, task_attr, t)
    await asyncio.sleep(0)  # 让任务先失败、异常落在 task 上
    assert t.done(), "前置条件：任务已终止"

    # 关键断言：不得抛出 RuntimeError
    await mgr.stop()


# 三个管理器的构造签名不同：ProviderProbeManager() 无参；
# FreeProxyFetcher/ProxyTracer 需 pool（stop() 不使用它，传 None 即可）。
_MANAGERS = [
    (lambda: ProviderProbeManager(), "_task"),
    (lambda: FreeProxyFetcher(None), "task"),
    (lambda: ProxyTracer(None), "task"),
]
_IDS = ["provider_probe", "free_proxy_fetcher", "proxy_tracer"]


@pytest.mark.parametrize("make,task_attr", _MANAGERS, ids=_IDS)
@pytest.mark.asyncio
async def test_stop_still_cancels_healthy_task(make, task_attr):
    """正常长跑任务：stop() 应 cancel 掉它且不抛（既有语义不得回退）。"""
    mgr = make()
    t = asyncio.create_task(_hang_until_cancelled())
    setattr(mgr, task_attr, t)
    await asyncio.sleep(0)

    await mgr.stop()
    # provider_probe 会把句柄置 None；另两个管理器至少应保证任务已结束
    assert t.cancelled() or t.done()


@pytest.mark.asyncio
async def test_provider_probe_stop_is_idempotent():
    """重复 stop() 不得抛（关闭路径可能被多次触发）。"""
    mgr = ProviderProbeManager()
    mgr._task = asyncio.create_task(_hang_until_cancelled())
    await asyncio.sleep(0)
    await mgr.stop()
    await mgr.stop()  # 第二次：_task 已是 None
    assert mgr._task is None
