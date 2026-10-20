import { _electron as electron } from 'playwright';
import * as path from 'node:path';
import * as fs from 'node:fs/promises';
import * as os from 'node:os';
import assert from 'node:assert/strict';
const root = path.resolve(import.meta.dirname, '..');
const executablePath = process.argv[2];
if (!executablePath) throw new Error('Pass the absolute path to the packaged Roku Engineer Studio executable.');
const env = { ...process.env }; delete env.ELECTRON_RUN_AS_NODE;
const studio = await electron.launch({ executablePath: path.resolve(executablePath), env, timeout: 45000 });
let preferencesPath;
let preferencesBefore;
try {
  const page = await studio.firstWindow();
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.locator('#engineerWorkbench').waitFor({ timeout: 45000 });
  await page.setViewportSize({ width: 1480, height: 980 });
  await page.locator('#ewRuntime').filter({ hasText: 'connected' }).waitFor({ timeout: 45000 });
  const engine = await page.evaluate(() => window.engineer.request({ action: 'status' }));
  assert.equal(engine.ok, true, JSON.stringify(engine));
  assert.match(engine.data.python, /^3\./, 'Packaged runtime must report the detected Python version.');
  const metadata = await studio.evaluate(({ app }) => ({ name: app.getName(), version: app.getVersion(), packaged: app.isPackaged, resources: process.resourcesPath, profile: app.getPath('userData') }));
  assert.equal(metadata.name, 'Roku Engineer Studio'); assert.equal(metadata.version, '3.0.0'); assert.equal(metadata.packaged, true);
  await fs.access(path.join(metadata.resources, 'third_party/roku-dev-studio.LICENSE'));
  await fs.access(path.join(metadata.resources, 'engine/roku_engineer.py'));
  await fs.access(path.join(metadata.resources, 'engine/system/system_prompt.py'));
  preferencesPath = path.join(metadata.profile, 'engineer-workspace.json');
  preferencesBefore = await fs.readFile(preferencesPath).catch(() => null);
  const parent = await fs.mkdtemp(path.join(os.tmpdir(), 'roku-engineer-packaged-qa-'));
  await studio.evaluate(({ dialog }, dir) => { dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [dir] }); }, parent);
  await page.locator('.ew-hero [data-action="create"]').click();
  await page.locator('#ewChannelName').fill('Packaged Channel');
  await page.locator('.ew-create-form button[type="submit"]').click();
  await page.locator('[data-file="manifest"]').waitFor({ timeout: 60000 });
  assert.match(await fs.readFile(path.join(parent, 'Packaged Channel/manifest'), 'utf8'), /title=Packaged Channel/);
  const result = { ...metadata, python: engine.data.python, rendererErrors: errors, bundledEngine: true, bundledNotices: true, packagedProjectCreation: true, signed: false, nativeCaptureVerified: false };
  assert.deepEqual(errors, []);
  await fs.mkdir(path.join(root, 'artifacts/studio-qa'), { recursive: true });
  await page.screenshot({ path: path.join(root, 'artifacts/studio-qa/10-packaged.png') });
  await fs.writeFile(path.join(root, 'artifacts/packaged-smoke.json'), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
} finally {
  await studio.close();
  if (preferencesPath) {
    if (preferencesBefore) await fs.writeFile(preferencesPath, preferencesBefore);
    else await fs.unlink(preferencesPath).catch(() => {});
  }
}
