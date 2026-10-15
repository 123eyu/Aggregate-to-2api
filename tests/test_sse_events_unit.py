"""api/sse_events.py TaskEventHub 单元测试（P0-2 覆盖率补强）。

覆盖：subscribe/unsubscribe、publish 广播 + 环形缓冲裁剪 + QueueFull 丢弃、
replay_after（None/-1/中途 id）、buffer_size/get_task_events/subscriber_count、
clear_task、publish_task_event（有 loop / 无 loop 两条路径）、await_pending_sse_tasks
（空集/正常/超时取消）、task_events_generator（Last-Event-ID 回放 + 终态断开 + 心跳）。
"""

from __future__ import annotations

import asyncio

import pytest

from api.sse_events import (
    MAX_QUEUE,
    TaskEventHub,
    _pending_sse_tasks,
    await_pending_sse_tasks,
    hub,
    publish_task_event,
    task_events_generator,
)


@pytest.fixture(autouse=True)
def _clean_hub():
    """每用例清空模块单例 hub 的内部状态（保持同一实例，避免双对象分叉）。"""
    hub._subscribers.clear()
    hub._buffers.clear()
    hub._seq = 0
    yield
    _pending_sse_tasks.clear()
    hub._subscribers.clear()
    hub._buffers.clear()


# ── 基础订阅/发布 ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_subscribe_and_unsubscribe():
    h = TaskEventHub()
    q = await h.subscribe("t1")
    assert h.subscriber_count("t1") == 1
    await h.unsubscribe("t1", q)
    assert h.subscriber_count("t1") == 0
    # 重复 unsubscribe 不抛
    await h.unsubscribe("t1", q)


@pytest.mark.asyncio
async def test_publish_broadcasts_to_subscribers():
    h = TaskEventHub()
    q = await h.subscribe("t1")
    await h.publish("t1", "status", {"s": "pending"})
    payload = q.get_nowait()
    assert "event: status" in payload
    assert '"s": "pending"' in payload or '"s":"pending"' in payload.replace(" ", "")
    assert h.buffer_size("t1") == 1


@pytest.mark.asyncio
async def test_publish_no_subscribers_still_buffers():
    h = TaskEventHub()
    await h.publish("t2", "status", {})
    assert h.buffer_size("t2") == 1
    assert h.subscriber_count("t2") == 0


@pytest.mark.asyncio
async def test_publish_ring_buffer_capped():
    h = TaskEventHub()
    for i in range(60):
        await h.publish("t3", "progress", {"i": i})
    assert h.buffer_size("t3") == 50  # _MAX_EVENTS_PER_TASK


@pytest.mark.asyncio
async def test_publish_queue_full_dropped_not_blocked():
    h = TaskEventHub()
    q = await h.subscribe("t4")
    # 填满订阅队列
    for i in range(MAX_QUEUE + 5):
        await h.publish("t4", "progress", {"i": i})
    # 不抛异常；队列保持满
    assert q.qsize() == MAX_QUEUE
    assert h.buffer_size("t4") == 50


@pytest.mark.asyncio
async def test_event_ids_monotonic_across_tasks():
    h = TaskEventHub()
    await h.publish("a", "status", {})
    await h.publish("b", "status", {})
    await h.publish("a", "progress", {})
    events_a = h.get_task_events("a")
    ids = [e["id"] for e in events_a]
    assert ids[1] > ids[0] > 0
    assert h.get_task_events("b")[0]["id"] == ids[0] + 1


# ── replay_after（Last-Event-ID 补偿）────────────────────────


@pytest.mark.asyncio
async def test_replay_after_none_returns_all():
    h = TaskEventHub()
    await h.publish("t", "status", {})
    await h.publish("t", "result", {})
    events = await h.replay_after("t", None)
    assert [e.event for e in events] == ["status", "result"]


@pytest.mark.asyncio
async def test_replay_after_midstream():
    h = TaskEventHub()
    await h.publish("t", "status", {})
    all_events = await h.replay_after("t", None)
    mid_id = all_events[0].id
    await h.publish("t", "progress", {})
    events = await h.replay_after("t", mid_id)
    assert [e.event for e in events] == ["progress"]


@pytest.mark.asyncio
async def test_replay_after_unknown_task_empty():
    h = TaskEventHub()
    assert await h.replay_after("ghost", None) == []


# ── 快照与清理 ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_task_events_flat_dict():
    h = TaskEventHub()
    await h.publish("t", "status", {"x": 1})
    events = h.get_task_events("t")
    assert set(events[0]) == {"id", "event", "data", "ts"}
    assert h.get_task_events("ghost") == []


@pytest.mark.asyncio
async def test_clear_task():
    h = TaskEventHub()
    await h.publish("t", "status", {})
    await h.clear_task("t")
    assert h.buffer_size("t") == 0


# ── 2026-10-15 回归锁：多订阅者下的缓冲清理 ─────────────────────────
#
# 真缺陷：连接 finally 原先无条件调 `clear_task`。同一 task 被 2+ 客户端订阅时
# （多标签页 / 重连旧连接尚未断开），先断开的一方会清掉**共享**回放缓冲，
# 另一方之后用 Last-Event-ID 重连拿不到任何历史 —— 静默降级、不报错。
# 修法：新增 `clear_task_if_idle`（判空与清理同锁内完成），连接收尾改用它。


@pytest.mark.asyncio
async def test_clear_task_if_idle_keeps_buffer_while_other_subscriber_remains():
    """A 断开后缓冲必须保留（B 仍在订阅）——这是原缺陷的核心断言。"""
    h = TaskEventHub()
    await h.publish("multi", "status", {"n": 1})

    qa = await h.subscribe("multi")
    qb = await h.subscribe("multi")
    assert h.subscriber_count("multi") == 2
    assert h.buffer_size("multi") == 1

    # 客户端 A 断开（复刻 sse_events/ws_events 的 finally 顺序）
    await h.unsubscribe("multi", qa)
    await h.clear_task_if_idle("multi")

    # B 仍在订阅 → 缓冲不得被清
    assert h.subscriber_count("multi") == 1
    assert h.buffer_size("multi") == 1, "A 断开即清缓冲 → B 失去 Last-Event-ID 回放（原缺陷复现）"

    # B 也能继续收到实时事件
    await h.publish("multi", "status", {"n": 2})
    assert h.buffer_size("multi") == 2
    assert qb.qsize() >= 1

    # 最后一个订阅者断开 → 此时才允许清理
    await h.unsubscribe("multi", qb)
    await h.clear_task_if_idle("multi")
    assert h.subscriber_count("multi") == 0
    assert h.buffer_size("multi") == 0


@pytest.mark.asyncio
async def test_clear_task_if_idle_clears_when_no_subscriber():
    """无订阅者时按预期清理（防内存膨胀语义不变）。"""
    h = TaskEventHub()
    await h.publish("idle", "status", {})
    assert h.buffer_size("idle") == 1
    await h.clear_task_if_idle("idle")
    assert h.buffer_size("idle") == 0


@pytest.mark.asyncio
async def test_clear_task_still_unconditional():
    """`clear_task` 保持无条件清理语义（其他调用方与测试依赖）。"""
    h = TaskEventHub()
    await h.publish("force", "status", {})
    _q = await h.subscribe("force")
    await h.clear_task("force")
    assert h.buffer_size("force") == 0, "clear_task 应保持无条件清理"


# ── publish_task_event（同步入口）─────────────────────────────


@pytest.mark.asyncio
async def test_publish_task_event_with_loop():
    publish_task_event("t-sync", "status", {"ok": 1})
    assert len(_pending_sse_tasks) == 1
    await asyncio.sleep(0.05)
    assert hub.buffer_size("t-sync") == 1
    await await_pending_sse_tasks()


def test_publish_task_event_without_loop_drops():
    """无运行 loop（同步上下文）→ 丢弃不抛。"""
    publish_task_event("t-noop", "status", {})  # pytest 同步函数无 loop


@pytest.mark.asyncio
async def test_await_pending_empty_returns_immediately():
    await await_pending_sse_tasks(timeout=0.1)  # 空集不抛不停


@pytest.mark.asyncio
async def test_await_pending_waits_and_clears():
    publish_task_event("t-wait", "status", {})
    assert len(_pending_sse_tasks) == 1
    await await_pending_sse_tasks(timeout=2.0)
    assert len(_pending_sse_tasks) == 0
    assert hub.buffer_size("t-wait") == 1


# ── task_events_generator ─────────────────────────────────────


class FakeRequest:
    """模拟 Starlette Request：headers + is_disconnected。"""

    def __init__(self, headers: dict | None = None, disconnect_after: int = 0):
        self.headers = headers or {}
        self._disconnect_after = disconnect_after
        self._reads = 0

    async def is_disconnected(self) -> bool:
        self._reads += 1
        return self._reads > self._disconnect_after


@pytest.mark.asyncio
async def test_generator_replays_last_event_id_then_live(monkeypatch):
    import api.sse_events as se

    monkeypatch.setattr(se, "_HEARTBEAT_INTERVAL", 0.05)
    await hub.publish("tg1", "status", {"s": "pending"})
    await hub.publish("tg1", "progress", {"p": 50})
    all_ev = await hub.replay_after("tg1", None)
    last_id = all_ev[0].id  # 只回放第二条

    req = FakeRequest(headers={"Last-Event-ID": str(last_id)}, disconnect_after=3)
    chunks = [c async for c in task_events_generator("tg1", req)]
    joined = "".join(chunks)
    assert "event: progress" in joined  # Last-Event-ID 补偿回放
    assert "connected" in joined  # 初始连接确认


@pytest.mark.asyncio
async def test_generator_breaks_on_terminal_event(monkeypatch):
    import api.sse_events as se

    monkeypatch.setattr(se, "_HEARTBEAT_INTERVAL", 0.05)
    req = FakeRequest(headers={}, disconnect_after=30)

    async def _publish_terminal():
        await asyncio.sleep(0.05)
        await hub.publish("tg2", "result", {"url": "x"})

    task = asyncio.create_task(_publish_terminal())
    chunks = [c async for c in task_events_generator("tg2", req)]
    await task
    joined = "".join(chunks)
    assert "event: result" in joined


@pytest.mark.asyncio
async def test_generator_invalid_last_event_id_ignored(monkeypatch):
    """Last-Event-ID 非数字 → 视为无补偿，全量回放。"""
    import api.sse_events as se

    monkeypatch.setattr(se, "_HEARTBEAT_INTERVAL", 0.05)
    await hub.publish("tg3", "status", {})
    req = FakeRequest(headers={"Last-Event-ID": "not-a-number"}, disconnect_after=1)
    chunks = [c async for c in task_events_generator("tg3", req)]
    joined = "".join(chunks)
    assert "event: status" in joined  # 回放了全部历史


@pytest.mark.asyncio
async def test_generator_heartbeat_on_timeout(monkeypatch):
    """队列空闲超时 → 发心跳。"""
    import api.sse_events as se

    monkeypatch.setattr(se, "_HEARTBEAT_INTERVAL", 0.05)
    req = FakeRequest(headers={}, disconnect_after=3)
    chunks = [c async for c in task_events_generator("tg4", req)]
    joined = "".join(chunks)
    assert '"heartbeat"' in joined.replace("'", '"')


@pytest.mark.asyncio
async def test_generator_disconnect_records_cancellation():
    """客户端断开 → finally 清理缓冲 + 取消计数。"""
    from api.sse_stats import sse_stats

    sse_stats.reset()
    req = FakeRequest(headers={}, disconnect_after=0)  # 立即断开
    chunks = [c async for c in task_events_generator("tg5", req)]
    assert any("connected" in c for c in chunks)
    snap = sse_stats.snapshot()
    assert snap["cancelled_subscriptions"] == 1
    assert snap["total_subscriptions"] == 1


# ── v22 P2-1: 全局活动连接上限 ──────────────────────────────
@pytest.mark.asyncio
async def test_connection_limit_default_zero_unlimited():
    """max_connections=0（缺省）→ 任意数量订阅通过（向后兼容）。"""
    hub.set_max_connections(0)
    hub._subscribers.clear()
    for i in range(5):
        q = await hub.subscribe(f"limit-default-{i}")
        assert q is not None
    assert hub.active_subscription_count() == 5


@pytest.mark.asyncio
async def test_connection_limit_enforced_429():
    """max_connections=2 → 第 3 个订阅抛 ConnectionError（429 语义）。"""
    hub._subscribers.clear()
    hub.set_max_connections(2)
    await hub.subscribe("limit-a")
    await hub.subscribe("limit-b")
    with pytest.raises(ConnectionError):
        await hub.subscribe("limit-c")  # 超限
    # 关闭上限后恢复
    hub.set_max_connections(0)
    q = await hub.subscribe("limit-d")
    assert q is not None


@pytest.mark.asyncio
async def test_connection_limit_counts_active_only():
    """unsubscribe 释放名额 → 可再次订阅（按活动连接数而非累计数）。"""
    hub._subscribers.clear()
    hub.set_max_connections(1)
    q1 = await hub.subscribe("limit-release")
    assert hub.active_subscription_count() == 1
    await hub.unsubscribe("limit-release", q1)
    # 释放后可再次订阅（不被累计计数卡死）
    q2 = await hub.subscribe("limit-release")
    assert q2 is not None
    hub.set_max_connections(0)


@pytest.mark.asyncio
async def test_generator_limit_error_yields_429():
    """上限触发 → task_events_generator 产出 429 error 事件后终止（真端到端，勿退化）。"""
    hub._subscribers.clear()
    hub.set_max_connections(1)
    await hub.subscribe("limit-gen")  # 占满唯一名额
    # 用测试本地 FakeRequest（保持连接）驱动 generator——验证 429 分支真实产出（H1 修复，勿 se.FakeRequest）
    req = FakeRequest(headers={}, disconnect_after=99)
    chunks = [c async for c in task_events_generator("limit-gen-2", req)]
    joined = "".join(chunks)
    assert '"code": 429' in joined and "event: error" in joined
    hub.set_max_connections(0)


# ── v22 P1-3: SSE 心跳间隔参数化 ───────────────────────────
def test_heartbeat_interval_default_15():
    """缺省心跳 15s（向后兼容）。"""
    import api.sse_events as se

    se._HEARTBEAT_INTERVAL = 15.0
    assert se.heartbeat_interval() == 15.0


def test_set_heartbeat_interval_updates():
    """set_heartbeat_interval 装配有效值 → generator 心跳间隔更新。"""
    import api.sse_events as se

    se.set_heartbeat_interval(3.5)
    assert se.heartbeat_interval() == 3.5
    se.set_heartbeat_interval(15.0)  # 还原


def test_set_heartbeat_interval_invalid_ignored():
    """非法值（0/负/非数字）→ 保持既有心跳，不改变行为。"""
    import api.sse_events as se

    se.set_heartbeat_interval(5.0)
    se.set_heartbeat_interval(0)
    assert se.heartbeat_interval() == 5.0  # 0 忽略
    se.set_heartbeat_interval(-1)
    assert se.heartbeat_interval() == 5.0  # 负忽略
    se.set_heartbeat_interval("abc")
    assert se.heartbeat_interval() == 5.0  # 非数字忽略
    se.set_heartbeat_interval(15.0)  # 还原


# ── 调用点契约：连接收尾必须用「判空」版清理 ────────────────────────
#
# 上组测试验证 `clear_task_if_idle` **方法本身**的行为，但**测不到调用点**：
# 把生成器里的 `clear_task_if_idle` 改回 `clear_task`，那组测试照样全绿
# （实测变异确认）。故补本组，锁死两个连接收尾点都使用判空版。


def test_generator_finally_uses_idle_aware_clear():
    """task_events_generator 的 finally 必须调 `clear_task_if_idle`，不得用无条件 `clear_task`。"""
    import ast
    import inspect
    import textwrap

    src = textwrap.dedent(inspect.getsource(task_events_generator))
    tree = ast.parse(src)

    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in ("clear_task", "clear_task_if_idle"):
            called.add(node.attr)

    assert "clear_task_if_idle" in called, (
        "task_events_generator 未调用 clear_task_if_idle —— 多订阅者场景下会误清他人回放缓冲"
    )
    assert "clear_task" not in called, "task_events_generator 不应直接调用无条件 clear_task"


def test_ws_task_events_uses_idle_aware_clear():
    """ws_events 的任务 WS 收尾同样必须用判空版（同一缺陷的另一处调用点）。"""
    import inspect

    from api import ws_events

    src = inspect.getsource(ws_events)
    # 只看非注释行，避免说明性注释里的旧写法被误判
    code = "\n".join(ln.split("#", 1)[0] for ln in src.splitlines())
    assert "clear_task_if_idle" in code, "ws_events 收尾未使用 clear_task_if_idle"
    assert "hub.clear_task(" not in code, "ws_events 收尾仍有无条件 clear_task 调用"
