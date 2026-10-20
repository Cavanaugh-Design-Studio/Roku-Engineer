import { spawn } from 'node:child_process';
import * as path from 'node:path';
import * as fs from 'node:fs';

export type PythonOptions = { engineDir: string; python?: string; signal?: AbortSignal; timeoutMs?: number };

export function pythonExecutable(engineDir: string, configured?: string): string {
  if (configured?.trim()) return configured.trim();
  const virtual = path.join(engineDir, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  return fs.existsSync(virtual) ? virtual : process.platform === 'win32' ? 'python' : 'python3';
}

export async function runEngine(request: Record<string, unknown>, options: PythonOptions): Promise<any> {
  if (options.signal?.aborted) throw new Error('Operation cancelled.');
  return new Promise((resolve, reject) => {
    const child = spawn(pythonExecutable(options.engineDir, options.python), ['-X', 'utf8', path.join(options.engineDir, 'engineer_bridge.py')], {
      cwd: options.engineDir, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' },
    });
    let output = Buffer.alloc(0);
    let settled = false;
    const finish = (error?: Error, data?: unknown) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      options.signal?.removeEventListener('abort', abort);
      error ? reject(error) : resolve(data);
    };
    const abort = () => { child.kill(); finish(new Error('Operation cancelled. Refresh the project before retrying a write.')); };
    const timer = setTimeout(() => { child.kill(); finish(new Error('Python operation timed out. Check the Python path and dependencies, then refresh the project.')); }, options.timeoutMs ?? 60000);
    options.signal?.addEventListener('abort', abort, { once: true });
    child.on('error', () => finish(new Error('Python could not start. Install Python and requirements.txt, or set a Python executable in Workspace Settings.')));
    child.stdin.on('error', () => { /* close/error handler reports the process result */ });
    child.stdout.on('data', chunk => {
      output = Buffer.concat([output, chunk]);
      if (output.length > 10 * 1024 * 1024) { child.kill(); finish(new Error('Engine response exceeded the 10 MB limit.')); }
    });
    // Optional library warnings can contain local paths. Do not forward stderr to renderer/logs.
    child.stderr.resume();
    child.on('close', code => {
      if (settled) return;
      try {
        const parsed = JSON.parse(output.toString('utf8'));
        if (code !== 0 || !parsed.ok) finish(new Error(parsed.error || 'Python engine failed. Install requirements.txt for authoring tools.'));
        else finish(undefined, parsed.data);
      } catch { finish(new Error('Python engine returned an invalid response. Verify Python and requirements.txt are installed.')); }
    });
    child.stdin.end(JSON.stringify(request));
  });
}
