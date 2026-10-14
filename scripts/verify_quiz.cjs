const path = require('path');
const ROOT = 'C:/Users/Administrator.DESKTOP-EGNE9ND/Desktop/2api目录/imagefree-2ai';
const { chromium } = require(path.join(ROOT, 'frontend', 'node_modules', 'playwright-core'));
const exe = 'C:/Users/Administrator.DESKTOP-EGNE9ND/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe';
const FILE_URL = 'file:///' + ROOT.split(path.sep).join('/') + '/docs/2026-10-14-hardening-report.html';

(async () => {
  const b = await chromium.launch({ executablePath: exe, headless: true });
  const p = await b.newPage({ viewport: { width: 1200, height: 900 } });
  const errs = [];
  p.on('pageerror', (e) => errs.push(e.message));

  await p.goto(FILE_URL);
  const nq = await p.evaluate(() => document.querySelectorAll('.q').length);
  console.log('题数:', nq);

  const keys = await p.evaluate(() =>
    [...document.querySelectorAll('.q')].map((q, i) => ({ idx: i, ans: q.dataset.a }))
  );
  console.log('答案序列:', keys.map((k) => k.ans).join(','));

  // 场景 1：全选正确答案 → 应通过
  for (let i = 0; i < keys.length; i++) {
    await p.click(`.q:nth-of-type(${i + 1}) input[value="${keys[i].ans}"]`);
  }
  await p.click('button');
  const allRight = await p.evaluate(() => document.getElementById('score').textContent);
  console.log('全对 →', allRight);
  await p.screenshot({ path: ROOT + '/docs/verification-artifacts/quiz-all-correct.png' });

  // 场景 2：第 4 题故意错 → 应不通过
  await p.goto(FILE_URL);
  for (let i = 0; i < keys.length; i++) {
    const wrong = ['a', 'b', 'c', 'd'].find((v) => v !== keys[i].ans);
    const sel = i === 3 ? wrong : keys[i].ans;
    await p.click(`.q:nth-of-type(${i + 1}) input[value="${sel}"]`);
  }
  await p.click('button');
  const oneWrong = await p.evaluate(() => document.getElementById('score').textContent);
  console.log('错1题 →', oneWrong);

  // 场景 3：完全不答 → 应提示未作答
  await p.goto(FILE_URL);
  await p.click('button');
  const none = await p.evaluate(() => document.getElementById('score').textContent);
  console.log('未作答 →', none);

  console.log('JS 错误:', errs.length ? errs : '无');
  await b.close();
})();
