import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { once } from 'node:events';
import { createApp } from '../src/app.js';
import { createRepository } from '../src/repository.js';

async function fixture(t, options) {
  const directory = mkdtempSync(join(tmpdir(), 'todolist-api-'));
  const repository = createRepository(join(directory, 'test.sqlite'));
  const server = createApp(repository, options).listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(async () => {
    await new Promise((resolve) => server.close(resolve));
    repository.close();
    rmSync(directory, { recursive: true, force: true });
  });
  const url = `http://127.0.0.1:${server.address().port}`;
  return { url, request: async (path = '', { method = 'GET', body, raw } = {}) => {
    const response = await fetch(`${url}/api/todos${path}`, {
      method, headers: { 'Content-Type': 'application/json' }, body: raw ?? (body === undefined ? undefined : JSON.stringify(body)),
    });
    return { status: response.status, location: response.headers.get('location'), body: response.status === 204 ? null : await response.json() };
  } };
}

test('task lifecycle, clearing optional fields, repeated toggles and missing IDs', async (t) => {
  const { request } = await fixture(t);
  assert.deepEqual((await request()).body, []);
  const created = await request('', { method: 'POST', body: { title: '  Interview task  ', description: 'Notes', dueDate: '2024-02-29' } });
  assert.equal(created.status, 201);
  assert.match(created.body.id, /^[0-9a-f-]{36}$/);
  assert.equal(created.location, `/api/todos/${created.body.id}`);
  assert.equal(created.body.title, 'Interview task');
  assert.equal(created.body.isCompleted, false);
  assert.equal(new Date(created.body.createdAt).toISOString(), created.body.createdAt);
  const path = `/${created.body.id}`;
  assert.deepEqual((await request(path)).body, created.body);
  const edited = await request(path, { method: 'PATCH', body: { title: 'Updated' } });
  assert.equal(edited.body.description, 'Notes');
  assert.equal(edited.body.dueDate, '2024-02-29');
  assert.equal(edited.body.createdAt, created.body.createdAt);
  for (const state of [true, true, false, false]) {
    const response = await request(path, { method: 'PATCH', body: { isCompleted: state } });
    assert.equal(response.status, 200);
    assert.equal(response.body.isCompleted, state);
  }
  const cleared = await request(path, { method: 'PATCH', body: { description: null, dueDate: null } });
  assert.equal(cleared.body.description, null);
  assert.equal(cleared.body.dueDate, null);
  assert.deepEqual((await request()).body, [cleared.body]);
  assert.equal((await request(path, { method: 'DELETE' })).status, 204);
  for (const options of [{}, { method: 'PATCH', body: { title: 'Updated' } }, { method: 'DELETE' }]) {
    const response = await request(path, options);
    assert.equal(response.status, 404);
    assert.equal(response.body.error.message, 'Task not found.');
  }
});

test('defaults, duplicate titles, past dates and full calendar range', async (t) => {
  const { request } = await fixture(t);
  for (const dueDate of ['0001-01-01', '9999-12-31', null]) {
    const response = await request('', { method: 'POST', body: { title: 'Same', dueDate } });
    assert.equal(response.status, 201);
    assert.equal(response.body.description, null);
    assert.equal(response.body.isCompleted, false);
  }
  assert.equal((await request()).body.length, 3);
});

test('invalid types, dates, fields, malformed bodies and empty updates', async (t) => {
  const { request } = await fixture(t);
  const bodies = [null, [], {}, { title: ' ' }, { title: 1 }, { title: 'x'.repeat(201) },
    { title: 'ok', description: false }, { title: 'ok', description: 'x'.repeat(5001) },
    { title: 'ok', dueDate: '2025-02-29' }, { title: 'ok', dueDate: '2024-04-31' },
    { title: 'ok', dueDate: '0000-01-01' }, { title: 'ok', dueDate: '2024-2-01' },
    { title: 'ok', dueDate: 1 }, { title: 'ok', isCompleted: true }, { title: 'ok', id: 'mine' }];
  for (const body of bodies) {
    const response = await request('', { method: 'POST', body });
    assert.equal(response.status, 400, JSON.stringify(body));
    assert.equal(typeof response.body.error.message, 'string');
  }
  assert.equal((await request('', { method: 'POST', raw: '{oops' })).status, 400);
  assert.equal((await request('', { method: 'POST', raw: JSON.stringify({ title: 'x'.repeat(110000) }) })).status, 400);
  const created = await request('', { method: 'POST', body: { title: 'Keep' } });
  for (const body of [{}, { title: null }, { isCompleted: 1 }, { createdAt: 'overwrite' }]) {
    assert.equal((await request(`/${created.body.id}`, { method: 'PATCH', body })).status, 400);
  }
  assert.deepEqual((await request(`/${created.body.id}`)).body, created.body);
});

test('POST rejects unknown __proto__ key with 400 without creating a task', async (t) => {
  const { request } = await fixture(t);
  const response = await request('', { method: 'POST', raw: '{"title":"Proto key","__proto__":{}}' });
  assert.equal(response.status, 400);
  assert.equal(Object.hasOwn(response.body.error.fields, '__proto__'), true);
  assert.equal(response.body.error.fields.__proto__, 'Unknown field.');
  assert.deepEqual((await request()).body, []);
});

test('PATCH rejects unknown-only __proto__ key with 400 without mutating the task', async (t) => {
  const { request } = await fixture(t);
  const created = await request('', { method: 'POST', body: { title: 'Keep', description: 'Original' } });
  const path = `/${created.body.id}`;
  const response = await request(path, { method: 'PATCH', raw: '{"__proto__":{}}' });
  assert.equal(response.status, 400);
  assert.equal(Object.hasOwn(response.body.error.fields, '__proto__'), true);
  assert.equal(response.body.error.fields.__proto__, 'Unknown field.');
  assert.deepEqual((await request(path)).body, created.body);
  assert.deepEqual((await request()).body, [created.body]);
});

test('production SPA fallback preserves JSON unknown API response', async (t) => {
  const directory = mkdtempSync(join(tmpdir(), 'todolist-web-'));
  writeFileSync(join(directory, 'index.html'), '<html>TodoList test</html>');
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  const { url } = await fixture(t, { serveWeb: true, webPath: directory });
  assert.match(await (await fetch(`${url}/tasks/example`)).text(), /TodoList test/);
  const response = await fetch(`${url}/api/unknown`);
  assert.equal(response.status, 404);
  assert.deepEqual(await response.json(), { error: { message: 'API route not found.' } });
});
