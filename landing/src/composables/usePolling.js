import { ref, onMounted, onBeforeUnmount } from 'vue'

/**
 * 轮询数据源 hook。
 * - 同源相对路径 /v1/...（base 空字符串）
 * - 每次请求都在 try/catch 中，失败不抛错，写入 error 并保留上次 data
 * - 卸载时清空定时器
 *
 * 错误语义（v23.2 修订）：`error` 一律为**面向用户的可读文案**，不再是
 * 原始异常字符串。此举修复真实缺陷：后端/Nginx/CDN 在 5xx 或超时时常返回
 * HTML 错误页（`<!DOCTYPE html>...`），旧实现直接 `res.json()` 并把
 * `Unexpected token '<', "<!DOCTYPE "... is not valid JSON` 渲染到界面上，
 * 属技术黑话泄漏。现改为按失败类型归类为中文提示，原始细节留在
 * `errorDetail`（供控制台/调试，不直接展示）。
 *
 * @param {string} url 相对路径，如 '/v1/stats'
 * @param {number} intervalMs 轮询间隔（0 = 不轮询，仅立即取一次）
 * @param {object} options
 * @param {function} [options.transform] 对响应做可选归一化
 * @param {boolean} [options.immediate=true] 是否挂载后立即拉取
 * @param {string} [options.errorMessage] 自定义用户态错误文案（默认按类型归类）
 */
export function usePolling(url, intervalMs, options = {}) {
  const { transform, immediate = true, errorMessage } = options
  const data = ref(null)
  const error = ref(null)
  /** 原始错误细节，仅供调试（如 console），不绑定到模板。 */
  const errorDetail = ref(null)
  const loading = ref(!!immediate)
  let timer = null

  /**
   * 把任意异常归类为面向用户的文案。
   * 保留分类而非直接展示 e.message，避免 HTML 错误页 / JSON 解析栈泄漏到 UI。
   */
  function toUserMessage(e) {
    if (e && e.__kind === 'http') {
      const s = e.status
      if (s === 401 || s === 403) return errorMessage || '无权访问该数据（需要管理凭据）'
      if (s === 404) return errorMessage || '接口不存在或已下线'
      if (s === 429) return errorMessage || '请求过于频繁，请稍后重试'
      if (s >= 500) return errorMessage || '服务暂时不可用，请稍后重试'
      return errorMessage || `请求失败（HTTP ${s}）`
    }
    if (e && e.__kind === 'parse') return errorMessage || '服务返回了非预期格式，请稍后重试'
    if (e && e.__kind === 'transform') return errorMessage || '数据解析失败，请稍后重试'
    if (e && e.__kind === 'network') return errorMessage || '网络连接失败，请检查网络后重试'
    return errorMessage || '数据加载失败，请稍后重试'
  }

  async function fetchOnce() {
    try {
      const res = await fetch(url, { headers: { Accept: 'application/json' } })
      if (!res.ok) {
        const e = new Error(`HTTP ${res.status}`)
        e.__kind = 'http'
        e.status = res.status
        throw e
      }

      // 内容类型校验：非 JSON 响应（常见于反代/网关的 HTML 错误页）不尝试解析，
      // 直接归为 parse 类，避免把 `Unexpected token '<'` 抛给用户。
      const ctype = (res.headers.get('content-type') || '').toLowerCase()
      const looksJson = ctype.includes('json')
      if (ctype && !looksJson) {
        const e = new Error(`unexpected content-type: ${ctype}`)
        e.__kind = 'parse'
        throw e
      }

      let json
      try {
        json = await res.json()
      } catch (pe) {
        const e = new Error('response body is not valid JSON')
        e.__kind = 'parse'
        e.cause = pe
        throw e
      }

      // transform 失败须与网络失败区分：否则调用方会看到"网络连接失败"而误判为断网
      // （实际是响应结构不符合预期）。独立 __kind 便于归类。
      let normalized
      try {
        normalized = transform ? transform(json) : json
      } catch (te) {
        const e = new Error('transform threw')
        e.__kind = 'transform'
        e.cause = te
        throw e
      }

      data.value = normalized
      error.value = null
      errorDetail.value = null
    } catch (e) {
      // fetch 本身失败（DNS/断网/CORS/超时中止）无 __kind
      if (e && !e.__kind) e.__kind = 'network'
      error.value = toUserMessage(e)
      errorDetail.value = e && e.message ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  function start() {
    if (timer) clearInterval(timer)
    if (intervalMs > 0) timer = setInterval(fetchOnce, intervalMs)
  }

  function stop() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  onMounted(() => {
    if (immediate) fetchOnce()
    start()
  })
  onBeforeUnmount(stop)

  return { data, error, errorDetail, loading, fetchOnce, start, stop }
}
