import { describe, it, expect, vi, afterEach } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { usePolling } from '../composables/usePolling'

/**
 * v23.2 回归锁：usePolling 的错误语义必须是「面向用户的中文文案」，
 * 不得把原始异常（尤其 HTML 错误页导致的 JSON 解析栈）泄漏到 UI。
 *
 * 真实缺陷背景：后端/Nginx/CDN 返回 HTML 错误页时，旧实现 `res.json()` 抛
 * `Unexpected token '<', "<!DOCTYPE "... is not valid JSON`，被 GalleryWall
 * 直接渲染给用户。本组用例锁死新行为。
 */

const makeStub = (url: string, options: Record<string, unknown> = {}) => {
  let captured: ReturnType<typeof usePolling> | null = null
  const Comp = defineComponent({
    setup() {
      captured = usePolling(url, 0, options)
      return () => h('div', captured.error.value ?? '')
    },
  })
  return { Comp, get: () => captured! }
}

const mockFetchOnce = (impl: () => Promise<unknown>) => {
  vi.stubGlobal('fetch', vi.fn(impl))
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('usePolling — 错误归类不泄漏技术细节', () => {
  it('HTML 错误页（content-type text/html）→ 非预期格式文案，不含 JSON 解析栈', async () => {
    mockFetchOnce(async () => ({
      ok: true,
      headers: { get: (k: string) => (k.toLowerCase() === 'content-type' ? 'text/html; charset=utf-8' : null) },
      json: async () => {
        throw new SyntaxError("Unexpected token '<', \"<!DOCTYPE \"... is not valid JSON")
      },
      text: async () => '<!DOCTYPE html><html>502 Bad Gateway</html>',
    }))

    const { Comp, get } = makeStub('/v1/gallery?limit=60')
    mount(Comp)
    await nextTick()
    await new Promise((r) => setTimeout(r, 0))

    expect(get().error.value).toBe('服务返回了非预期格式，请稍后重试')
    expect(get().error.value).not.toContain('Unexpected token')
    expect(get().error.value).not.toContain('DOCTYPE')
    // 原始细节仍可用于调试
    expect(get().errorDetail.value).toContain('content-type')
  })

  it('HTTP 502 → 服务暂时不可用文案', async () => {
    mockFetchOnce(async () => ({
      ok: false,
      status: 502,
      headers: { get: () => 'text/html' },
      text: async () => '<html>Bad Gateway</html>',
    }))

    const { Comp, get } = makeStub('/v1/stats')
    mount(Comp)
    await nextTick()
    await new Promise((r) => setTimeout(r, 0))

    expect(get().error.value).toBe('服务暂时不可用，请稍后重试')
  })

  it('HTTP 429 → 限流文案', async () => {
    mockFetchOnce(async () => ({
      ok: false,
      status: 429,
      headers: { get: () => 'application/json' },
      text: async () => '{"error":"rate limited"}',
    }))

    const { Comp, get } = makeStub('/v1/gallery')
    mount(Comp)
    await nextTick()
    await new Promise((r) => setTimeout(r, 0))

    expect(get().error.value).toBe('请求过于频繁，请稍后重试')
  })

  it('网络失败（fetch reject）→ 网络连接失败文案', async () => {
    mockFetchOnce(async () => {
      throw new TypeError('Failed to fetch')
    })

    const { Comp, get } = makeStub('/v1/providers')
    mount(Comp)
    await nextTick()
    await new Promise((r) => setTimeout(r, 0))

    expect(get().error.value).toBe('网络连接失败，请检查网络后重试')
  })

  it('正常 JSON 响应 → error 归 null，data 正确填充', async () => {
    mockFetchOnce(async () => ({
      ok: true,
      headers: { get: (k: string) => (k.toLowerCase() === 'content-type' ? 'application/json' : null) },
      json: async () => ({ items: [1, 2, 3], total: 3 }),
    }))

    const { Comp, get } = makeStub('/v1/gallery')
    mount(Comp)
    await nextTick()
    await new Promise((r) => setTimeout(r, 0))

    expect(get().error.value).toBeNull()
    expect(get().errorDetail.value).toBeNull()
    expect(get().data.value).toEqual({ items: [1, 2, 3], total: 3 })
  })

  it('content-type 缺失时仍尝试解析 JSON（兼容不设头的服务）', async () => {
    mockFetchOnce(async () => ({
      ok: true,
      headers: { get: () => null },
      json: async () => ({ ok: true }),
    }))

    const { Comp, get } = makeStub('/v1/meta')
    mount(Comp)
    await nextTick()
    await new Promise((r) => setTimeout(r, 0))

    expect(get().error.value).toBeNull()
    expect(get().data.value).toEqual({ ok: true })
  })

  it('transform 抛错 → 归类为解析失败，不得误报为网络失败', async () => {
    mockFetchOnce(async () => ({
      ok: true,
      headers: { get: (k: string) => (k.toLowerCase() === 'content-type' ? 'application/json' : null) },
      json: async () => ({ weird: 'shape' }),
    }))

    const { Comp, get } = makeStub('/v1/gallery', {
      transform: () => {
        throw new TypeError('cannot read items of undefined')
      },
    })
    mount(Comp)
    await nextTick()
    await new Promise((r) => setTimeout(r, 0))

    expect(get().error.value).toBe('数据解析失败，请稍后重试')
    expect(get().error.value).not.toContain('网络')
  })

  it('errorMessage 选项可覆盖默认文案', async () => {
    mockFetchOnce(async () => ({
      ok: false,
      status: 500,
      headers: { get: () => 'application/json' },
      text: async () => '{}',
    }))

    const { Comp, get } = makeStub('/v1/stats', { errorMessage: '画廊暂时无法加载' })
    mount(Comp)
    await nextTick()
    await new Promise((r) => setTimeout(r, 0))

    // 关键断言：自定义文案必须真正替换默认归类文案（此前该用例只断言 Comp 为真，属空转）
    expect(get().error.value).toBe('画廊暂时无法加载')
    expect(get().error.value).not.toBe('服务暂时不可用，请稍后重试')
  })
})
