// P0-4 前端部分测试：任务实时进度可视化 + 幂等取消 + 一键重试。
// 风格对齐 GalleryAlbum.test.tsx（vi.mock('../api') + act flush + IntersectionObserver stub 惯例）。
//
// jsdom 无 EventSource：默认走 useTaskProgress 轮询兜底路径；本文件 stub 一个最小 EventSource
// 以验证 SSE 精确阶段徽章流转（solving/generating + progress）在真实浏览器路径下的渲染。
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, act, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { TasksPage } from '../pages/Tasks';
import type { Task } from '../api';
import { fetchTasks, fetchTask, cancelTask, retryTask, notify } from '../api';

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api')>();
  return {
    ...actual,
    fetchTasks: vi.fn(),
    fetchTask: vi.fn(),
    cancelTask: vi.fn(),
    retryTask: vi.fn(),
    notify: vi.fn(),
  };
});

// ── jsdom 最小 EventSource stub：登记实例 + 手动 dispatch 事件（验证 SSE 阶段流转用） ──
class EventSourceStub {
  static instances: EventSourceStub[] = [];
  listeners: Record<string, ((ev: MessageEvent) => void)[]> = {};
  onerror: ((ev: Event) => void) | null = null;
  closed = false;
  constructor(public url: string) {
    EventSourceStub.instances.push(this);
  }
  addEventListener(type: string, cb: (ev: MessageEvent) => void) {
    (this.listeners[type] ??= []).push(cb);
  }
  removeEventListener(): void {}
  close() {
    this.closed = true;
  }
  dispatch(type: string, data: unknown) {
    (this.listeners[type] ?? []).forEach(cb => cb({ data: JSON.stringify(data) } as MessageEvent));
  }
}

function task(id: string, status: string, extra: Partial<Task> = {}): Task {
  return {
    id,
    status,
    prompt: 'a cat',
    image_url: null,
    error: null,
    duration_sec: null,
    created_at: 1700000000,
    model: 'imagefree/default',
    ...extra,
  };
}

// jsdom 无 EventSource：模块作用域 stub 一次（沿用 GalleryAlbum 对 IntersectionObserver 的惯例），
// 使所有用例都能走到「SSE 增强 + 轮询兜底」双路径。
if (typeof EventSource === 'undefined') {
  vi.stubGlobal('EventSource', EventSourceStub);
}

function list(items: Task[]) {
  return { items, total: items.length };
}

async function flush() {
  await act(async () => {});
}

beforeEach(() => {
  vi.clearAllMocks();
  EventSourceStub.instances = [];
});

afterEach(() => {
  // v20.3.1 flaky 根治：restoreAllMocks 会还原 vi.stubGlobal('EventSource')，
  // 并行测试文件间导致 EventSource 被还原为 undefined → SSE dispatch 失败。
  // 改用 clearAllMocks（只清 mock 调用/实现，不清全局 stub）。
  vi.clearAllMocks();
  EventSourceStub.instances = [];
  // 「SSE 阶段流转」用例装了假定时器（见该用例注释）：此处无条件还原，避免用例中途
  // 失败时假定时器泄漏到后续用例。
  vi.useRealTimers();
});

describe('Tasks 页面 P0-4 进度可视化 + 取消/重试', () => {
  it('processing 行显示阶段徽章/进度条：轮询兜底「运行中」→ SSE 事件流转到 solving/generating', async () => {
    // ── 预存并行 flaky 根治（2026-10-16）───────────────────────────────────
    // 本用例先在轮询路径断言「运行中」，再用 SSE 事件把阶段推到 solving(30)/generating(80)。
    // 但 useTaskProgress 每 2000ms 轮询一次 `GET /v1/tasks/{id}`，而 GET 响应**不含**
    // status_detail（见该 hook 文档注释）→ mapStatusToDetail('processing') 返回 {null,null}，
    // 会把 SSE 刚写入的「求解中/30」**清回「运行中」/无定值进度条**。
    // 失败时的 DOM 实证（CI/本机并行满载）：
    //   `aria-label="任务阶段：运行中"` + progressbar 无 aria-valuenow
    // 于是成败只取决于「事件派发→断言」这段是否恰好跑在两次 tick 之间 —— 机器一慢
    // （并行 16 个 jsdom worker、CI 4 vCPU）就跨过 2s 边界随机红。原配置（isolate:false +
    // 并行）同样复现，故与本轮 isolate 修复无关，属独立预存 flake
    // （docs/verification-log.md 旧记录：「全量 2 失败为预存并行 flaky」）。
    // 修法：固定定时器 —— 轮询只在 mount 时跑一次（`void poll()` 是直接调用，不依赖定时器），
    // interval 不再自行触发，断言只考察 SSE 路径。断言强度不变（仍要求 solving/30 与
    // generating/80 两个阶段都真的渲染出来）。afterEach 统一还原真实定时器。
    vi.useFakeTimers();
    fetchTasks.mockResolvedValue(list([task('t1', 'processing')]));
    fetchTask.mockResolvedValue(task('t1', 'processing'));
    render(<MemoryRouter><TasksPage /></MemoryRouter>);
    await flush();

    // 轮询路径：status=processing 无精确子阶段 → 回退「运行中」徽章 + 不确定进度条（progressbar 无 valuenow）
    const runningLabel = screen.getByText('运行中');
    expect(runningLabel).toBeInTheDocument();
    const bar = screen.getByRole('progressbar');
    expect(bar).toBeInTheDocument();
    expect(bar).not.toHaveAttribute('aria-valuenow');

    // SSE 路径：status 事件携带 solving=30 → 阶段徽章流转 + 定值进度条
    const es = EventSourceStub.instances[EventSourceStub.instances.length - 1];
    expect(es).toBeTruthy();
    await act(async () => {
      es.dispatch('status', { status: 'processing', status_detail: 'solving', progress: 30 });
    });
    expect(screen.getByText('求解中')).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '30');

    // 继续流转 generating=80
    await act(async () => {
      es.dispatch('status', { status: 'processing', status_detail: 'generating', progress: 80 });
    });
    expect(screen.getByText('生成中')).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '80');
  });

  it('processing 行点「取消」→ 调 cancelTask + 行状态更新为 cancelled + 按钮消失', async () => {
    fetchTasks.mockResolvedValue(list([task('t1', 'processing')]));
    fetchTask.mockResolvedValue(task('t1', 'processing'));
    cancelTask.mockResolvedValue({ task_id: 't1', status: 'cancelled', cancelled: true });
    render(<MemoryRouter><TasksPage /></MemoryRouter>);
    await flush();

    fireEvent.click(screen.getByRole('button', { name: /取消/ }));
    await flush();

    expect(cancelTask).toHaveBeenCalledWith('t1');
    expect(notify).toHaveBeenCalledWith(expect.stringContaining('已取消'), 'success');
    // 行状态徽章变 cancelled
    expect(screen.getByText('已取消')).toBeInTheDocument();
    expect(screen.queryByText('处理中')).not.toBeInTheDocument();
    // 已终态行不再显示取消按钮（防重复点击已由 loading 态 + 移除按钮双保险）
    expect(screen.queryByRole('button', { name: /取消/ })).not.toBeInTheDocument();
  });

  it('error 行点「重试」→ 调 retryTask + toast 新任务已提交', async () => {
    fetchTasks.mockResolvedValue(list([task('t1', 'error')]));
    retryTask.mockResolvedValue({ task_id: 't2', source_task_id: 't1', status: 'queued' });
    render(<MemoryRouter><TasksPage /></MemoryRouter>);
    await flush();

    expect(screen.getByText('失败')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /重试/ }));
    await flush();

    expect(retryTask).toHaveBeenCalledWith('t1');
    expect(notify).toHaveBeenCalledWith(expect.stringContaining('重试已提交'), 'success');
  });

  it('幂等取消：任务已被终态 → cancelled=false → 提示已终态不报错 + 行状态同步为终态', async () => {
    fetchTasks.mockResolvedValue(list([task('t1', 'processing')]));
    fetchTask.mockResolvedValue(task('t1', 'processing'));
    cancelTask.mockResolvedValue({ task_id: 't1', status: 'completed', cancelled: false });
    render(<MemoryRouter><TasksPage /></MemoryRouter>);
    await flush();

    fireEvent.click(screen.getByRole('button', { name: /取消/ }));
    await flush();

    expect(cancelTask).toHaveBeenCalledWith('t1');
    // 幂等命中：info 提示已终态，非 error
    expect(notify).toHaveBeenCalledWith(expect.stringContaining('终态'), 'info');
    expect(notify).not.toHaveBeenCalledWith(expect.anything(), 'error');
    // 行状态徽章同步为后端返回的当前终态
    expect(screen.getByText('已完成')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /取消/ })).not.toBeInTheDocument();
  });
});
// ── 轮询不得降级覆盖 SSE 的精确阶段（2026-10-16 产品缺陷回归锁）──────────
//
// 真缺陷（非 flaky）：`useTaskProgress` 的轮询每 tick 都无条件
// `apply(mapStatusToDetail(t.status))`，而 `GET /v1/tasks/{id}` 的响应
// **不含 status_detail/progress**（二者只在 SSE 事件负载里，见 TaskInfo）
// → processing 映射出 {null,null} → 把 SSE 刚写入的「求解中/30」抹回
// 「运行中」+ 无定值进度条。用户看到的就是**进度条每 2 秒跳一次**。
//
// 与上一节用例的区别：那条用 `vi.useFakeTimers()` 把轮询 interval 禁掉了
// （只留 mount 时的直接 poll），因此它**根本碰不到降级覆盖**这条路径。
// 本节用**真定时器**，主动触发一次 2000ms tick 来断言精确阶段不丢失。
describe('Tasks 进度条：轮询 tick 不得把 SSE 的精确阶段降级覆盖', () => {
  it('SSE 写入 solving/30 后再过一次轮询 tick，仍保持「求解中」+ 30', async () => {
    vi.useRealTimers(); // 本用例需要真实的 setInterval（默认轮询间隔 2000ms）
    fetchTasks.mockResolvedValue(list([task('t1', 'processing')]));
    // 轮询响应刻意**不含** status_detail/progress —— 与真实后端一致
    fetchTask.mockResolvedValue(task('t1', 'processing'));
    render(<MemoryRouter><TasksPage /></MemoryRouter>);
    await flush();

    // 先等 mount 时的直接 poll 落地（轮询路径兜底：「运行中」+ 无定值进度条）
    expect(screen.getByText('运行中')).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).not.toHaveAttribute('aria-valuenow');

    // SSE 推精确阶段
    const es = EventSourceStub.instances[EventSourceStub.instances.length - 1];
    expect(es).toBeTruthy();
    await act(async () => {
      es.dispatch('status', { status: 'processing', status_detail: 'solving', progress: 30 });
    });
    expect(screen.getByText('求解中')).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '30');

    // 越过一个轮询周期（>2000ms）：轮询仍会成功返回 processing，
    // 但**不得**用它映射出的 {null,null} 覆盖已知的精确阶段。
    await act(async () => {
      await new Promise(r => setTimeout(r, 2200));
    });
    expect(screen.getByText('求解中')).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '30');
  });
});

// ── SSE 断线后不得「冻结」在最后一个精确阶段（2026-10-17 独立审查 R1）──────
//
// 真缺陷（本批自身引入）：降级守卫 `lastAppliedStatus` 若在断线时**不复位**，
// 则轮询的粗粒度映射被永久抑制 → 徽章**停滞**在最后一个精确阶段（「求解中 30%」），
// 且无「数据已失联」提示。那不是降级而是停滞 —— 用户更可能误判卡死而点取消/重试，
// 制造重复上游调用。本文件头部契约明写「SSE 断线 → 纯轮询兜底，行为不变」。
describe('Tasks 进度条：SSE 断线后必须回落到轮询（不得冻结）', () => {
  it('断线后过一次轮询 tick，徽章回到轮询口径（不再停留在精确阶段）', async () => {
    vi.useRealTimers();
    fetchTasks.mockResolvedValue(list([task('t1', 'processing')]));
    fetchTask.mockResolvedValue(task('t1', 'processing')); // 轮询口径：无精确子阶段
    render(<MemoryRouter><TasksPage /></MemoryRouter>);
    await flush();

    // SSE 推精确阶段
    const es = EventSourceStub.instances[EventSourceStub.instances.length - 1];
    await act(async () => {
      es.dispatch('status', { status: 'processing', status_detail: 'solving', progress: 30 });
    });
    expect(screen.getByText('求解中')).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '30');

    // 断线：stub 的 onerror 即 handleDisconnect
    await act(async () => {
      es.onerror?.(new Event('error'));
    });
    expect(es.closed).toBe(true);

    // 越过一个轮询周期 → 轮询应恢复更新（回到「运行中」+ 无定值进度条）
    await act(async () => {
      await new Promise(r => setTimeout(r, 2200));
    });
    expect(screen.getByText('运行中')).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).not.toHaveAttribute('aria-valuenow');
  });
});
