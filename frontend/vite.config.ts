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
    // ── 关于「非 ASCII 路径下隔离 worker 启动 60s 超时」的**结论订正史** ──────────
    // 这段结论我反复改了三次，把经过写清楚，避免下个会话再翻烧饼：
    //
    //   ① 原注释（2026-10-14，34d9dbd）：为绕开该超时 → 关隔离（isolate:false）。
    //   ② 代理复测（2026-10-16）：**未复现**该超时（全量 28 文件 2m28s 正常）→ 开隔离。
    //   ③ 我据一次实测（`28 errors / 0 tests`）写下「更正：该超时**依然存在**」。
    //   ④ **再订正（2026-10-17，独立验证线程 + 我本人重测）：③ 是错的。**
    //
    // **③ 那次 `28 errors / 0 tests` 是「机器负载」伪影**，不是 isolate 或路径的属性 ——
    // 当时我并行开着 3 个正在跑 vitest 的子代理（CPU ≈95%）。
    // 独立验证线程在同一台机上跑 **4 组组合（默认并发 / maxWorkers:2 × 堆 512/不设）
    // 全部 28 passed / 300 passed**；我本人在 CPU ≈80% 下重测
    // `--maxWorkers=24`（=默认）→ **28 文件 / 300 passed**（仅 1 例 `CostsPage 导出 CSV`
    // 因 20s 单测超时失败，墙钟 103s —— 仍是**负载**型，非 worker 启动失败）。
    //
    // **这与 HEAD `79a5374` 已记录的陷阱完全一致**：
    // 「vitest worker 启动对**机器负载**敏感（换 pool 无效的误判陷阱）」——
    // 正确响应是**查负载**，而不是据此推断某个配置属性或改 pool。
    // 我 ③ 正是又踩了它一次。**故：会读到此处的你，遇到 `no tests` 先 `psutil` 看 CPU。**
    //
    // 配套提醒：本设置与 src/test/setup.ts 的 `afterEach(cleanup)` 仍是配套的 ——
    // isolate 管**文件之间**的模块/环境隔离，文件内**用例之间**的 DOM 清理靠那个 cleanup。
    isolate: true,
    // forks（独立子进程）：每个测试进程有独立堆，不易受项目全局
    // NODE_OPTIONS=--max-old-space-size=512 挤压而 OOM。
    // 注意：vitest 4 已移除 `test.poolOptions`（实测跑时打 DEPRECATED 警告并被忽略），
    // 不要再写 poolOptions.forks.execArgv —— 无效配置会让人误以为内存已调大。
    pool: 'forks',
    // ── 关于 `maxWorkers`：**已移除**（2026-10-17）──────────────────────────
    // 本行原为 `maxWorkers: 2`，理由写成「isolate:true + 默认并发 → 28 errors / 0 tests，
    // 套件完全不可用」。**该结论是错的**（机器负载伪影，见上面那段订正史），
    // 且独立验证线程实测四组组合全部通过：
    //
    //   配置值 maxWorkers:2   → 28 passed / 300 passed，**511s**
    //   `--maxWorkers=24`（默认）→ 28 passed / 300 passed，**108s**   ← 快 4.7×
    //   （另两组换堆大小同样 300 passed：默认并发 112s / 限流 517s）
    //
    // 即该限流**没有任何收益，却带来约 4.7× 的本机退化**（8.5 分钟 vs 1.8 分钟）。
    // 我本人在 CPU≈80% 下重测 `--maxWorkers=24` 同样通过（仅 1 例负载型单测超时）。
    // 故移除，恢复 vitest 默认并发（也恢复到本批改动前的并发行为）。
    //
    // **遇到 `no tests` / `Timeout waiting for worker to respond` 时怎么做**：
    // 那是**负载**问题（HEAD `79a5374` 已记录：worker 启动对机器负载敏感，换 pool 无效）。
    // 先看 CPU（`python -c "import psutil;print(psutil.cpu_percent(2))"`）；
    // 确认是负载后，**临时**降并发即可（`npx vitest run --maxWorkers=2`），
    // **不要把降并发固化进配置** —— 那会把「偶发负载」变成「每次都慢 4.7×」。
    //
    // 曾试过的替代方案：关掉 isolate（isolate:false）能让套件跑起来，
    // 但那会引入**跨文件 mock 实例串味**（同 worker 内多个文件共享模块实例，
    // 而 vi.mock 按文件注册 → 后跑文件的组件闭包仍指向上个文件遗留的 mock 实例）
    // —— 即 CI 上「同一 commit 时而红时而绿」的根因。**隔离必须保持开启。**
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
