import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'

// P-UI-5: vendor 分包 —— react 系 / router / 图表库分离，配合 App.tsx 路由懒加载
// base=/admin/ —— 后端以 StaticFiles 挂载于 /admin，资源必须用该前缀（否则根路径 404）
//
// v6.3.0: 版本号不再硬编码在前端组件，改为 build-time 从 package.json 注入 __APP_VERSION__，
// 侧栏 footer / 任何页面展示的版本号随构建自动更新，杜绝「代码注释 v6.3.4 / 显示 v4.3.3」式漂移。
const pkg = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf-8'))

export default defineConfig({
  base: '/admin/',
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'scheduler'],
          'vendor-router': ['react-router-dom'],
          'vendor-chart': ['recharts'],
        },
      },
    },
  },
  server: {
    proxy: {
      '/v1': 'http://127.0.0.1:8100',
      '/metrics': 'http://127.0.0.1:8100',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    // P1-14：Playwright e2e/ 目录归 @playwright/test 跑（npm run test:e2e），
    // vitest 不得误收（Playwright Test 不允许被 vitest import）
    exclude: ['**/node_modules/**', 'e2e/**'],
    // api.ts / useApi.ts / Feedback.tsx 等被测试模块依赖 CSS 或 window 全局，
    // 仅跑纯逻辑与 hook 测试；CSS 模块由 jsdom 忽略。
    css: false,
    // isolate=false：本项目位于非 ASCII 路径（Desktop/2api目录/...）时，
    // vitest 4 的隔离 worker 启动会在 60s 后超时
    // （`[vitest-pool-runner]: Timeout waiting for worker to respond`，
    //  URL 中 `2api目录` 被编码为 2api%E7%9B%AE%E5%BD%95），28 个 worker 全挂、0 测试执行。
    //
    // 2026-10-15 修正：此前本注释写「测试间通过 src/test/setup.ts 的 beforeEach 清理」，
    // **但 setup.ts 当时根本没有任何清理逻辑** —— 注释与实现不符，导致 CI 上稳定失败：
    //   CostsPage.test.tsx「按模型」用例 → Found multiple elements with role "button"
    //   （上个用例 render 的组件残留在 document 上，isolate:false 下无人清理）
    // 现已在该文件显式注册 `afterEach(cleanup)`。**本设置与那个 cleanup 是配套的，
    // 改动任一方都要同时检查另一方。**
    isolate: false,
    // forks（独立子进程）：每个测试进程有独立堆，不易受项目全局
    // NODE_OPTIONS=--max-old-space-size=512 挤压而 OOM。
    // 注意：vitest 4 已移除 `test.poolOptions`（实测跑时打 DEPRECATED 警告并被忽略），
    // 不要再写 poolOptions.forks.execArgv —— 无效配置会让人误以为内存已调大。
    pool: 'forks',
    // setup/import 变慢（实测 setup 累计 199s、environment 1161s），5s 默认超时不够 →
    // 放宽到 20000ms（与此前 `--testTimeout=20000` 的手工口径一致）。
    testTimeout: 20000,
    hookTimeout: 20000,
    coverage: {
      // 仅度量高价值核心模块（任务要求 ≥90%）；不强制全局阈值以免阻塞 CI。
      include: ['src/api.ts', 'src/components/Feedback.tsx', 'src/hooks/useApi.ts'],
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
    },
  },
})
