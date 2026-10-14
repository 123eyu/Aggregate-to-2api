import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { readFileSync } from 'node:fs'

const pkg = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf-8'))

export default defineConfig({
  plugins: [vue()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['src/test/setup.ts'],
    include: ['src/**/*.test.ts'],
    // isolate=false：本项目位于非 ASCII 路径（Desktop/2api目录/...）时，
    // vitest 4 的隔离 worker 启动会在 60s 后超时
    // （`[vitest-pool-runner]: Timeout waiting for worker to respond`，
    //  URL 中 `2api目录` 被编码为 2api%E7%9B%AE%E5%BD%95）。
    // 测试间通过 setup.ts 的 beforeEach 清理 localStorage 保证独立，
    // 不依赖 isolate；关掉可稳定跑通（实测 12/12 通过，~30s）。
    isolate: false,
    pool: 'threads',
  },
})
