/**
 * useTaskProgress — 单任务实时进度 hook（P0-4）
 *
 * 为任务列表运行行 / 生成页提交卡提供「阶段徽章流转（queued→solving→generating）+ 简化进度条」。
 *
 * 数据源选型（最小接线，保留可换 SSE）：
 * - 主路径 = 轮询 `GET /v1/tasks/{id}`：可靠拿到顶层状态（pending/processing/completed/error/cancelled），
 *   命中终态即停。但 GET 响应（task_to_public）不含 status_detail/progress 字段（它们只在 SSE 事件负载），
 *   故轮询路径用 `mapStatusToDetail` 做状态映射兜底（pending→queued/5，终态→100）。
 * - 增强路径 = SSE 订阅 `/v1/tasks/{id}/events`（真实浏览器 EventSource 存在时才开，与 Generate 页
 *   既有 startTxtSse 同一通道）：收到 status 事件即用精确的 status_detail/progress（solving=30/generating=80）
 *   覆盖映射值；SSE 断线 / jsdom 无 EventSource → 纯轮询兜底，行为不变。
 *
 * 设计约束：
 * - 仅 `enabled && taskId` 时启动（列表页只对 pending/processing 行启用，避免已终态行空轮询）。
 * - 每轮请求带自增序号防竞态；卸载 / 停用即停轮询 + 关 SSE。
 * - 不做乐观状态机：终态一律以后端为准。
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchTask } from '../api';

export interface TaskProgressState {
  /** 顶层任务状态：pending/processing/completed/error/cancelled；null=尚未拉到 */
  status: string | null;
  /** 阶段徽章：queued/solving/generating/completed/cancelled；null=未知（渲染层回退「运行中」） */
  statusDetail: string | null;
  /** 阶段进度 0-100；null=未知（渲染层回退不确定进度条） */
  progress: number | null;
  /** 是否仍订阅中（运行中 + 已连上轮询/SSE） */
  running: boolean;
}

export interface UseTaskProgressOptions {
  /** 任务非运行态时跳过订阅（列表页只对 pending/processing 行启用） */
  enabled?: boolean;
  /** 轮询间隔 ms（默认 2000） */
  pollIntervalMs?: number;
}

const TERMINAL = new Set(['completed', 'error', 'cancelled']);

/** 运行态 → 阶段徽章/进度的兜底映射（轮询 /v1/tasks/{id} 只拿得到 status）。 */
function mapStatusToDetail(status: string): { statusDetail: string | null; progress: number | null } {
  switch (status) {
    case 'pending':
      return { statusDetail: 'queued', progress: 5 };
    case 'processing':
      return { statusDetail: null, progress: null };
    case 'completed':
      return { statusDetail: 'completed', progress: 100 };
    case 'cancelled':
      return { statusDetail: 'cancelled', progress: 100 };
    default:
      return { statusDetail: null, progress: null };
  }
}

export function useTaskProgress(taskId: string | null, options: UseTaskProgressOptions = {}): TaskProgressState {
  const { enabled = true, pollIntervalMs = 2000 } = options;
  const active = Boolean(taskId) && enabled;
  const [status, setStatus] = useState<string | null>(null);
  const [statusDetail, setStatusDetail] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [running, setRunning] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const seqRef = useRef(0);

  const stop = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    setRunning(false);
  }, []);

  useEffect(() => {
    if (!active) {
      stop();
      return;
    }
    const tId = taskId as string;
    const seq = ++seqRef.current;
    setRunning(true);

    // 轮询「不得降级覆盖」用的状态记忆（本次 effect 生命周期内有效）。
    // 背景：轮询 `GET /v1/tasks/{id}` 只拿得到顶层 status（该响应不含 status_detail/progress，
    // 二者仅存在于 SSE 事件负载）。若每轮 tick 都无条件 apply(mapStatusToDetail(...))，
    // 则 processing 映射出的 {null,null} 会把 SSE 刚写入的精确阶段（solving/30、generating/80）
    // **抹回「运行中」+ 无定值进度条** —— 表现为进度条每 2s 跳一次（用户可见缺陷，
    // 2026-10-16 由 Tasks.test.tsx 的失败 DOM 实证：aria-label="任务阶段：运行中" + 无 aria-valuenow）。
    //
    // ⚠ **不变量（改动此处前必读）**：本变量记录「最后一次写入 state 时所用的 status」，
    // 守卫依赖它等价于「当前保存的精确 detail 属于哪个 status」。当前调用图下两者成立
    // （SSE 的 apply 也写它）。**若将来在 SSE 路径写入粗粒度值**（例如只带 status 的帧），
    // 或**后端给 `TaskInfo` 补上 status_detail/progress**（verification-log 里记的那条
    // "独立决策项"），本守卫会反过来让**更新的轮询精确值被更旧的 SSE 值压住** ——
    // 那时应改为按「数据新鲜度」（时间戳/版本号）判定，而不是「status 是否变化」。
    let lastAppliedStatus: string | null = null;

    const apply = (s: string, detail: string | null, p: number | null) => {
      if (seq !== seqRef.current) return;
      lastAppliedStatus = s;
      setStatus(s);
      setStatusDetail(detail);
      setProgress(p);
    };

    const finish = (s: string) => {
      if (seq !== seqRef.current) return;
      if (TERMINAL.has(s)) apply(s, s === 'cancelled' ? 'cancelled' : s === 'completed' ? 'completed' : null, 100);
      stop();
    };

    const poll = async () => {
      try {
        const t = await fetchTask(tId);
        if (seq !== seqRef.current) return;
        if (TERMINAL.has(t.status)) {
          finish(t.status);
          return;
        }
        const mapped = mapStatusToDetail(t.status);
        // 兜底映射为空（典型：processing）且顶层状态未变 → 保留已知的更精确值，不降级覆盖。
        // 轮询的职责是「探测终态 + 无 SSE 时兜底」，不是用粗粒度信息覆盖精确信息。
        if (mapped.statusDetail === null && lastAppliedStatus === t.status) return;
        apply(t.status, mapped.statusDetail, mapped.progress);
      } catch {
        // 单轮轮询失败静默（网络抖动），下一轮继续；终态兜底由 SSE result/error 或后续轮询补
      }
    };

    void poll();
    timerRef.current = setInterval(() => {
      void poll();
    }, pollIntervalMs);

    // SSE 增强：仅真实浏览器（jsdom 无 EventSource → 直接走纯轮询）。同一通道与 Generate.startTxtSse 一致。
    if (typeof EventSource !== 'undefined') {
      try {
        const es = new EventSource(`/v1/tasks/${tId}/events`);
        esRef.current = es;
        const handleStatus = (ev: MessageEvent) => {
          if (seq !== seqRef.current) return;
          try {
            const data = JSON.parse(String((ev as MessageEvent).data ?? '{}')) as {
              status?: string;
              status_detail?: string;
              progress?: number;
            };
            if (data.status_detail || typeof data.progress === 'number' || data.status) {
              apply(
                data.status ?? 'processing',
                data.status_detail ?? null,
                typeof data.progress === 'number' ? data.progress : null,
              );
            }
          } catch {
            // 坏帧忽略
          }
        };
        // 终态事件（result/error）→ 立即拉一次权威状态收尾（poll 内部命中终态会 stop）
        const handleTerminal = () => {
          void poll();
        };
        const handleDisconnect = () => {
          if (esRef.current === es) {
            es.close();
            esRef.current = null;
          }
          // 2026-10-17 修（独立审查 R1）：断线必须**复位降级守卫**。
          // 否则轮询的粗粒度映射会被守卫永久抑制 → 徽章**冻结**在最后一个精确阶段
          // （如「求解中 30%」）且无「数据已失联」提示 —— 那不是降级而是**停滞**，
          // 用户更可能误判卡死而点取消/重试，制造重复上游调用。
          // 本文件头部契约（:10-12）明写「SSE 断线 → 纯轮询兜底，行为不变」，复位即恢复该语义。
          lastAppliedStatus = null;
        };
        es.addEventListener('status', handleStatus);
        es.addEventListener('result', handleTerminal);
        es.addEventListener('error', handleTerminal);
        es.onerror = handleDisconnect; // 断线：关 SSE，轮询兜底继续
      } catch {
        // EventSource 构造失败 → 纯轮询
      }
    }

    return () => {
      seqRef.current++;
      stop();
    };
  }, [active, taskId, pollIntervalMs, stop]);

  return { status, statusDetail, progress, running };
}

export default useTaskProgress;
