import { _electron as electron } from 'playwright';
import { createRequire } from 'node:module';
import * as fs from 'node:fs/promises';
import * as path from 'node:path';
import * as os from 'node:os';
import assert from 'node:assert/strict';
const require = createRequire(import.meta.url);
const root = path.resolve(import.meta.dirname, '..');
const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'roku-engineer-window-qa-'));
const bootstrap = path.join(temp, 'bootstrap.cjs');
await fs.writeFile(bootstrap, `const {app}=require('electron'); app.setPath('userData',${JSON.stringify(path.join(temp, 'profile'))});require(${JSON.stringify(path.join(root, 'apps/roku-engineer-studio/main.bundled.cjs'))});`);
const env = { ...process.env }; delete env.ELECTRON_RUN_AS_NODE;
const packaged = process.argv[2];
const studio = await electron.launch({ executablePath: packaged ? path.resolve(packaged) : require('electron'), args: [...(packaged ? [] : [bootstrap]), '--force-device-scale-factor=1'], env, timeout: 45000 });
try {
  const page = await studio.firstWindow(); page.setDefaultTimeout(30000);
  await page.locator('#ewRuntime').filter({ hasText: 'connected' }).waitFor({ timeout: 45000 });
  const win = await studio.browserWindow(page);
  await win.evaluate(w => {
    globalThis.__windowControlInputs = [];
    w.webContents.on('before-input-event', (_event, input) => globalThis.__windowControlInputs.push(input));
  });
  await win.evaluate(w => { w.unmaximize(); w.setContentSize(1280, 800); });
  const read = () => win.evaluate(w => ({ maximized: w.isMaximized(), fullscreen: w.isFullScreen(), bounds: w.getBounds() }));
  const initial = await read();
  const pressF11 = () => win.evaluate(w => {
    w.focus(); w.webContents.focus();
    w.webContents.sendInputEvent({ type: 'keyDown', keyCode: 'F11' });
    w.webContents.sendInputEvent({ type: 'keyUp', keyCode: 'F11' });
  });
  async function waitFor(check, label) {
    const deadline = Date.now() + 8000;
    while (Date.now() < deadline) { const state = await read(); if (check(state)) return state; await new Promise(r => setTimeout(r, 50)); }
    throw new Error(`${label}: ${JSON.stringify(await read())}; inputs=${JSON.stringify(await win.evaluate(() => globalThis.__windowControlInputs))}`);
  }
  const results = [];
  for (const mode of ['workspace', 'lab']) {
    await page.locator(`.ew-mode-switch [data-mode="${mode}"]`).click();
    await page.locator('.titlebar-maximize').click();
    await waitFor(s => s.maximized, `${mode} maximize`);
    await page.waitForFunction(() => document.querySelector('.titlebar-maximize').classList.contains('titlebar-maximized'));
    await page.locator('.titlebar-maximize').click();
    const restored = await waitFor(s => !s.maximized, `${mode} restore`);
    assert.equal(restored.bounds.width, initial.bounds.width); assert.equal(restored.bounds.height, initial.bounds.height);
    results.push(`${mode}: top-right maximize / restore and glyph state pass; original dimensions restored.`);
  }
  for (const mode of ['workspace', 'lab']) {
    await page.locator(`.ew-mode-switch [data-mode="${mode}"]`).click();
    for (const exit of ['F11', 'button']) {
      await pressF11();
      await waitFor(s => s.fullscreen, `${mode} F11 enter fullscreen`);
      await page.waitForFunction(() => document.querySelector('.titlebar-maximize').classList.contains('titlebar-maximized'));
      if (exit === 'F11') await pressF11();
      else await page.locator('.titlebar-maximize').click();
      const restored = await waitFor(s => !s.fullscreen, `${mode} ${exit} exit fullscreen`);
      assert.equal(restored.bounds.width, initial.bounds.width); assert.equal(restored.bounds.height, initial.bounds.height);
      results.push(`${mode}: F11 enters fullscreen; ${exit} exits and restores the original window dimensions.`);
    }
  }
  const restored = await read();
  await fs.mkdir(path.join(root, 'artifacts/studio-qa'), { recursive: true });
  await fs.writeFile(path.join(root, `artifacts/studio-qa/window-controls${packaged ? '-packaged' : ''}.json`), JSON.stringify({ results, initial, restored }, null, 2));
  console.log(JSON.stringify({ results, initial, restored }, null, 2));
} finally {
  const shutdown = setTimeout(() => studio.process().kill(), 5000);
  try { await studio.close(); } finally { clearTimeout(shutdown); }
}
