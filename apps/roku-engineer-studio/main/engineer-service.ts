import { app, ipcMain, dialog, shell, safeStorage, BrowserWindow } from 'electron';
import type { IpcMainInvokeEvent } from 'electron';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { parseEnv } from 'node:util';
import { ENGINEER_CHANNEL } from '../shared/engineer';
import type { Project, WorkspaceRequest } from '../shared/engineer';
import { runEngine } from './engineer-runtime';
import { runEngineerAgent } from './engineer-agent';

type Preferences = { model?: string; python?: string; encryptedKey?: string; recentRoot?: string };
type Session = { root?: string; revision: string; artifact?: string; running?: boolean; controller?: AbortController };

export function registerEngineerWorkspace(): void {
  const engineDir = app.isPackaged ? path.join(process.resourcesPath, 'engine') : path.resolve(__dirname, '../..');
  const settingsFile = path.join(app.getPath('userData'), 'engineer-workspace.json');
  let preferences: Preferences = {};
  try { preferences = JSON.parse(fs.readFileSync(settingsFile, 'utf8')); } catch { /* first launch */ }
  const sessions = new Map<number, Session>();
  const save = () => {
    fs.mkdirSync(path.dirname(settingsFile), { recursive: true });
    const temp = `${settingsFile}.${randomUUID()}.tmp`;
    fs.writeFileSync(temp, JSON.stringify(preferences), { mode: 0o600 });
    fs.renameSync(temp, settingsFile);
  };
  const envValues = (): Record<string, string | undefined> => {
    let local: Record<string, string | undefined> = {};
    try { local = parseEnv(fs.readFileSync(path.join(engineDir, '.env'), 'utf8')); } catch { /* optional */ }
    return { ...local, ...process.env };
  };
  const apiKey = () => {
    if (preferences.encryptedKey && safeStorage.isEncryptionAvailable()) {
      try { return safeStorage.decryptString(Buffer.from(preferences.encryptedKey, 'base64')); } catch { /* fallback to environment */ }
    }
    return envValues().ANTHROPIC_API_KEY ?? '';
  };
  const configuration = () => ({
    hasKey: Boolean(apiKey()), encryptedStorage: safeStorage.isEncryptionAvailable() && (process.platform !== 'linux' || safeStorage.getSelectedStorageBackend() !== 'basic_text'),
    model: preferences.model || envValues().MAINMODEL || 'claude-sonnet-5-5',
    python: preferences.python || envValues().ROKU_ENGINEER_PYTHON || '',
    engineDir,
  });
  const call = (session: Session, request: Record<string, unknown>, signal?: AbortSignal) => runEngine(
    { ...request, root: session.root }, { engineDir, python: configuration().python, signal },
  );
  const project = async (session: Session): Promise<Project> => ({ ...await call(session, { action: 'project' }), revision: session.revision });
  ipcMain.handle(ENGINEER_CHANNEL, async (event: IpcMainInvokeEvent, request: WorkspaceRequest) => {
    try {
      // Only the real main renderer may access project files or credentials, never an arbitrary iframe/window.
      const frame = event.senderFrame;
      if (!frame || frame !== event.sender.mainFrame || !frame.url.startsWith('file:')) throw new Error('Workspace is available only in the desktop main window.');
      const expected = path.resolve(__dirname, 'renderer/index.html');
      if (path.resolve(fileURLToPath(frame.url.split('?')[0])) !== expected) throw new Error('Untrusted workspace sender.');
      if (!request || typeof request.action !== 'string') throw new Error('Invalid workspace request.');
      let session = sessions.get(event.sender.id);
      if (!session) {
        session = { revision: randomUUID() }; sessions.set(event.sender.id, session);
        const id = event.sender.id;
        event.sender.once('destroyed', () => { sessions.get(id)?.controller?.abort(); sessions.delete(id); });
      }
      let data: any;
      if (request.action === 'cancel') { session.controller?.abort(); return { ok: true, data: {} }; }
      if (request.action === 'settings') return { ok: true, data: configuration() };
      if (session.running) throw new Error('A workspace operation is already running. Wait for it to finish.');
      session.running = true;
      try {
        switch (request.action) {
          case 'configure': {
            if (typeof request.model === 'string') {
              if (!/^[a-zA-Z0-9_.:-]{1,120}$/.test(request.model)) throw new Error('Enter a valid Anthropic model ID.');
              preferences.model = request.model;
            }
            if (typeof request.python === 'string') {
              if (request.python.length > 1024 || /[\r\n\0]/.test(request.python)) throw new Error('Invalid Python executable.');
              preferences.python = request.python.trim();
            }
            if (request.clearKey) delete preferences.encryptedKey;
            if (request.apiKey?.trim()) {
              if (!configuration().encryptedStorage) throw new Error('Encrypted storage is unavailable. Set ANTHROPIC_API_KEY in your environment instead.');
              if (request.apiKey.length > 1024 || /[\r\n\0]/.test(request.apiKey)) throw new Error('Invalid API key.');
              preferences.encryptedKey = safeStorage.encryptString(request.apiKey.trim()).toString('base64');
            }
            save(); data = configuration(); break;
          }
          case 'status': data = { ...configuration(), ...await call(session, { action: 'status' }), pythonExecutable: configuration().python, recentRoot: preferences.recentRoot }; break;
          case 'tool': {
            const parent = BrowserWindow.fromWebContents(event.sender) ?? undefined;
            if (request.name === 'scripts') require('./action-scripts-viewer-window').openActionScriptsViewerWindow(parent);
            else if (request.name === 'fiddle') event.sender.send(require('../shared/ipc/channels').IPC.FiddleOpen, {});
            else if (request.name === 'analysis') require('./static-analysis-window').openStaticAnalysisWindow(parent);
            else throw new Error('Unknown development tool.');
            data = {}; break;
          }
          case 'restore':
            if (!preferences.recentRoot || !fs.existsSync(preferences.recentRoot)) { data = null; break; }
            session.root = fs.realpathSync(preferences.recentRoot); session.revision = randomUUID(); data = await project(session); break;
          case 'pick': {
            const result = await dialog.showOpenDialog({ title: 'Open Roku project', properties: ['openDirectory'] });
            if (result.canceled) { data = null; break; }
            session.root = fs.realpathSync(result.filePaths[0]); session.revision = randomUUID(); session.artifact = undefined;
            data = await project(session); preferences.recentRoot = session.root; save(); break;
          }
          case 'scaffold': {
            const result = await dialog.showOpenDialog({ title: 'Choose a parent folder for the new channel', properties: ['openDirectory', 'createDirectory'] });
            if (result.canceled) { data = null; break; }
            const parent = { ...session, root: fs.realpathSync(result.filePaths[0]) };
            const created = await call(parent, { action: 'scaffold', name: request.name, kind: request.kind });
            session.root = created.root; session.revision = randomUUID(); session.artifact = undefined;
            data = { ...created, revision: session.revision }; preferences.recentRoot = session.root; save(); break;
          }
          default: {
            if (!session.root) throw new Error('Open or create a project first.');
            if (request.revision !== session.revision) throw new Error('The selected project changed. Refresh the workspace before continuing.');
            if (request.action === 'project') data = await project(session);
            else if (request.action === 'read') data = await call(session, { action: 'read', path: request.path });
            else if (request.action === 'apply') data = { ...await call(session, { action: 'apply', changes: request.changes }), revision: session.revision };
            else if (request.action === 'preview') data = await call(session, { action: 'preview', generator: request.generator });
            else if (request.action === 'validate') data = await call(session, { action: 'validate' });
            else if (request.action === 'lint') data = await call(session, { action: 'lint', content: request.content });
            else if (request.action === 'package') { data = await call(session, { action: 'package' }); session.artifact = data.path; }
            else if (request.action === 'reveal') { shell.showItemInFolder(session.artifact || session.root); data = {}; }
            else if (request.action === 'export-report') {
              if (typeof request.content !== 'string' || request.content.length > 1024 * 1024) throw new Error('Invalid report.');
              const choice = await dialog.showSaveDialog({ title: 'Export workspace report', defaultPath: 'roku-engineer-report.md', filters: [{ name: 'Markdown', extensions: ['md'] }] });
              if (!choice.canceled && choice.filePath) fs.writeFileSync(choice.filePath, request.content, 'utf8');
              data = { saved: !choice.canceled };
            } else if (request.action === 'chat') {
              if (!Array.isArray(request.messages) || request.messages.length > 100 || request.messages.some(m => !m || !['user', 'assistant'].includes(m.role) || typeof m.content !== 'string' || m.content.length > 32000)) throw new Error('Invalid conversation.');
              session.controller = new AbortController();
              try {
                data = await runEngineerAgent({ apiKey: apiKey(), model: configuration().model, messages: request.messages, project: await project(session), signal: session.controller.signal, call: req => call(session!, req, session!.controller?.signal) });
              } finally { session.controller = undefined; }
            } else throw new Error('Unsupported workspace action.');
          }
        }
      } finally { session.running = false; }
      return { ok: true, data };
    } catch (error) {
      return { ok: false, error: error instanceof Error ? error.message : 'Workspace action failed.' };
    }
  });
  app.on('before-quit', () => { for (const session of sessions.values()) session.controller?.abort(); });
}
