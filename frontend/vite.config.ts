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
    // ── isolate 必须为 true：这是「跨文件 mock 实例串味」的唯一防线 ──────────────
    //
    // 2026-10-16（flaky 根治）实证根因：isolate=false 时同一 worker 内的多个测试文件
    // 共享模块实例，而 vi.mock 的假模块是**按文件注册**的 —— 后跑文件里被缓存的组件
    // 闭包仍指向**上一个文件遗留的 mock 实例**，本文件新注册的 mock 对它完全无效。
    // 强制两文件同 worker 连跑的实测（`--no-file-parallelism`）：
    //   GalleryAlbum → Gallery：Gallery.test.tsx **4 用例全红**
    //     `TestingLibraryElementError: Unable to find an element with the alt text: test prompt`
    //     （DOM 里其实是 GalleryAlbum 的 2 项数据：`imagefree/default` 徽章 +「已加载全部 2 张」）
    //   Gallery → GalleryAlbum：GalleryAlbum **7 用例全红**
    //     （`Cannot read properties of undefined (reading 'total')`）
    // 这两个文件是全仓库唯一「同一组件 + 同一 vi.mock 目标」的组合（其余 26 文件不受影响，
    // 全量单 worker 实测：2 failed | 26 passed，失败仅此一对）。
    //
    // 这正是 CI 上「同一 commit 时红时绿」的机制：文件→worker 的分配取决于哪个 worker 先
    // 空闲，4 vCPU 的 runner 上两个 Gallery 文件偶尔落进同一 worker → 后跑者必红；
    // 本机 16 vCPU 几乎不会同组，所以本地长期复现不到。
    //
    // ⚠ **更正（2026-10-17）**：本段原先写「2026-10-16 复测…**未复现**该超时」——
    // **那是失实的**，我实测复现了：`isolate:true` + **默认并发**下 28 个文件全部
    // worker 启动超时（`28 errors / 0 tests`，套件完全不可用）。准确表述是：
    //   · `isolate:false` + 默认并发 → 跑得起来，但有跨文件 mock 串味（见上）
    //   · `isolate:true`  + 默认并发 → **28 errors / 0 tests**
    //   · `isolate:true`  + `maxWorkers:2` → 28 files / 300 passed
    // 即那个超时**依然存在**，只是被下面这行 `maxWorkers:2` 压住了 —— 两者是**配套**的。
    // （该失实陈述源于代理记录，我在 `.wolf/buglog.json` bug-025 里已更正，
    //   但当时**漏改本文件**，属本批自己列为「文字与实现不符」的同类问题。）
    //
    // 配套提醒：本设置与 src/test/setup.ts 的 `afterEach(cleanup)` 仍是配套的 ——
    // isolate 管**文件之间**的模块/环境隔离，文件内**用例之间**的 DOM 清理靠那个 cleanup。
    isolate: true,
    // forks（独立子进程）：每个测试进程有独立堆，不易受项目全局
    // NODE_OPTIONS=--max-old-space-size=512 挤压而 OOM。
    // 注意：vitest 4 已移除 `test.poolOptions`（实测跑时打 DEPRECATED 警告并被忽略），
    // 不要再写 poolOptions.forks.execArgv —— 无效配置会让人误以为内存已调大。
    pool: 'forks',
    // ── 并发上限（2026-10-16，与 isolate:true 配套的**必需**项）────────────────
    // isolate:true 下每个测试文件都要重启一次 worker 环境，启动成本显著高于
    // isolate:false。而 vitest 的 worker 启动有 60s 内部硬超时
    // （`[vitest-pool-runner]: Timeout waiting for worker to respond`）。
    //
    // **实测（口径已标清，勿混用）**：
    //   · 本机 Windows / Node 25 / 默认并发 + isolate:true
    //       → **28 errors / 0 tests**（全部 worker 启动超时，套件完全不可用）
    //   · 本机 Windows / Node 25 / **maxWorkers:2** + isolate:true
    //       → **28 files / 300 passed**，墙钟约 **488s**
    //   · **CI（ubuntu-latest，4 vCPU，Node 20，读的就是本文件）**
    //       → vitest 步骤 **仅 15s**（Actions API 实测 started_at→completed_at）
    //
    // ⚠ **不要把 488s 与 15s 当成「同一配置的性能对比」**：平台/路径/Node 版本全不同。
    // 尤其**「非 ASCII 路径拖慢 worker 启动」这条推断没有证据支持** ——
    // CI 是 ASCII 路径（`/home/runner/work/...`）所以不能直接类比，
    // 而本机 488s 主要来自 Windows 文件系统 + `isolate:true` 的每文件环境重建。
    // 结论：**maxWorkers:2 在本机是「能不能跑」的必需项；在本机之外未见副作用**
    // （CI 实测 15s，未受该限流拖累）。
    //
    // 曾试过的替代方案：关掉 isolate（isolate:false）能让默认并发跑起来，
    // 但那会引入**跨文件 mock 实例串味**（同 worker 内多个文件共享模块实例，
    // 而 vi.mock 按文件注册 → 后跑文件的组件闭包仍指向上个文件遗留的 mock 实例）
    // —— 即 CI 上「同一 commit 时而红时而绿」的根因。
    // 因此**不关隔离**，改为降低并发让 worker 能在超时前起来。
    maxWorkers: 2,
    // setup/import 变慢（实测 setup 累计 199s、environment 1161s），5s 默认超时不够 →
    // 放宽到 20000ms（与此前 `--testTimeout=20000` 的手工口径一致）。
    testTimeout: 20000,
    hookTimeout: 20000,
    coverage: {
      // 仅度量高价值核心模块（任务要求 ≥90%）；不强制全局阈值以免阻塞 CI。
      // ⚠ 更正（2026-10-17）：原首项写 `'src/api.ts'` —— 该**文件不存在**
      // （前端 API 层早已拆成包 `frontend/src/api/`，含 core/misc/tasks/chat/agent/
      //   providers/security/index 共 8 个文件）。原写法会让 `npm run test:coverage`
      // 对 API 层**静默无覆盖数据**（glob 匹配不到任何文件，不报错）。
      include: ['src/api/**/*.ts', 'src/components/Feedback.tsx', 'src/hooks/useApi.ts'],
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
    },
  },
})
