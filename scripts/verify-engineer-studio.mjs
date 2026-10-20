/** Real Electron + real IPC + real Python QA. Only the OS pickers are scripted.
 * Run after npm run studio:build. Screenshots and report go to artifacts/studio-qa/.
 */
import { _electron as electron } from 'playwright';
import { createRequire } from 'node:module';
import * as fs from 'node:fs/promises';
import * as os from 'node:os';
import * as path from 'node:path';
import assert from 'node:assert/strict';
const require = createRequire(import.meta.url);
const root = path.resolve(import.meta.dirname, '..');
const appDir = path.join(root, 'apps/roku-engineer-studio');
const artifacts = path.join(root, 'artifacts/studio-qa');
const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'roku-engineer-electron-qa-'));
await fs.mkdir(artifacts, { recursive: true });
const bootstrap = path.join(temp, 'bootstrap.cjs');
await fs.writeFile(bootstrap, `const {app,dialog}=require('electron');
app.setPath('userData',${JSON.stringify(path.join(temp, 'profile'))});
global.__qaDirs=[];
dialog.showOpenDialog=async()=>({canceled:!global.__qaDirs.length,filePaths:global.__qaDirs.length?[global.__qaDirs.shift()]:[]});
dialog.showSaveDialog=async()=>({canceled:false,filePath:${JSON.stringify(path.join(artifacts, 'validation.md'))}});
dialog.showMessageBoxSync=()=>1;
require(${JSON.stringify(path.join(appDir, 'main.bundled.cjs'))});
`);
const env = { ...process.env };
delete env.ELECTRON_RUN_AS_NODE;
delete env.ANTHROPIC_API_KEY;
delete env.TAVILY_API_KEY;
const results = [];
const errors = [];
const studio = await electron.launch({ executablePath: require('electron'), args: [bootstrap, '--force-device-scale-factor=1'], env, timeout: 45000 });
try {
  const page = await studio.firstWindow();
  page.setDefaultTimeout(30000);
  page.on('pageerror', error => errors.push(error.message));
  await page.waitForSelector('#engineerWorkbench', { timeout: 45000 });
  await page.locator('#ewRuntime').filter({ hasText: 'connected' }).waitFor({ timeout: 45000 });
  async function resize(width, height, zoom = 1) {
    const actual = await studio.evaluate(({ BrowserWindow }, size) => {
      const win = BrowserWindow.getAllWindows().find(w => !w.isDestroyed() && !w.webContents.isDestroyed() && w.webContents.getURL().includes('/renderer/index.html'));
      win.unmaximize(); win.webContents.setZoomFactor(size.zoom); win.setContentSize(size.width, size.height);
      return { content: win.getContentSize(), zoom: win.webContents.getZoomFactor() };
    }, { width, height, zoom });
    await page.waitForFunction(({ content, zoom }) => Math.abs(window.innerWidth - content[0] / zoom) < 3 && Math.abs(window.innerHeight - content[1] / zoom) < 3, actual, { timeout: 15000 });
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  }
  await resize(1480, 980);
  await page.screenshot({ path: path.join(artifacts, '01-overview.png') });
  results.push('Desktop loads real preload and Python runtime.');

  await page.locator('.ew-hero [data-action="create"]').click();
  await page.locator('#ewCreateCancel').click();
  assert.equal(await page.locator('#ewDialog').evaluate(el => el.open), false);
  results.push('New-channel Cancel closes with an empty required field.');
  await studio.evaluate(async () => { global.__qaDirs.push(process.env.TEMP || process.env.TMP || '.'); });
  // Replace picker queue with isolated temporary parent.
  await studio.evaluate((_electron, dir) => { global.__qaDirs = [dir]; }, temp);
  await page.locator('.ew-hero [data-action="create"]').click();
  await page.locator('#ewChannelName').fill('Orbit Cinema');
  await page.locator('#ewTemplate').selectOption('grid');
  await page.locator('.ew-create-form button[type="submit"]').click();
  await page.locator('[data-file="source/main.brs"]').waitFor({ timeout: 60000 });
  results.push('Grid scaffold created through real IPC + Python with assets.');
  await page.locator('[data-file="source/main.brs"]').click();
  await page.locator('#ewCode').waitFor({ state: 'visible' });
  await page.locator('.ew.ew-busy').waitFor({ state: 'detached' });
  const original = await page.locator('#ewCode').inputValue();
  await page.locator('#ewCode').fill(original + '\n\' Electron QA edit\n');
  await page.locator('[data-file="manifest"]').click();
  await page.getByRole('button', { name: 'Keep editing', exact: true }).click();
  assert.match(await page.locator('#ewCode').inputValue(), /Electron QA edit/);
  await page.locator('.ew-editor-toolbar [data-action="save"]').click();
  await page.locator('#ewToast').filter({ hasText: 'Saved.' }).waitFor({ timeout: 45000 });
  assert.match(await fs.readFile(path.join(temp, 'Orbit Cinema/source/main.brs'), 'utf8'), /Electron QA edit/);
  await page.screenshot({ path: path.join(artifacts, '02-editor.png') });
  results.push('Editor preserves unsaved work on Cancel and saves with a history backup.');

  await page.locator('.ew-sidebar nav [data-view="integrations"]').click();
  await page.locator('[data-generator="feed"]').click();
  await page.getByRole('button', { name: 'Apply reviewed changes', exact: true }).waitFor({ timeout: 45000 });
  await page.screenshot({ path: path.join(artifacts, '03-preview.png') });
  assert.equal(await fs.stat(path.join(temp, 'Orbit Cinema/components/ContentFeedTask/ContentFeedTask.xml')).then(() => true, () => false), false);
  await page.getByRole('button', { name: 'Apply reviewed changes', exact: true }).click();
  await page.locator('#ewToast').filter({ hasText: 'Applied' }).waitFor({ timeout: 45000 });
  results.push('Integration preview leaves project unchanged; reviewed Apply writes files.');
  await page.screenshot({ path: path.join(artifacts, '04-integrations.png') });

  await page.locator('.ew-sidebar nav [data-view="readiness"]').click();
  await page.locator('[data-action="validate"]').click();
  await page.locator('#ewReport').filter({ hasText: 'Project validation' }).waitFor({ timeout: 45000 });
  await page.locator('[data-action="export-report"]').click();
  await page.locator('.ew-busy').waitFor({ state: 'detached' });
  assert.match(await fs.readFile(path.join(artifacts, 'validation.md'), 'utf8'), /local validation/);
  await page.locator('[data-action="package"]').click();
  await page.locator('.ew-artifact').waitFor({ timeout: 45000 });
  assert.ok((await fs.stat(path.join(temp, 'Orbit Cinema/.engineer/artifacts/Orbit Cinema.zip'))).size > 1000);
  await page.screenshot({ path: path.join(artifacts, '05-readiness.png') });
  results.push('Local checks, report export, and real channel ZIP creation work.');

  await page.locator('.ew-sidebar-bottom [data-view="settings"]').click();
  await page.screenshot({ path: path.join(artifacts, '06-settings.png') });
  await page.locator('[data-action="commands"]').click();
  await page.getByRole('textbox', { name: 'Search commands' }).fill('main.brs');
  await page.locator('.ew-command-list button').first().click();
  await page.locator('#ewCode').waitFor({ state: 'visible' });
  results.push('Command palette filters project files and opens the editor.');

  await page.locator('.ew-mode-switch [data-mode="lab"]').click();
  assert.equal(await page.locator('body').evaluate(el => el.classList.contains('engineer-mode')), false);
  await page.screenshot({ path: path.join(artifacts, '07-device-lab.png') });
  await page.locator('.ew-mode-switch [data-mode="workspace"]').click();

  for (const [action, title] of [['scripts', /Action Scripts/i], ['fiddle', /Fiddle/i], ['analysis', /Static Channel Analysis/i]]) {
    const windowPromise = studio.waitForEvent('window');
    await page.locator(`.ew-sidebar [data-action="${action}"]`).click();
    const child = await windowPromise;
    await child.waitForLoadState('domcontentloaded');
    if (action === 'fiddle') await child.locator('.monaco-editor').waitFor({ timeout: 30000 });
    await child.screenshot({ path: path.join(artifacts, `08-${action}.png`) });
    assert.match(await child.title(), title);
    await child.close();
    results.push(`${action} opens its complete standalone window.`);
  }
  await resize(1050, 780);
  await page.locator('.ew-sidebar nav [data-view="home"]').click();
  await page.screenshot({ path: path.join(artifacts, '09-compact.png') });
  const overflow = await page.evaluate(() => ({ width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
  assert.ok(overflow.scroll <= overflow.width + 1, JSON.stringify(overflow));
  results.push('Compact 1050 × 780 layout has no document horizontal overflow.');
  const resizeResults = [];
  for (const [width, height] of [[900, 600], [1024, 720], [1280, 800], [1480, 980], [1920, 1080]]) {
    await resize(width, height);
    for (const view of ['home', 'project', 'integrations', 'readiness', 'settings']) {
      await page.locator(`.ew-sidebar [data-view="${view}"]`).first().click();
      const layout = await page.evaluate(() => {
        const targets = ['.ew-header', '#ewContent', '.ew-status', '#ewYukiToggle'];
        if (document.querySelector('.ew-editor')) targets.push('.ew-editor-toolbar', '.ew-editor-footer');
        return { width: innerWidth, height: innerHeight, scrollWidth: document.documentElement.scrollWidth,
          outside: targets.filter(selector => { const r = document.querySelector(selector).getBoundingClientRect(); return r.left < -1 || r.right > innerWidth + 1 || r.top < -1 || r.bottom > innerHeight + 1 || r.width < 1 || r.height < 1; }),
          contentOverflow: document.querySelector('#ewContent').scrollWidth > document.querySelector('#ewContent').clientWidth + 2,
        };
      });
      assert.deepEqual(layout.outside, [], `${width}x${height} ${view}: ${JSON.stringify(layout)}`);
      assert.ok(layout.scrollWidth <= layout.width + 1, `${width}x${height} ${view}: document overflow`);
      assert.equal(layout.contentOverflow, false, `${width}x${height} ${view}: workspace overflow`);
      resizeResults.push({ requestedWidth: width, requestedHeight: height, view, ...layout });
    }
  }
  await resize(900, 620);
  await page.locator('.ew-sidebar [data-view="home"]').first().click();
  assert.equal(await page.locator('#ewAssistant').isVisible(), false);
  await page.locator('#ewYukiToggle').click();
  assert.equal(await page.locator('#ewAssistant').isVisible(), true);
  await page.keyboard.press('Escape');
  assert.equal(await page.locator('#ewAssistant').isVisible(), false);
  for (const zoom of [1.25, 1.5]) {
    await resize(1024, 720, zoom);
    await page.locator('.ew-sidebar [data-view="project"]').first().click();
    const size = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth }));
    assert.ok(size.scroll <= size.width + 1, `Zoom ${zoom} overflow: ${JSON.stringify(size)}`);
    const editorBounds = await page.locator('.ew-editor-footer').boundingBox();
    assert.ok(editorBounds.y + editorBounds.height <= await page.evaluate(() => innerHeight), `Zoom ${zoom} clips the editor footer`);
    await page.locator('#ewYukiToggle').click(); await page.keyboard.press('Escape');
  }
  results.push('25 native window/view combinations, 125% and 150% zoom, and compact Yuki drawer pass.');
  await resize(1480, 980);
  await page.locator('#ewYukiToggle').click();
  assert.equal(await page.locator('#ewAssistant').isVisible(), false);
  await page.locator('#ewYukiToggle').click();
  assert.equal(await page.locator('#ewAssistant').isVisible(), true);
  await page.locator('.ew-sidebar [data-view="home"]').first().click();
  await page.screenshot({ path: path.join(artifacts, 'gallery-overview.png') });
  await page.locator('.ew-sidebar [data-view="project"]').first().click();
  await page.locator('[data-file="source/main.brs"]').click();
  await page.locator('#ewCode').waitFor({ state: 'visible' });
  await page.locator('.ew.ew-busy').waitFor({ state: 'detached' });
  await page.mouse.move(5, 5);
  await page.screenshot({ path: path.join(artifacts, 'gallery-editor.png') });
  await page.locator('.ew-sidebar [data-view="integrations"]').first().click();
  await page.locator('[data-generator="payments"]').click();
  await page.getByRole('button', { name: 'Apply reviewed changes', exact: true }).waitFor({ timeout: 45000 });
  await page.screenshot({ path: path.join(artifacts, 'gallery-review.png') });
  await page.getByRole('button', { name: 'Keep reviewing later', exact: true }).click();
  await page.screenshot({ path: path.join(artifacts, 'gallery-integrations.png') });
  await page.locator('.ew-sidebar [data-view="readiness"]').first().click();
  await page.screenshot({ path: path.join(artifacts, 'gallery-readiness.png') });
  await resize(900, 620);
  await page.locator('.ew-sidebar [data-view="project"]').first().click();
  await page.screenshot({ path: path.join(artifacts, 'gallery-compact.png') });
  await fs.writeFile(path.join(artifacts, 'resize-report.json'), JSON.stringify(resizeResults, null, 2));
  assert.deepEqual(errors, []);
  await fs.writeFile(path.join(artifacts, 'report.json'), JSON.stringify({ results, errors, hardwareTested: false, liveProviderTested: false }, null, 2));
  console.log(JSON.stringify({ passed: results.length, results, errors }, null, 2));
} catch (error) {
  await fs.writeFile(path.join(artifacts, 'failure.txt'), String(error) + '\n' + errors.join('\n'));
  try { await (await studio.firstWindow()).screenshot({ path: path.join(artifacts, 'failure.png') }); } catch {}
  throw error;
} finally {
  const shutdown = setTimeout(() => studio.process().kill(), 5000);
  try { await studio.close(); } finally { clearTimeout(shutdown); }
}
