import { spawn } from 'node:child_process';
import * as net from 'node:net';
import * as path from 'node:path';
import { randomBytes } from 'node:crypto';
import assert from 'node:assert/strict';
import * as fs from 'node:fs/promises';
const root = path.resolve(import.meta.dirname, '..');
const children = [];
try {
  const mcp = spawn(process.execPath, [path.join(root, 'packages/roku-engineer-studio-mcp/dist/index.cjs')], { windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'] });
  children.push(mcp); mcp.stderr.resume();
  const pending = new Map(); let sequence = 0; let buffer = '';
  mcp.stdout.on('data', chunk => {
    buffer += chunk;
    let newline;
    while ((newline = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, newline); buffer = buffer.slice(newline + 1);
      const message = JSON.parse(line); const waiter = pending.get(message.id);
      if (waiter) { clearTimeout(waiter.timer); pending.delete(message.id); waiter.resolve(message); }
    }
  });
  function rpc(method, params = {}) {
    const id = ++sequence;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { pending.delete(id); reject(new Error(`MCP timed out: ${method}`)); }, 10000);
      pending.set(id, { resolve, timer }); mcp.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
    });
  }
  const initialize = await rpc('initialize', { protocolVersion: '2024-11-05', capabilities: {}, clientInfo: { name: 'roku-engineer-smoke', version: '1.0.0' } });
  assert.equal(initialize.result.serverInfo.name, 'roku-engineer-studio');
  mcp.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) + '\n');
  const tools = await rpc('tools/list');
  assert.ok(tools.result.tools.length > 20);
  const resources = await rpc('resources/list');
  assert.ok(resources.result.resources.length > 0);
  const prompts = await rpc('prompts/list');
  const validation = await rpc('tools/call', { name: 'validate_script', arguments: { script: { steps: [{ type: 'wait', delayMs: 25 }] } } });
  assert.ok(!validation.error);
  assert.ok(!validation.result.isError, JSON.stringify(validation));
  const reserve = net.createServer();
  await new Promise(resolve => reserve.listen(0, '127.0.0.1', resolve));
  const port = reserve.address().port; await new Promise(resolve => reserve.close(resolve));
  const token = randomBytes(32).toString('hex');
  const relay = spawn(process.execPath, [path.join(root, 'packages/roku-engineer-studio-remote-server/roku-remote-server.js'), String(port)], { windowsHide: true, env: { ...process.env, ROKU_ENGINEER_RELAY_TOKEN: token }, stdio: ['ignore', 'pipe', 'pipe'] });
  children.push(relay); relay.stderr.resume();
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Relay startup timed out')), 15000);
    relay.on('error', reject);
    relay.stdout.on('data', chunk => { if (chunk.toString().includes('Roku Remote Server started')) { clearTimeout(timer); resolve(); } });
  });
  const base = `http://127.0.0.1:${port}`;
  assert.equal((await fetch(base + '/health')).status, 200);
  assert.equal((await fetch(base + '/capabilities')).status, 401);
  assert.equal((await fetch(base + '/capabilities', { headers: { authorization: `Bearer ${token}` } })).status, 200);
  const result = { mcpTools: tools.result.tools.length, mcpResources: resources.result.resources.length, mcpPrompts: prompts.result.prompts.length, scriptValidation: true, relayHealth: true, relayRejectsMissingToken: true, relayAcceptsConfiguredToken: true, deviceCommandsSent: 0 };
  await fs.mkdir(path.join(root, 'artifacts'), { recursive: true });
  await fs.writeFile(path.join(root, 'artifacts/transport-smoke.json'), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
} finally {
  for (const child of children) child.kill();
}
