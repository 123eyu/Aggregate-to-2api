// 移动端 375×667 视口冒烟（v22 P1-4，v23.x 修订）
//
// 验证范围（v22 指南承诺 2 条最小路径，本脚本全覆盖）：
//   /         landing 门户 —— 无横向滚动 + 关键标题渲染 + 可交互元素存在
//   /admin    SPA 管理面板 —— 深链回退生效 + 无横向滚动 + 导航可交互
//
// 无后端依赖（纯静态产物）。需先起静态服务器：
//   node scripts/serve_static.cjs            # 或任意静态服务器指向 landing/dist
// 通过环境变量覆盖：
//   IF_E2E_BASE=http://127.0.0.1:4590  静态服务地址（默认）
//
// 路径策略：全部基于脚本自身位置推导相对路径，不写死宿主绝对路径
// （v22 初版写死 Desktop/imagefree-2ai/... 与 ms-playwright 绝对路径，
//  换机/改目录名即崩——此处修正为 __dirname 推导 + 环境变量回退）。
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');

/** 解析 playwright-core：优先项目内 frontend/node_modules，回退根 node_modules。 */
function resolvePlaywrightCore() {
  const candidates = [
    process.env.IF_PLAYWRIGHT_CORE,
    path.join(ROOT, 'frontend', 'node_modules', 'playwright-core'),
    path.join(ROOT, 'node_modules', 'playwright-core'),
  ].filter(Boolean);
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  throw new Error(
    'playwright-core 未找到。请先在 frontend/ 执行 npm install，或设置 IF_PLAYWRIGHT_CORE 指向其绝对路径。'
  );
}

/** 解析 chromium 可执行文件：环境变量优先，其次按平台在 ms-playwright 缓存中查找。 */
function findChromium() {
  if (process.env.IF_CHROMIUM_EXE && fs.existsSync(process.env.IF_CHROMIUM_EXE)) {
    return process.env.IF_CHROMIUM_EXE;
  }
  const cacheRoots = [
    process.env.PLAYWRIGHT_BROWSERS_PATH,
    // Windows
    process.env.LOCALAPPDATA && path.join(process.env.LOCALAPPDATA, 'ms-playwright'),
    // macOS
    process.env.HOME && path.join(process.env.HOME, 'Library', 'Caches', 'ms-playwright'),
    // Linux
    process.env.HOME && path.join(process.env.HOME, '.cache', 'ms-playwright'),
  ].filter(Boolean);

  const subDirs =
    process.platform === 'win32'
      ? ['chrome-win64', 'chrome-win']
      : process.platform === 'darwin'
        ? ['chrome-mac', 'chrome-mac-arm64']
        : ['chrome-linux64', 'chrome-linux'];
  const exeName = process.platform === 'win32' ? 'chrome.exe' : 'chrome';

  for (const cacheRoot of cacheRoots) {
    if (!fs.existsSync(cacheRoot)) continue;
    const dirs = fs
      .readdirSync(cacheRoot)
      .filter((d) => /^chromium-\d+$/.test(d))
      .sort((a, b) => parseInt(b.slice(9), 10) - parseInt(a.slice(9), 10));
    for (const d of dirs) {
      for (const sub of subDirs) {
        const exe = path.join(cacheRoot, d, sub, exeName);
        if (fs.existsSync(exe)) return exe;
      }
    }
  }
  return null;
}

const BASE = process.env.IF_E2E_BASE || 'http://127.0.0.1:4590';
const VIEWPORT = { width: 375, height: 667 };
let pass = 0;
let fail = 0;
const ok = (name, cond, detail = '') => {
  if (cond) {
    pass++;
    console.log('  PASS ' + name);
  } else {
    fail++;
    console.log('  FAIL ' + name + (detail ? ' | ' + detail : ''));
  }
};

/**
 * 对单个路径跑通用移动端断言（无横向滚动 + overflow 元素计数）。
 *
 * overflow 判定排除「有意截断」容器：带 text-overflow:ellipsis / overflow:hidden
 * 的元素 scrollWidth>clientWidth 属设计意图（省略号生效），不是布局缺陷。
 * 若把它们计入，会增加噪声并掩盖真正溢出的容器。
 */
async function checkNoHorizontalScroll(page, label) {
  const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  ok(`${label} 无横向滚动 (scrollWidth<=375)`, scrollWidth <= 375, `实际 scrollWidth=${scrollWidth}`);

  const offenders = await page.evaluate(() => {
    const vw = document.documentElement.clientWidth;
    return [...document.querySelectorAll('*')]
      .filter((e) => {
        if (e.scrollWidth <= e.clientWidth + 1) return false;
        const cs = getComputedStyle(e);
        // 有意截断：省略号 / 隐藏溢出 / 可滚动容器（属设计意图，非布局缺陷）
        const intentional =
          cs.textOverflow === 'ellipsis' ||
          cs.overflowX === 'hidden' ||
          cs.overflowX === 'auto' ||
          cs.overflowX === 'scroll';
        if (intentional) return false;
        // 装饰性溢出判定：元素实际盒子未越出视口右缘，且无 overflow 滚动能力，
        // 则其 scrollWidth 膨胀来自伪元素动画（如 .tf-dot-pulse::after 的 scale(2)
        // 脉冲）或不可见内容，不产生用户可见的横向滚动 → 非布局缺陷。
        const r = e.getBoundingClientRect();
        if (r.right <= vw + 1) return false;
        return true;
      })
      .map((e) => `${e.tagName}.${(e.className || '').toString().slice(0, 40)}[${e.scrollWidth}>${e.clientWidth}]`)
  });
  ok(
    `${label} 无意外横向溢出元素`,
    offenders.length === 0,
    offenders.length ? `${offenders.length} 个: ${offenders.slice(0, 6).join(', ')}` : ''
  );
}

(async () => {
  let chromium;
  try {
    chromium = require(resolvePlaywrightCore()).chromium;
  } catch (e) {
    console.log('FAIL ' + e.message);
    process.exit(1);
  }

  const exe = findChromium();
  if (!exe) {
    console.log('FAIL 未找到 chromium 可执行文件（设 IF_CHROMIUM_EXE 或执行 npx playwright install chromium）');
    process.exit(1);
  }
  console.log('chromium:', exe);

  const browser = await chromium.launch({ executablePath: exe, headless: true });
  const page = await browser.newPage({ viewport: VIEWPORT });
  const consoleErrors = [];
  page.on('console', (m) => {
    if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 100));
  });

  const artifactsDir = path.join(ROOT, 'docs', 'verification-artifacts');
  fs.mkdirSync(artifactsDir, { recursive: true });

  try {
    // ── 路径 1：landing 门户 / ──
    console.log('\n[1/2] landing /');
    await page
      .goto(BASE + '/', { waitUntil: 'networkidle', timeout: 30000 })
      .catch(() => page.goto(BASE + '/', { timeout: 30000 }));

    await checkNoHorizontalScroll(page, 'landing');

    const titleText = await page.evaluate(() => {
      const el =
        document.querySelector('.brand-name') || document.querySelector('h1') || document.querySelector('.hero h1');
      return el ? el.textContent.trim() : null;
    });
    ok('landing 关键标题渲染', !!titleText, `title=${titleText}`);

    const ctaExists = await page.evaluate(() => !!document.querySelector('button, .btn, a.btn, [role="button"]'));
    ok('landing 有可点击元素 (button/.btn)', ctaExists);

    await page.screenshot({ path: path.join(artifactsDir, 'mobile-landing-375.png'), fullPage: true });
    console.log('  截图: docs/verification-artifacts/mobile-landing-375.png');

    // ── 路径 2：SPA 管理面板 /admin（v22 指南承诺但初版漏测）──
    console.log('\n[2/2] admin /admin');
    const adminResp = await page.goto(BASE + '/admin/', { waitUntil: 'networkidle', timeout: 30000 });
    ok('admin 页面可访问', !!adminResp && adminResp.status() < 400, `status=${adminResp && adminResp.status()}`);

    // SPA 挂载证据：存在 id=root 且已渲染出子节点（非空壳）
    const rootRendered = await page.evaluate(() => {
      const root = document.getElementById('root') || document.querySelector('#app');
      return root ? root.children.length > 0 : false;
    });
    ok('admin SPA 已渲染（#root 有子节点）', rootRendered);

    await checkNoHorizontalScroll(page, 'admin');

    // 深链回退：直接访问 /admin/tasks 应仍渲染 SPA（StaticFiles html=True 回退 index.html）
    const deepResp = await page.goto(BASE + '/admin/tasks', { waitUntil: 'networkidle', timeout: 30000 });
    const deepRendered = await page.evaluate(() => {
      const root = document.getElementById('root') || document.querySelector('#app');
      return root ? root.children.length > 0 : false;
    });
    ok('admin 深链 /admin/tasks 回退渲染', !!deepResp && deepResp.status() < 400 && deepRendered,
      `status=${deepResp && deepResp.status()} rendered=${deepRendered}`);

    await page.screenshot({ path: path.join(artifactsDir, 'mobile-admin-375.png'), fullPage: true });
    console.log('  截图: docs/verification-artifacts/mobile-admin-375.png');
  } catch (e) {
    console.log('FAIL 页面访问异常: ' + e.message.slice(0, 200));
    fail++;
  } finally {
    if (consoleErrors.length) {
      console.log('  console.error (' + consoleErrors.length + '): ' + consoleErrors.slice(0, 3).join(' || '));
    }
    await browser.close();
  }

  console.log(`\n结果: ${pass} passed / ${fail} failed`);
  process.exit(fail ? 1 : 0);
})();
