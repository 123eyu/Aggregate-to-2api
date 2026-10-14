import { usePolling } from './usePolling'

// /v1/stats —— 状态胶囊条（兼容旧 SectionStatus）
export function useStats() {
  return usePolling('/v1/stats', 10000)
}

// /v1/providers —— 提供商网格（兼容旧 SectionProviders）
export function useProviders() {
  return usePolling('/v1/providers', 60000)
}

// /v1/models —— 模型列表
export function useModels() {
  return usePolling('/v1/models', 60000)
}

// /v1/meta —— 站台信息
export function useMeta() {
  return usePolling('/v1/meta', 60000)
}

// /v1/chat/usage — 对话 Token 用量
export function useChatUsage() {
  return usePolling('/v1/chat/usage?period=24h', 30000)
}

// ── Spec 009 门户新增 ───────────────────────────────────────────────

/**
 * 画廊：GET /v1/gallery?limit=N（公开，无需 Key；limit ≤ 100）
 * 响应 { items, total, page, page_size, count }
 * 每次手动刷新（不轮询，避免无谓流量；提供 refresh）
 *
 * errorMessage：画廊区块独立文案——比通用"数据加载失败"更贴合用户预期，
 * 且避免把后端/网关故障的通用措辞直接搬到作品展示区造成困惑。
 */
export function useGallery(limit = 60, options = {}) {
  const opts = { immediate: true, intervalMs: 0, errorMessage: '灵感画廊暂时无法加载，请稍后重试', ...options }
  return usePolling(`/v1/gallery?limit=${limit}`, 0, opts)
}

/**
 * 模型目录（生图分组）：GET /v1/models
 * items: Record<provider, ImageModelInfo[]>（txt2img / img2img capabilities）
 */
export function useModelsOnce() {
  return usePolling('/v1/models', 0)
}
