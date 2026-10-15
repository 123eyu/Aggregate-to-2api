// Vitest 全局测试环境初始化。
// 引入 @testing-library/jest-dom 扩展 expect 断言（toBeInTheDocument 等）。
import '@testing-library/jest-dom';

import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// ── DOM 清理（2026-10-15 修复）────────────────────────────────────
//
// 背景：`vite.config.ts` 设了 `isolate: false`（绕开非 ASCII 路径下 vitest worker
// 启动 60s 超时），但**当时并未真正实现隔离清理** —— 配置注释声称
// 「测试间通过 src/test/setup.ts 的 beforeEach 清理」，而本文件此前**没有任何清理逻辑**。
//
// 后果（CI 实证）：`isolate: false` + 无 cleanup ⇒ 上个用例 render 的组件残留在
// document 上 ⇒ 下一个用例的 `getByRole('button', { name: '按模型' })` 命中**两个**
// 同名按钮，抛 `TestingLibraryElementError: Found multiple elements`。
//
// CI 实锤（GitHub Actions run 38571665048，job「前端构建门禁」step「Vitest 测试」）：
//   src/test/CostsPage.test.tsx > CostsPage 成本视角切换 >
//   按具体模型、切换到 model 视角（provider+model 行）后 aria-pressed 同步
//   TestingLibraryElementError: Found multiple elements with the role "button" and name "按模型"
//
// 本机（ASCII 无关，但受进程内文件分配顺序影响）未必现，CI 上稳定失败 ——
// 正是「隔离设置与清理逻辑不配套」的典型症状。
//
// 修法：显式注册 afterEach(cleanup)。比依赖 RTL 的自动清理更可靠：
// 自动清理依赖模块加载时 `afterEach` 已在全局可见，isolate:false 下该前提不保证。
afterEach(() => {
  cleanup();
});

// Node 22+ 通过 vitest 的 tinypool 注入「Node 内置全局」（localStorage/crypto 等）作为
// 普通对象，会遮蔽 jsdom 的 Storage 实现（导致 localStorage.clear is not a function）。
// 这里用真实 jsdom Storage 实例替换全局 localStorage，恢复 Storage 原型链。
import { JSDOM } from 'jsdom';

const dom = new JSDOM('<!DOCTYPE html>', { url: 'http://localhost/' });
const win = dom.window as unknown as {
  localStorage: Storage;
  Storage: typeof Storage;
};
if (typeof localStorage?.clear !== 'function') {
  Object.defineProperty(globalThis, 'localStorage', {
    value: win.localStorage,
    configurable: true,
    writable: true,
  });
  if (win.Storage) (globalThis as { Storage?: typeof Storage }).Storage = win.Storage;
}
