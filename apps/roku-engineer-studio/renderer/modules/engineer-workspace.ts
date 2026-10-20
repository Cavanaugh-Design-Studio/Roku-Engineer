import type { EngineerAPI, Project, Proposal, AgentMessage, WorkspaceRequest } from '../../shared/engineer';

declare global { interface Window { engineer: EngineerAPI } }
type View = 'home' | 'project' | 'integrations' | 'readiness' | 'settings';
type OpenFile = { path: string; content: string; sha256: string };
const icons: Record<string, string> = {
  home: '<path d="m3 10 9-7 9 7v10H3z"/><path d="M9 20v-7h6v7"/>',
  folder: '<path d="M3 7V4h7l2 3h9v13H3z"/>',
  code: '<path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18"/>',
  spark: '<path d="m12 2 3 7 7 3-7 3-3 7-3-7-7-3 7-3zM20 2v4m-2-2h4"/>',
  shield: '<path d="m12 2 9 4v6c0 6-9 10-9 10S3 18 3 12V6z"/><path d="m8 12 3 3 5-6"/>',
  device: '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8m-4-4v4"/>',
  settings: '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="16" cy="17" r="3"/>',
  arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>',
  plus: '<path d="M12 4v16M4 12h16"/>',
  search: '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
  check: '<path d="m4 12 5 5L20 6"/>',
  close: '<path d="m5 5 14 14M5 19 19 5"/>',
  refresh: '<path d="M20 8a9 9 0 1 0 0 8M20 2v6h-6"/>',
};
const icon = (name: string) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] ?? icons.code}</svg>`;
const generators = [
  ['memory', '01', 'Memory monitoring', 'Handle low-memory events and keep your channel responsive.', 'Runtime'],
  ['deeplink', '02', 'Deep link routing', 'Route launch arguments and runtime content requests.', 'Navigation'],
  ['feed', '03', 'Content feeds', 'Load JSON content into a SceneGraph ContentNode tree.', 'Content'],
  ['ads', '04', 'Advertising', 'Start an integration with the Roku Advertising Framework.', 'Monetization'],
  ['payments', '05', 'Roku Pay', 'Scaffold catalog, entitlement, and purchase workflows.', 'Monetization'],
  ['websocket', '06', 'WebSocket task', 'Generate a task for a compatible real-time backend.', 'Connectivity'],
  ['sse', '07', 'Server-sent events', 'Scaffold a task for a compatible event stream.', 'Connectivity'],
];

function element<K extends keyof HTMLElementTagNameMap>(tag: K, text?: string, className?: string): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag); if (text !== undefined) el.textContent = text; if (className) el.className = className; return el;
}

function boot(): void {
  if (!window.engineer) return;
  const root = element('section', undefined, 'ew'); root.id = 'engineerWorkbench'; root.setAttribute('aria-label', 'Engineer Workspace');
  root.innerHTML = `
    <aside class="ew-sidebar">
      <button class="ew-brand" data-view="home" aria-label="Roku Engineer home"><span class="ew-monogram">re<span>·</span></span><span>ROKU<br><b>ENGINEER</b></span><small>STUDIO</small></button>
      <button class="ew-project-switch" data-action="open">${icon('folder')}<span id="ewProjectLabel">Open a project<small>Your channel workspace</small></span><span class="ew-key">⌘</span></button>
      <div class="ew-nav-label">WORKSPACE</div>
      <nav aria-label="Workspace navigation">
        <button data-view="home">${icon('home')}<span>Overview</span></button>
        <button data-view="project">${icon('code')}<span>Project editor</span></button>
        <button data-view="integrations">${icon('spark')}<span>Integrations</span><small>7</small></button>
        <button data-view="readiness">${icon('shield')}<span>Readiness</span></button>
      </nav>
      <div class="ew-nav-label ew-lab-label">DEVELOP &amp; TEST</div>
      <nav aria-label="Device development">
        <button data-action="lab">${icon('device')}<span>Device lab</span><span class="ew-external">↗</span></button>
        <button data-action="scripts">${icon('code')}<span>Action scripts</span></button>
        <button data-action="fiddle">${icon('plus')}<span>BrightScript Fiddle</span></button>
        <button data-action="analysis">${icon('shield')}<span>Static analysis</span></button>
        <button data-action="studio-settings">${icon('settings')}<span>MCP &amp; connections</span></button>
      </nav>
      <div class="ew-sidebar-bottom"><div class="ew-local-note"><span></span> Local workspace<small>Your files stay on your machine</small></div><button data-view="settings">${icon('settings')}Workspace settings</button><button data-action="about">${icon('code')}Credits &amp; licenses</button><div class="ew-version">CAVANAUGH DESIGN STUDIO <span>3.0</span></div></div>
    </aside>
    <div class="ew-main"><header class="ew-header"><div><span class="ew-header-brand">Workspace</span><span class="ew-slash">/</span><b id="ewViewLabel">Overview</b></div><button data-action="commands" class="ew-command-trigger" aria-label="Jump to anything">${icon('search')}<span>Jump to anything</span><kbd>Ctrl K</kbd></button><button data-action="refresh" class="ew-icon-button" title="Refresh project" aria-label="Refresh project">${icon('refresh')}</button><button data-action="toggle-yuki" id="ewYukiToggle" class="ew-assistant-toggle" aria-expanded="true" aria-controls="ewAssistant">${icon('spark')}<span>Yuki</span></button></header><main class="ew-content" id="ewContent"></main><footer class="ew-status"><span id="ewStatusText">Ready to build</span><span id="ewRuntime">Checking Python…</span></footer></div>
    <aside class="ew-yuki" id="ewAssistant" aria-label="Yuki assistant"><header><span class="ew-yuki-icon">${icon('spark')}</span><div><b>Yuki</b><small>YOUR CHANNEL COPILOT</small></div><button class="ew-icon-button" data-action="reset-chat" title="Clear conversation" aria-label="Clear conversation">${icon('refresh')}</button><button class="ew-icon-button" data-action="toggle-yuki" title="Hide Yuki" aria-label="Hide Yuki">${icon('close')}</button></header><div id="ewChat" class="ew-chat" aria-live="polite"></div><div class="ew-chat-bottom"><div id="ewChatContext" class="ew-chat-context">No project selected</div><form id="ewChatForm"><label class="ew-sr-only" for="ewChatInput">Message Yuki</label><textarea id="ewChatInput" placeholder="What are we building?" rows="3" maxlength="32000"></textarea><div><span id="ewChatModel">Anthropic · key required</span><button type="button" id="ewCancelChat" data-action="cancel-chat" hidden>Stop</button><button type="submit" aria-label="Send message to Yuki">${icon('arrow')}</button></div></form><p>Code changes are proposed for review.<br>Only the context Yuki reads is sent to Anthropic.</p></div></aside>
    <div id="ewToast" class="ew-toast" role="status" hidden></div>
    <dialog class="ew-dialog" id="ewDialog"><div id="ewDialogContent"></div></dialog>
  `;
  document.body.append(root);
  const modeSwitch = element('div', undefined, 'ew-mode-switch');
  modeSwitch.innerHTML = '<button data-mode="workspace" aria-pressed="true">Engineer Workspace</button><button data-mode="lab" aria-pressed="false">Device Lab</button>';
  document.querySelector('.titlebar-center')?.replaceChildren(modeSwitch);
  const content = root.querySelector<HTMLElement>('#ewContent')!;
  const dialog = root.querySelector<HTMLDialogElement>('#ewDialog')!;
  const dialogContent = root.querySelector<HTMLElement>('#ewDialogContent')!;
  const status = root.querySelector<HTMLElement>('#ewStatusText')!;
  const chat = root.querySelector<HTMLElement>('#ewChat')!;
  const chatInput = root.querySelector<HTMLTextAreaElement>('#ewChatInput')!;
  const chatForm = root.querySelector<HTMLFormElement>('#ewChatForm')!;
  let project: Project | null = null;
  let view: View = 'home';
  let openFile: OpenFile | null = null;
  let draft = '';
  let busy = false;
  let chatBusy = false;
  let report: { report: string; status: string; scope: string; at: string } | null = null;
  let lastPackage: { path: string; size: number; sha256: string } | null = null;
  let config: { model: string; python: string; hasKey: boolean; encryptedStorage: boolean; engineDir: string } | null = null;
  let messages: AgentMessage[] = [];
  let proposals: { proposal: Proposal; messageIndex: number; applied: boolean }[] = [];
  let toastTimer: ReturnType<typeof setTimeout>;

  async function request<T = any>(req: WorkspaceRequest): Promise<T> {
    const response = await window.engineer.request<T>({ revision: project?.revision, ...req });
    if (!response.ok) throw new Error(response.error);
    return response.data;
  }
  function notify(message: string, error = false): void {
    const toast = root.querySelector<HTMLElement>('#ewToast')!;
    toast.textContent = message; toast.hidden = false; toast.classList.toggle('is-error', error);
    clearTimeout(toastTimer); toastTimer = setTimeout(() => { toast.hidden = true; }, error ? 8000 : 4000);
  }
  async function work<T>(label: string, operation: () => Promise<T>): Promise<T | undefined> {
    if (busy || chatBusy) { notify('Wait for the current operation to finish.'); return; }
    busy = true; root.classList.add('ew-busy'); status.textContent = label;
    try { return await operation(); } catch (e) { notify(e instanceof Error ? e.message : 'Operation failed.', true); }
    finally { busy = false; root.classList.remove('ew-busy'); status.textContent = project ? `${project.title} · ${project.files.length} source files` : 'Ready to build'; }
  }
  function dirty(): boolean { return Boolean(openFile && draft !== openFile.content); }
  async function canLeave(): Promise<boolean> {
    if (!dirty()) return true;
    return new Promise(resolve => {
      modal('Unsaved changes', 'Your editor has changes. Save the file or discard them before switching projects or files.');
      const actions = element('div', undefined, 'ew-dialog-actions');
      const cancel = element('button', 'Keep editing', 'ew-button'); cancel.type = 'button';
      const discard = element('button', 'Discard changes', 'ew-button ew-primary'); discard.type = 'button';
      cancel.onclick = () => { dialog.close(); resolve(false); };
      discard.onclick = () => { draft = openFile?.content ?? ''; dialog.close(); resolve(true); };
      dialog.oncancel = () => { resolve(false); };
      dialog.addEventListener('close', () => resolve(false), { once: true });
      actions.append(cancel, discard); dialogContent.append(actions);
    });
  }
  function modal(title: string, description?: string): void {
    dialog.oncancel = null;
    dialogContent.replaceChildren(); dialog.classList.remove('ew-diff-dialog');
    const heading = element('div', undefined, 'ew-dialog-heading');
    heading.append(element('h2', title));
    const close = element('button', '×', 'ew-icon-button'); close.type = 'button'; close.setAttribute('aria-label', 'Close dialog'); close.onclick = () => dialog.close(); heading.append(close);
    dialogContent.append(heading);
    if (description) dialogContent.append(element('p', description, 'ew-dialog-description'));
    if (!dialog.open) dialog.showModal();
  }
  function mode(lab: boolean): void {
    document.body.classList.toggle('engineer-mode', !lab);
    modeSwitch.querySelectorAll<HTMLButtonElement>('button').forEach(button => button.setAttribute('aria-pressed', String((button.dataset.mode === 'lab') === lab)));
  }
  modeSwitch.addEventListener('click', event => {
    const button = (event.target as HTMLElement).closest<HTMLButtonElement>('[data-mode]');
    if (button) mode(button.dataset.mode === 'lab');
  });
  const compact = window.matchMedia('(max-width: 1180px)');
  function updateAssistant(): void {
    const visible = compact.matches ? root.classList.contains('ew-assistant-open') : !root.classList.contains('ew-assistant-hidden');
    root.querySelector('#ewYukiToggle')!.setAttribute('aria-expanded', String(visible));
    root.querySelector('#ewAssistant')!.setAttribute('aria-hidden', String(!visible));
  }
  compact.addEventListener('change', () => { root.classList.remove('ew-assistant-open'); updateAssistant(); });
  updateAssistant();
  function setProject(next: Project | null): void {
    if (!next) return;
    project = next; openFile = null; draft = ''; report = null; lastPackage = null; messages = []; proposals = []; renderChat();
    root.querySelector('#ewProjectLabel')!.textContent = next.title;
    root.querySelector('#ewChatContext')!.textContent = `${next.title} · ${next.files.length} files`;
    render();
  }
  function emptyProject(): void {
    content.innerHTML = `<div class="ew-empty"><span class="ew-empty-icon">${icon('folder')}</span><p class="ew-eyebrow">A PLACE FOR YOUR NEXT CHANNEL</p><h1>Start with a project.</h1><p>Open a BrightScript project or create a new channel.<br>Your editor, integrations, and checks live here.</p><div><button class="ew-button ew-primary" data-action="create">${icon('plus')}Create a channel</button><button class="ew-button" data-action="open">${icon('folder')}Open project</button></div></div>`;
  }
  function renderHome(): void {
    content.innerHTML = `<section class="ew-hero"><div><p class="ew-eyebrow"><span></span> FROM FIRST IDEA TO THE BIG SCREEN</p><h1>Build the next<br>thing on <em>TV.</em></h1><p>Your channel, your tools, one workspace.<br>Author with Yuki. Inspect, test, and ship with confidence.</p><div class="ew-hero-actions"><button class="ew-button ew-primary" data-action="create">${icon('plus')}Create a channel</button><button class="ew-button" data-action="open">Open project ${icon('arrow')}</button></div></div><div class="ew-tv-art" aria-hidden="true"><div class="ew-tv-top"><span>YOUR NEXT CHANNEL</span><i></i><i></i><i></i></div><div class="ew-tv-screen"><div class="ew-tv-orbit"></div><div class="ew-tv-grain"></div><span class="ew-tv-caption">Made for<br><b>the big screen.</b></span><span class="ew-tv-tag">SCENEGRAPH CANVAS</span></div><div class="ew-tv-cards"><span></span><span></span><span></span></div><div class="ew-tv-bottom"><span>ROKU ENGINEER</span><span>01 — ∞</span></div></div></section>
      <section class="ew-launchers"><button data-view="project"><span class="ew-launch-icon">${icon('code')}</span><b>Build your channel</b><p>Explore files, edit BrightScript,<br>and scaffold integrations.</p><span class="ew-card-link">Project workspace ${icon('arrow')}</span></button><button data-action="lab"><span class="ew-launch-icon ew-blue">${icon('device')}</span><b>Get closer to the device</b><p>Remote, debugger, network tools,<br>and automated test flows.</p><span class="ew-card-link">Open device lab ${icon('arrow')}</span></button><button data-view="readiness"><span class="ew-launch-icon ew-amber">${icon('shield')}</span><b>Know where you stand</b><p>Check structure and manifest,<br>review findings, build a package.</p><span class="ew-card-link">Channel readiness ${icon('arrow')}</span></button></section>
      <section class="ew-home-bottom"><div><div class="ew-section-heading"><h2>Current project</h2><button data-action="open">Open another ${icon('arrow')}</button></div><div id="ewCurrentProject" class="ew-current-project"></div></div><div class="ew-toolchain"><p class="ew-eyebrow">YOUR TOOLCHAIN, CONNECTED</p><h3>Built for the whole workflow.</h3><p>CLI + MCP · local &amp; remote devices<br>SceneGraph · BrightScript · Yuki AI</p><button data-action="studio-settings">Connect your tools ${icon('arrow')}</button></div></section>`;
    const current = content.querySelector('#ewCurrentProject')!;
    if (project) {
      const button = element('button', undefined, 'ew-recent-project'); button.dataset.view = 'project';
      const mark = element('span', project.title.slice(0, 2).toUpperCase(), 'ew-project-mark');
      const info = element('div'); info.append(element('b', project.title), element('small', `${project.files.length} source files · Local project`));
      button.append(mark, info, element('span', '→')); current.append(button);
    } else current.append(element('p', 'No project open yet. Your next channel starts here.', 'ew-muted'));
  }
  function renderEditor(): void {
    if (!project) { emptyProject(); return; }
    content.innerHTML = `<div class="ew-view-heading"><div><p class="ew-eyebrow">PROJECT WORKSPACE</p><h1 id="ewEditorTitle"></h1></div><button class="ew-button" data-action="reveal">${icon('folder')}Show in folder</button></div><div class="ew-editor"><aside class="ew-file-sidebar"><label for="ewFileFilter">PROJECT FILES</label><input id="ewFileFilter" placeholder="Filter files…" type="search"><div id="ewFileTree"></div></aside><div class="ew-code-pane"><div class="ew-editor-toolbar"><span id="ewFilePath">Select a file</span><span id="ewDirty"></span><button class="ew-button ew-small" data-action="lint">Check file</button><button class="ew-button ew-primary ew-small" data-action="save">Save <kbd>Ctrl S</kbd></button></div><div id="ewCodeEmpty" class="ew-editor-empty">${icon('code')}<h3>Your code, in context.</h3><p>Choose a file from the project tree to start editing.</p></div><textarea id="ewCode" aria-label="Source code editor" spellcheck="false" hidden></textarea><div id="ewLint" class="ew-lint" hidden></div><div class="ew-editor-footer"><span id="ewCursor">UTF-8</span><span>Local file · Conflict-aware saves</span></div></div></div>`;
    content.querySelector('#ewEditorTitle')!.textContent = project.title;
    const tree = content.querySelector<HTMLElement>('#ewFileTree')!;
    const filter = content.querySelector<HTMLInputElement>('#ewFileFilter')!;
    const drawTree = () => {
      tree.replaceChildren();
      const files = project!.files.filter(f => f.path.toLowerCase().includes(filter.value.toLowerCase()));
      for (const file of files) {
        const button = element('button', undefined, 'ew-file'); button.dataset.file = file.path;
        button.classList.toggle('selected', file.path === openFile?.path);
        button.title = file.path;
        const ext = file.path.split('.').pop();
        button.append(element('span', ext === 'brs' || ext === 'bs' ? 'B' : ext === 'xml' ? '<>' : '·', 'ew-file-kind'), element('span', file.path));
        tree.append(button);
      }
      if (!files.length) tree.append(element('p', 'No matching files.', 'ew-muted'));
    };
    filter.oninput = drawTree; drawTree();
    const editor = content.querySelector<HTMLTextAreaElement>('#ewCode')!;
    if (openFile) { editor.value = draft; editor.hidden = false; content.querySelector<HTMLElement>('#ewCodeEmpty')!.hidden = true; content.querySelector('#ewFilePath')!.textContent = openFile.path; }
    const update = () => {
      draft = editor.value;
      content.querySelector('#ewDirty')!.textContent = dirty() ? 'Unsaved' : 'Saved';
      const before = editor.value.slice(0, editor.selectionStart); const lines = before.split('\n');
      content.querySelector('#ewCursor')!.textContent = `Ln ${lines.length}, Col ${lines[lines.length - 1].length + 1} · UTF-8`;
    };
    editor.oninput = update; editor.onclick = update; editor.onkeyup = update;
    editor.onkeydown = event => {
      if (event.key === 'Tab') { event.preventDefault(); const start = editor.selectionStart; editor.setRangeText('    ', start, editor.selectionEnd, 'end'); update(); }
    };
  }
  function renderIntegrations(): void {
    content.innerHTML = `<div class="ew-view-heading"><div><p class="ew-eyebrow">LESS BOILERPLATE. MORE CHANNEL.</p><h1>Plug into the platform.</h1><p>Purpose-built scaffolds from the Roku Engineer engine.<br>Preview every file before applying changes to your project.</p></div><span class="ew-chip">7 INTEGRATIONS</span></div><div class="ew-integrations" id="ewIntegrations"></div><div class="ew-disclosure">Generated code is a starting point. Check API support on your target firmware, configure your backend, and validate on a real device.</div>`;
    for (const [id, number, title, description, category] of generators) {
      const card = element('article', undefined, 'ew-integration');
      const top = element('div', undefined, 'ew-integration-top'); top.append(element('span', number), element('span', category, 'ew-chip'));
      const button = element('button', 'Preview integration →', 'ew-button'); button.dataset.generator = id;
      card.append(top, element('h2', title), element('p', description), button); content.querySelector('#ewIntegrations')!.append(card);
    }
  }
  function renderReadiness(): void {
    if (!project) { emptyProject(); return; }
    content.innerHTML = `<div class="ew-view-heading"><div><p class="ew-eyebrow">BUILD WITH EVIDENCE</p><h1>Channel readiness.</h1><p>Find local issues, review the evidence, and package your channel.</p></div><button class="ew-button ew-primary" data-action="validate">${icon('shield')}Run project checks</button></div><div class="ew-readiness-grid"><article><span class="ew-eyebrow">01 / LOCAL CHECKS</span><h2 id="ewReportStatus">Not checked yet</h2><p>Structure, manifest, SceneGraph, accessibility hints, and certification heuristics.</p><span id="ewReportTime" class="ew-muted">Run checks to see this project's report.</span></article><article><span class="ew-eyebrow">02 / DEVICE VALIDATION</span><h2>Bring your own device.</h2><p>Use the lab for debugging, performance inspection, traffic capture, and action scripts.</p><button class="ew-button" data-action="lab">Open device lab ${icon('arrow')}</button></article><article><span class="ew-eyebrow">03 / BUILD ARTIFACT</span><h2>Package your channel.</h2><p>Create a ZIP with manifest and assets. Secrets, development caches, and symlinks are excluded.</p><button class="ew-button" data-action="package">Build channel ZIP ${icon('arrow')}</button></article></div><section class="ew-report-section"><div class="ew-section-heading"><h2>Validation report</h2><button data-action="export-report">Export report ${icon('arrow')}</button></div><pre id="ewReport"></pre></section><div id="ewPackageResult"></div><div class="ew-disclosure">Local checks are heuristic. They do not certify your channel. Use File → Static Channel Analysis for Roku's official tooling and test on representative devices before submitting.</div>`;
    if (report) { content.querySelector('#ewReportStatus')!.textContent = report.status === 'passed' ? 'Local checks passed' : report.status === 'warnings' ? 'Review warnings' : 'Issues to resolve'; content.querySelector('#ewReportStatus')!.className = `ew-report-${report.status}`; content.querySelector('#ewReportTime')!.textContent = report.at; }
    content.querySelector('#ewReport')!.textContent = report?.report ?? 'No report yet. Run project checks to start.';
    if (lastPackage) {
      const card = element('div', undefined, 'ew-artifact'); const info = element('div'); info.append(element('b', 'Channel package created'), element('p', lastPackage.path), element('code', `SHA-256 ${lastPackage.sha256}`));
      const reveal = element('button', `Show ZIP · ${(lastPackage.size / 1024).toFixed(1)} KB`, 'ew-button'); reveal.dataset.action = 'reveal'; card.append(info, reveal); content.querySelector('#ewPackageResult')!.append(card);
    }
  }
  function renderSettings(): void {
    content.innerHTML = `<div class="ew-view-heading"><div><p class="ew-eyebrow">MAKE IT YOURS</p><h1>Workspace settings.</h1><p>Project tools work offline. Configure Anthropic to use Yuki.</p></div></div><form id="ewSettingsForm" class="ew-settings-form"><section><h2>${icon('spark')} Yuki assistant</h2><label for="ewModel">Anthropic model ID</label><input id="ewModel" name="model" required pattern="[a-zA-Z0-9_.:-]{1,120}" placeholder="Your account's model ID"><p>Use a model available to your Anthropic account. Availability and billing are managed by Anthropic.</p><label for="ewApiKey">API key <span id="ewKeyStatus"></span></label><input id="ewApiKey" name="apiKey" type="password" autocomplete="off" placeholder="Leave blank to keep the current key"><p id="ewEncryptionNote">Stored through the operating system's encrypted storage. The renderer never receives the saved key.</p><label class="ew-checkbox"><input id="ewClearKey" type="checkbox"> Remove the saved key (environment keys remain available)</label></section><section><h2>${icon('code')} Python engine</h2><label for="ewPython">Python executable</label><input id="ewPython" name="python" placeholder="Automatic (.venv, then python)"><p>Install Python and run <code>python -m pip install -r requirements.txt</code> in the engine folder. A project-local .venv is detected automatically.</p><label>Engine folder</label><code id="ewEnginePath" class="ew-engine-path"></code></section><div><button class="ew-button ew-primary" type="submit">Save settings</button><button class="ew-button" type="button" data-action="test-runtime">Test Python connection</button></div><div class="ew-disclosure">Your project is local. Chat sends messages and files Yuki reads to Anthropic. Do not put secrets in source files or chat. Existing CLI voice mode, web research, and automode remain available through <code>python roku_engineer.py</code>.</div></form>`;
    if (config) {
      content.querySelector<HTMLInputElement>('#ewModel')!.value = config.model;
      content.querySelector<HTMLInputElement>('#ewPython')!.value = config.python;
      content.querySelector('#ewKeyStatus')!.textContent = config.hasKey ? 'Configured' : 'Not configured';
      content.querySelector('#ewEnginePath')!.textContent = config.engineDir;
      if (!config.encryptedStorage) { content.querySelector<HTMLInputElement>('#ewApiKey')!.disabled = true; content.querySelector('#ewEncryptionNote')!.textContent = 'Encrypted storage is unavailable. Set ANTHROPIC_API_KEY in your environment to enable Yuki.'; }
    }
    content.querySelector<HTMLFormElement>('#ewSettingsForm')!.onsubmit = event => {
      event.preventDefault();
      const key = content.querySelector<HTMLInputElement>('#ewApiKey')!;
      void work('Saving workspace settings…', async () => {
        config = await request({ action: 'configure', model: content.querySelector<HTMLInputElement>('#ewModel')!.value, python: content.querySelector<HTMLInputElement>('#ewPython')!.value, apiKey: key.value, clearKey: content.querySelector<HTMLInputElement>('#ewClearKey')!.checked });
        key.value = ''; updateConfig(); renderSettings(); notify('Workspace settings saved.');
      });
    };
  }
  function render(): void {
    if (project) {
      root.querySelector('#ewProjectLabel')!.textContent = project.title;
      root.querySelector('#ewChatContext')!.textContent = `${project.title} · ${project.files.length} files`;
    }
    root.querySelectorAll<HTMLElement>('[data-view]').forEach(button => { button.classList.toggle('active', button.dataset.view === view); if (button.closest('nav')) button.setAttribute('aria-current', button.dataset.view === view ? 'page' : 'false'); });
    root.querySelector('#ewViewLabel')!.textContent = ({ home: 'Overview', project: 'Project editor', integrations: 'Integrations', readiness: 'Readiness', settings: 'Settings' })[view];
    content.classList.toggle('ew-editor-content', view === 'project' && Boolean(project));
    ({ home: renderHome, project: renderEditor, integrations: renderIntegrations, readiness: renderReadiness, settings: renderSettings })[view]();
  }
  async function navigate(next: View): Promise<void> {
    if (compact.matches) { root.classList.remove('ew-assistant-open'); updateAssistant(); }
    view = next; render();
  }
  function createDialog(): void {
    modal('A new channel starts here.', 'Choose a template and a channel name. You’ll pick the parent folder next.');
    const form = element('form', undefined, 'ew-create-form');
    form.innerHTML = '<label for="ewChannelName">Channel name</label><input id="ewChannelName" name="channelName" required maxlength="64" pattern="[A-Za-z0-9][A-Za-z0-9 _-]{0,63}" placeholder="e.g. My Streaming Channel" autofocus><label for="ewTemplate">Starting template</label><select id="ewTemplate"><option value="basic">SceneGraph · clean starting point</option><option value="grid">Content grid · RowList browsing</option><option value="sgdex">SGDEX · requires official SGDEX components</option></select><p>Includes a manifest, launch loop, memory monitoring, deep link routing, and starter artwork. Configure and test before publishing.</p><div class="ew-dialog-actions"><button type="button" class="ew-button" id="ewCreateCancel">Cancel</button><button type="submit" class="ew-button ew-primary">Choose folder &amp; create →</button></div>';
    form.querySelector<HTMLButtonElement>('#ewCreateCancel')!.onclick = () => dialog.close();
    form.onsubmit = event => {
      event.preventDefault();
      const name = form.querySelector<HTMLInputElement>('#ewChannelName')!.value;
      const kind = form.querySelector<HTMLSelectElement>('#ewTemplate')!.value;
      dialog.close();
      void work('Creating your channel…', async () => { const created = await request<Project | null>({ action: 'scaffold', name, kind }); if (created) { setProject(created); await navigate('project'); notify('Channel created. Select a file to begin.'); } });
    };
    dialogContent.append(form);
  }
  function review(proposal: Proposal, onApplied?: () => void): void {
    modal(proposal.title, `${proposal.changes.length} file${proposal.changes.length === 1 ? '' : 's'} in this proposal. Review before applying. Existing versions are backed up under .engineer/history.`);
    dialog.classList.add('ew-diff-dialog');
    const tabs = element('div', undefined, 'ew-diff-tabs');
    const panes = element('div', undefined, 'ew-diff-panes');
    const before = element('pre'); const after = element('pre');
    const left = element('section'); left.append(element('h3', 'CURRENT FILE'), before);
    const right = element('section'); right.append(element('h3', 'PROPOSED FILE'), after); panes.append(left, right);
    const show = (index: number) => {
      const change = proposal.changes[index]; if (!change) return;
      before.textContent = change.before || '(new file)'; after.textContent = change.content;
      Array.from(tabs.children).forEach((tab, i) => tab.classList.toggle('active', i === index));
    };
    proposal.changes.forEach((change, i) => { const tab = element('button', change.path); tab.type = 'button'; tab.onclick = () => show(i); tabs.append(tab); });
    const actions = element('div', undefined, 'ew-dialog-actions');
    const cancel = element('button', 'Keep reviewing later', 'ew-button'); cancel.type = 'button'; cancel.onclick = () => dialog.close();
    const apply = element('button', 'Apply reviewed changes', 'ew-button ew-primary'); apply.type = 'button'; apply.disabled = !proposal.changes.length;
    apply.onclick = () => {
      if (dirty()) { notify('Save your editor changes before applying a proposal.', true); return; }
      dialog.close();
      void work('Applying reviewed changes…', async () => {
        const result = await request({ action: 'apply', changes: proposal.changes });
        project = { ...result.project, revision: project!.revision };
        if (openFile && result.changed.includes(openFile.path)) { openFile = await request({ action: 'read', path: openFile.path }); draft = openFile!.content; }
        report = null; onApplied?.(); render(); notify(`Applied ${result.changed.length} file changes. Previous versions saved.`);
      });
    };
    actions.append(cancel, apply); dialogContent.append(tabs, panes, actions); show(0);
    if (!proposal.changes.length) { before.textContent = 'No file changes.'; after.textContent = 'This integration already matches the generated output.'; }
  }
  function renderChat(): void {
    chat.replaceChildren();
    if (!messages.length) {
      const intro = element('div', undefined, 'ew-chat-intro');
      intro.innerHTML = `<span class="ew-chat-orbit">${icon('spark')}</span><h2>A little guidance.<br>A lot of possibility.</h2><p>Ask Yuki to explore your channel, investigate an issue, or propose your next integration.</p><div><button data-prompt="Review this channel and identify the most useful improvements.">Review my channel ${icon('arrow')}</button><button data-prompt="Explain how this channel is organized and where to start.">Help me find my way ${icon('arrow')}</button><button data-prompt="Propose deep linking using the existing generator and explain how to wire it into my Scene.">Add deep link routing ${icon('arrow')}</button></div>`;
      chat.append(intro);
    }
    messages.forEach((message, messageIndex) => {
      const bubble = element('article', undefined, `ew-message ew-${message.role}`); bubble.append(element('small', message.role === 'user' ? 'YOU' : 'YUKI'), element('p', message.content)); chat.append(bubble);
      for (const entry of proposals.filter(p => p.messageIndex === messageIndex)) {
        const card = element('div', undefined, 'ew-proposal'); card.append(element('b', entry.proposal.title), element('small', entry.applied ? 'Applied to your project' : `${entry.proposal.changes.length} files · Pending review`));
        const button = element('button', entry.applied ? 'Applied' : 'Review changes →', 'ew-button'); button.disabled = entry.applied;
        button.onclick = () => review(entry.proposal, () => { entry.applied = true; renderChat(); }); card.append(button); chat.append(card);
      }
    });
    chat.scrollTop = chat.scrollHeight;
  }
  function updateConfig(): void { root.querySelector('#ewChatModel')!.textContent = config?.hasKey ? config.model : 'Anthropic · configure a key'; }
  async function sendChat(): Promise<void> {
    if (busy || chatBusy) return;
    if (!project) { notify('Open a project so Yuki can work with your channel.'); return; }
    if (!config?.hasKey) { void navigate('settings'); notify('Configure an Anthropic API key to enable Yuki.'); return; }
    const text = chatInput.value.trim(); if (!text) return;
    messages.push({ role: 'user', content: text }); chatInput.value = ''; renderChat();
    chatBusy = true; chatForm.classList.add('ew-chat-busy'); root.querySelector<HTMLElement>('#ewCancelChat')!.hidden = false;
    const pending = element('p', 'Reading your channel and thinking…', 'ew-thinking'); chat.append(pending);
    try {
      const result = await request<{ text: string; proposals: Proposal[]; usage: { input: number; output: number } }>({ action: 'chat', messages });
      messages.push({ role: 'assistant', content: result.text || 'I prepared the following changes for review.' });
      proposals.push(...result.proposals.map(proposal => ({ proposal, messageIndex: messages.length - 1, applied: false })));
      renderChat();
      chat.append(element('small', `${result.usage.input.toLocaleString()} input · ${result.usage.output.toLocaleString()} output tokens`, 'ew-token-usage'));
      chat.scrollTop = chat.scrollHeight;
    } catch (error) { pending.remove(); chat.append(element('p', error instanceof Error ? error.message : 'Yuki could not complete the request.', 'ew-chat-error')); }
    finally { chatBusy = false; chatForm.classList.remove('ew-chat-busy'); root.querySelector<HTMLElement>('#ewCancelChat')!.hidden = true; }
  }
  function commands(): void {
    modal('Jump to anything');
    const search = element('input'); search.placeholder = 'Search views, tools, or project files…'; search.setAttribute('aria-label', 'Search commands');
    const list = element('div', undefined, 'ew-command-list');
    const entries = [
      { label: 'Overview', run: () => navigate('home') }, { label: 'Project editor', run: () => navigate('project') },
      { label: 'Integrations', run: () => navigate('integrations') }, { label: 'Channel readiness', run: () => navigate('readiness') },
      { label: 'Workspace settings', run: () => navigate('settings') }, { label: 'Device lab', run: () => mode(true) },
      ...(project?.files ?? []).map(file => ({ label: file.path, run: async () => { if (await canLeave()) await work('Opening file…', async () => { openFile = await request({ action: 'read', path: file.path }); draft = openFile!.content; await navigate('project'); }); } })),
    ];
    const draw = () => { list.replaceChildren(); for (const entry of entries.filter(e => e.label.toLowerCase().includes(search.value.toLowerCase())).slice(0, 40)) { const button = element('button', entry.label); button.type = 'button'; button.onclick = () => { dialog.close(); void entry.run(); }; list.append(button); } if (!list.children.length) list.append(element('p', 'No matches.')); };
    search.oninput = draw; search.onkeydown = event => { if (event.key === 'ArrowDown') { event.preventDefault(); list.querySelector('button')?.focus(); } if (event.key === 'Enter') { event.preventDefault(); list.querySelector('button')?.click(); } };
    dialogContent.append(search, list); draw(); search.focus();
  }
  const actions: Record<string, () => void | Promise<unknown>> = {
    open: async () => { if (await canLeave()) await work('Opening project…', async () => setProject(await request({ action: 'pick' }))); },
    create: async () => { if (await canLeave()) createDialog(); },
    refresh: async () => { if (project && await canLeave()) await work('Refreshing project…', async () => { project = await request({ action: 'project' }); openFile = null; draft = ''; render(); }); },
    save: async () => { if (!openFile) return; await work('Saving file…', async () => { const result = await request({ action: 'apply', changes: [{ path: openFile!.path, beforeSha256: openFile!.sha256, content: draft }] }); project = { ...result.project, revision: project!.revision }; openFile = await request({ action: 'read', path: openFile!.path }); draft = openFile!.content; report = null; render(); notify('Saved. Previous version backed up.'); }); },
    lint: async () => { if (!openFile) return; await work('Checking file…', async () => { const result = await request({ action: 'lint', content: draft }); const lint = content.querySelector<HTMLElement>('#ewLint'); if (lint) { lint.textContent = result.report; lint.hidden = false; } }); },
    validate: async () => { await work('Running local project checks…', async () => { report = { ...await request<{ report: string; status: string; scope: string }>({ action: 'validate' }), at: new Date().toLocaleString() }; renderReadiness(); }); },
    package: async () => { if (dirty()) { notify('Save your editor changes before building a ZIP.'); return; } await work('Building channel package…', async () => { lastPackage = await request({ action: 'package' }); renderReadiness(); notify('Channel ZIP created.'); }); },
    reveal: async () => { await work('Opening folder…', () => request({ action: 'reveal' })); },
    'export-report': async () => { if (!report) { notify('Run checks before exporting a report.'); return; } await work('Exporting report…', () => request({ action: 'export-report', content: `# Roku Engineer local validation\n\nProject: ${project?.title}\nDate: ${report!.at}\nStatus: ${report!.status}\n\n${report!.report}\n\n${report!.scope}\n` })); },
    lab: () => mode(true),
    scripts: () => work('Opening action scripts…', () => request({ action: 'tool', name: 'scripts' })),
    fiddle: () => work('Opening BrightScript Fiddle…', () => request({ action: 'tool', name: 'fiddle' })),
    analysis: () => work('Opening static analysis…', () => request({ action: 'tool', name: 'analysis' })),
    'studio-settings': () => window.roku.openSettings('mcp'),
    about: () => { modal('Roku Engineer Studio', 'Independent tooling by Cavanaugh Design Studio.'); const credit = element('p', 'The device studio, libraries, relay, MCP server, and companion components derive from Roku Dev Studio, Copyright © 2026 Paramount Streaming (Hareendra Donapati), licensed under MIT. Yuki, the original Python engine, and this workspace are integrated and maintained by Cavanaugh Design Studio. Full notices are included in third_party/ and packaged resources.'); dialogContent.append(credit); },
    commands,
    'toggle-yuki': () => { root.classList.toggle(compact.matches ? 'ew-assistant-open' : 'ew-assistant-hidden'); updateAssistant(); if (root.querySelector('#ewYukiToggle')!.getAttribute('aria-expanded') === 'false') root.querySelector<HTMLButtonElement>('#ewYukiToggle')!.focus(); },
    'reset-chat': () => { if (!chatBusy) { messages = []; proposals = []; renderChat(); } },
    'cancel-chat': () => request({ action: 'cancel' }),
    'test-runtime': () => work('Testing Python engine…', async () => { const result = await request({ action: 'status' }); root.querySelector('#ewRuntime')!.textContent = `Python ${result.python} · connected`; notify(`Python ${result.python} connected.`); }),
  };
  root.addEventListener('click', event => {
    const button = (event.target as HTMLElement).closest<HTMLButtonElement>('button'); if (!button || button.disabled) return;
    if (button.dataset.view) { if (!busy && !chatBusy) void navigate(button.dataset.view as View); }
    else if (button.dataset.action && actions[button.dataset.action]) void actions[button.dataset.action]();
    else if (button.dataset.file) void (async () => { if (!await canLeave()) return; await work('Opening file…', async () => { openFile = await request({ action: 'read', path: button.dataset.file }); draft = openFile!.content; renderEditor(); }); })();
    else if (button.dataset.generator) void work('Preparing integration preview…', async () => { if (!project) throw new Error('Open a project before adding an integration.'); if (dirty()) throw new Error('Save your editor changes before generating an integration.'); const proposal = await request<Proposal>({ action: 'preview', generator: button.dataset.generator }); review(proposal); });
    else if (button.dataset.prompt) { chatInput.value = button.dataset.prompt; chatInput.focus(); }
  });
  chatForm.onsubmit = event => { event.preventDefault(); void sendChat(); };
  chatInput.onkeydown = event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void sendChat(); } };
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !dialog.open && compact.matches) { root.classList.remove('ew-assistant-open'); updateAssistant(); }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); mode(false); commands(); }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's' && document.body.classList.contains('engineer-mode') && view === 'project') { event.preventDefault(); void actions.save(); }
  });
  // Keep unsaved editor contents when switching workspace views; warn before the window closes.
  window.addEventListener('beforeunload', event => { if (dirty()) { event.preventDefault(); event.returnValue = ''; } });
  mode(false); render(); renderChat();
  void (async () => {
    try {
      config = await request({ action: 'settings' }); updateConfig();
      const restored = await request<Project | null>({ action: 'restore' }); if (restored) setProject(restored);
      const info = await request({ action: 'status' }); root.querySelector('#ewRuntime')!.textContent = `Python ${info.python} · connected`;
    } catch (error) { root.querySelector('#ewRuntime')!.textContent = 'Python setup needed'; notify(error instanceof Error ? error.message : 'Engine setup needed.', true); }
  })();
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true }); else boot();
