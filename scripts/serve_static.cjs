// 静态预览服务器（E2E 专用，无后端依赖）
//
// 复刻 api/main.py 的静态挂载语义，用于移动端/视觉 E2E 冒烟：
//   /              → landing/dist       （html=True，SPA 单页）
//   /admin  /admin/  → frontend/dist    （SPA 深链回退 index.html + /admin→/admin/ 307）
//
// 与生产差异（已知且刻意）：不加载 api 动态路由（/v1/*、/healthz 等），
// 故 E2E 只能验证前端静态产物与路由，不覆盖后端联调。
//
// 用法：node scripts/serve_static.cjs [--port 4590] [--root .]
const fs = require('fs');
const http = require('http');
const path = require('path');

const args = process.argv.slice(2);
const argVal = (name, dflt) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : dflt;
};
const PORT = parseInt(argVal('--port', '4590'), 10);
const ROOT = path.resolve(argVal('--root', path.join(__dirname, '..')));

const LANDING_DIR = path.join(ROOT, 'landing', 'dist');
const ADMIN_DIR = path.join(ROOT, 'frontend', 'dist');

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.webmanifest': 'application/manifest+json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.txt': 'text/plain; charset=utf-8',
  '.xml': 'application/xml; charset=utf-8',
  '.map': 'application/json; charset=utf-8',
};

/**
 * 防目录穿越：解析后必须仍在 baseDir 内。
 *
 * 返回 null 表示请求路径无效（畸形编码或越界），调用方应回退 400/index。
 * 注意两处易错点：
 *  1. decodeURIComponent 对畸形百分号编码（如 `/%`）抛 URIError —— 必须捕获，
 *     否则在请求回调中同步抛出会成为 uncaughtException 直接杀进程（一条畸形请求即 DoS）。
 *  2. 边界比较不能只用 startsWith(baseDir)：`baseDir` 为 `/x/dist` 时
 *     `/x/dist-evil` 也是同前缀兄弟目录，必须以 `baseDir + path.sep` 为界。
 */
function safeJoin(baseDir, urlPath) {
  let decoded;
  try {
    decoded = decodeURIComponent(urlPath.split('?')[0].split('#')[0]);
  } catch {
    return null; // URIError: URI malformed
  }
  const base = path.normalize(baseDir);
  const target = path.normalize(path.join(base, decoded));
  if (target !== base && !target.startsWith(base + path.sep)) return null;
  return target;
}

/** 请求路径是否可解码（畸形编码应回 400 而非静默回退 index.html）。 */
function isDecodable(urlPath) {
  try {
    decodeURIComponent(urlPath.split('?')[0].split('#')[0]);
    return true;
  } catch {
    return false;
  }
}

function sendFile(res, filePath, status = 200) {
  const ext = path.extname(filePath).toLowerCase();
  const body = fs.readFileSync(filePath);
  res.writeHead(status, {
    'Content-Type': MIME[ext] || 'application/octet-stream',
    'Content-Length': body.length,
    'Cache-Control': 'no-store',
  });
  res.end(body);
}

/** SPA 解析：命中真实文件则返回；否则回退 index.html（深链刷新）。 */
function resolveSpa(dir, urlPath) {
  const direct = safeJoin(dir, urlPath);
  if (direct && fs.existsSync(direct) && fs.statSync(direct).isFile()) return direct;
  const asDirIndex = direct && fs.existsSync(direct) && fs.statSync(direct).isDirectory()
    ? path.join(direct, 'index.html')
    : null;
  if (asDirIndex && fs.existsSync(asDirIndex)) return asDirIndex;
  const fallback = path.join(dir, 'index.html');
  return fs.existsSync(fallback) ? fallback : null;
}

for (const [label, dir] of [['landing', LANDING_DIR], ['admin', ADMIN_DIR]]) {
  if (!fs.existsSync(path.join(dir, 'index.html'))) {
    console.error(`[FATAL] ${label} dist 缺失: ${dir}\\index.html`);
    console.error('        请先构建：cd landing && npm run build ／ cd frontend && npm run build');
    process.exit(2);
  }
}

const server = http.createServer((req, res) => {
  try {
    const url = req.url || '/';

    // 畸形百分号编码（如 `/%`）→ 400，而非崩溃或静默回退 index.html
    if (!isDecodable(url)) {
      res.writeHead(400, { 'Content-Type': 'text/plain; charset=utf-8' });
      return res.end('400 Bad Request: malformed percent-encoding');
    }

    // /admin 无斜杠 → 307 到 /admin/（与 api/main.py:209 行为一致）
    if (url === '/admin' || url === '/admin?') {
      res.writeHead(307, { Location: '/admin/' });
      return res.end();
    }

    if (url === '/admin/' || url.startsWith('/admin/')) {
      const sub = url === '/admin/' ? '/' : url.slice('/admin'.length);
      const file = resolveSpa(ADMIN_DIR, sub);
      if (!file) {
        res.writeHead(404).end('admin index.html missing');
        return;
      }
      return sendFile(res, file);
    }

    const file = resolveSpa(LANDING_DIR, url);
    if (!file) {
      res.writeHead(404).end('landing index.html missing');
      return;
    }
    return sendFile(res, file);
  } catch (e) {
    // 纵深防御：任何未预期异常都不应杀死预览进程（否则污染 E2E 验收）
    console.error('[serve_static] request failed:', e && e.message);
    if (!res.headersSent) res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' });
    return res.end('500 Internal Preview Server Error');
  }
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`static preview on http://127.0.0.1:${PORT}`);
  console.log(`  /        -> ${LANDING_DIR}`);
  console.log(`  /admin/  -> ${ADMIN_DIR}`);
});

// 供测试进程优雅终止
process.on('SIGTERM', () => server.close(() => process.exit(0)));
process.on('SIGINT', () => server.close(() => process.exit(0)));
