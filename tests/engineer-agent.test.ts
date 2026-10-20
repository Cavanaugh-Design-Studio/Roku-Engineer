import { test } from 'node:test';
import assert from 'node:assert/strict';
import { runEngineerAgent, type AgentOptions } from '../apps/roku-engineer-studio/main/engineer-agent';
import { runEngine } from '../apps/roku-engineer-studio/main/engineer-runtime';
import * as path from 'node:path';

const base: AgentOptions = {
  apiKey: 'test-key-never-sent-to-provider', model: 'fixture-model', messages: [{ role: 'user', content: 'Improve my channel' }],
  project: { title: 'Fixture', files: [{ path: 'source/main.brs', sha256: 'original' }] },
  call: async () => { throw new Error('Unexpected tool'); },
};
const response = (content: unknown[]) => new Response(JSON.stringify({ content, usage: { input_tokens: 10, output_tokens: 5 } }), { status: 200 });

test('agent reads context and returns a file proposal without writing', async () => {
  const calls: Record<string, unknown>[] = [];
  let turn = 0;
  const result = await runEngineerAgent({ ...base,
    call: async request => { calls.push(request); return { content: 'sub Main()\nend sub', sha256: 'original' }; },
    fetcher: async (url, init) => {
      assert.equal(url, 'https://api.anthropic.com/v1/messages');
      const body = JSON.parse(String(init?.body));
      assert.equal(body.model, 'fixture-model');
      if (turn++ === 0) return response([{ type: 'tool_use', id: 'a', name: 'propose_file', input: { path: 'source/main.brs', content: 'sub Main()\nprint "hello"\nend sub', reason: 'Add a log line' } }]);
      assert.equal(body.messages.at(-1).content[0].type, 'tool_result');
      return response([{ type: 'text', text: 'Review the proposed log line.' }]);
    },
  });
  assert.deepEqual(calls, [{ action: 'read', path: 'source/main.brs' }]);
  assert.equal(result.proposals[0].changes[0].beforeSha256, 'original');
  assert.match(result.text, /proposed/);
  assert.deepEqual(result.usage, { input: 20, output: 10 });
});

test('generator proposals only request a preview', async () => {
  const calls: any[] = [];
  let turn = 0;
  const result = await runEngineerAgent({ ...base, call: async req => { calls.push(req); return { title: 'Memory', changes: [{ path: 'source/Memory.brs', content: 'code', beforeSha256: null }] }; },
    fetcher: async () => turn++ === 0 ? response([{ type: 'tool_use', id: 'a', name: 'propose_generator', input: { generator: 'memory' } }]) : response([{ type: 'text', text: 'Ready for review.' }]),
  });
  assert.deepEqual(calls, [{ action: 'preview', generator: 'memory' }]);
  assert.equal(result.proposals.length, 1);
});

test('provider errors never echo response bodies or API keys', async () => {
  await assert.rejects(runEngineerAgent({ ...base, fetcher: async () => new Response('sensitive request echo', { status: 401, headers: { 'request-id': 'fixture-123' } }) }), error => {
    assert.match(String(error), /HTTP 401/); assert.match(String(error), /fixture-123/); assert.doesNotMatch(String(error), /sensitive|test-key/); return true;
  });
});

test('no key causes a local error before any network call', async () => {
  await assert.rejects(runEngineerAgent({ ...base, apiKey: '', fetcher: async () => { throw new Error('Network must not run'); } }), /API key/);
});

test('unknown tools produce a tool error, never an arbitrary command', async () => {
  let turn = 0;
  await runEngineerAgent({ ...base, fetcher: async (_url, init) => {
    if (turn++ === 0) return response([{ type: 'tool_use', id: 'x', name: 'run_shell_command', input: { command: 'anything' } }]);
    const body = JSON.parse(String(init?.body)); assert.equal(body.messages.at(-1).content[0].is_error, true);
    return response([{ type: 'text', text: 'Unavailable.' }]);
  } });
});

test('bounded tool loop stops runaway agent requests', async () => {
  await assert.rejects(runEngineerAgent({ ...base, call: async () => ({}), fetcher: async () => response(Array.from({ length: 17 }, (_, i) => ({ type: 'tool_use', id: `t${i}`, name: 'validate_project', input: {} }))) }), /16-tool limit/);
});

test('cancelled requests do not call the provider', async () => {
  const controller = new AbortController(); controller.abort();
  await assert.rejects(runEngineerAgent({ ...base, signal: controller.signal, fetcher: async () => { throw new Error('Network must not run'); } }), /abort/i);
});

test('Python child protocol handles valid JSON and engine errors', async () => {
  const engineDir = path.resolve('.');
  const status = await runEngine({ action: 'status' }, { engineDir });
  assert.equal(status.generators.length, 7);
  await assert.rejects(runEngine({ action: 'not-a-real-action', root: engineDir }, { engineDir }), /Unknown workspace action/);
});
