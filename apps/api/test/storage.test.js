import test from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createRepository, migrate } from '../src/repository.js';

test('reopen and repeatable forward migration preserve rows', (t) => {
  const directory = mkdtempSync(join(tmpdir(), 'todolist-storage-'));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  const path = join(directory, 'test.sqlite');
  let repository = createRepository(path);
  const created = repository.create({ title: 'Persist', description: 'Saved', dueDate: '9999-12-31' });
  const completed = repository.update(created.id, { isCompleted: true });
  repository.close();
  const db = new DatabaseSync(path);
  migrate(db);
  migrate(db);
  assert.deepEqual(db.prepare('SELECT version FROM schema_migrations').all().map((row) => row.version), [1]);
  assert.equal(db.prepare('SELECT COUNT(*) AS count FROM todos').get().count, 1);
  db.close();
  repository = createRepository(path);
  assert.deepEqual(repository.get(created.id), completed);
  repository.close();
});

test('initial rollback deletes tasks; forward migration works again on isolated DB', () => {
  const db = new DatabaseSync(':memory:');
  try {
    migrate(db);
    db.prepare('INSERT INTO todos (id, title, created_at) VALUES (?, ?, ?)').run('test', 'Isolated data', new Date().toISOString());
    migrate(db, 0);
    assert.equal(db.prepare("SELECT COUNT(*) AS count FROM sqlite_master WHERE type = 'table' AND name = 'todos'").get().count, 0);
    assert.equal(db.prepare('SELECT COUNT(*) AS count FROM schema_migrations').get().count, 0);
    migrate(db);
    assert.equal(db.prepare('SELECT COUNT(*) AS count FROM todos').get().count, 0);
  } finally { db.close(); }
});

test('failed migration rolls back version tracking and preserves existing table', () => {
  const db = new DatabaseSync(':memory:');
  try {
    db.exec('CREATE TABLE todos (note TEXT)');
    db.prepare('INSERT INTO todos VALUES (?)').run('preserve');
    assert.throws(() => migrate(db), /already exists/);
    assert.equal(db.prepare('SELECT COUNT(*) AS count FROM schema_migrations').get().count, 0);
    assert.equal(db.prepare('SELECT note FROM todos').get().note, 'preserve');
  } finally { db.close(); }
});

test('list order is newest first with deterministic ID tie breaker', () => {
  const repository = createRepository(':memory:');
  try {
    const older = repository.create({ title: 'Older' });
    const newer = repository.create({ title: 'Newer' });
    const expected = [older, newer].sort((a, b) => b.createdAt.localeCompare(a.createdAt) || a.id.localeCompare(b.id));
    assert.deepEqual(repository.list(), expected);
  } finally { repository.close(); }
});

test('all sort directions preserve stable ties and keep undated tasks last', (t) => {
  const directory = mkdtempSync(join(tmpdir(), 'todolist-order-'));
  const path = join(directory, 'test.sqlite');
  const repository = createRepository(path);
  t.after(() => {
    repository.close();
    rmSync(directory, { recursive: true, force: true });
  });
  const db = new DatabaseSync(path);
  try {
    const insert = db.prepare('INSERT INTO todos (id, title, due_date, created_at) VALUES (?, ?, ?, ?)');
    insert.run('b', 'alpha', '2026-10-05', '2026-10-01T00:00:00.000Z');
    insert.run('a', 'ALPHA', '2026-10-05', '2026-10-01T00:00:00.000Z');
    insert.run('c', 'Beta', '2026-10-06', '2026-10-02T00:00:00.000Z');
    insert.run('d', 'zebra', null, '2026-10-03T00:00:00.000Z');
    insert.run('e', 'ZEBRA', null, '2026-10-03T00:00:00.000Z');
  } finally { db.close(); }
  const ids = (options) => repository.list(options).map((task) => task.id);
  for (const sortBy of ['createdAt', 'dueDate', 'title']) {
    assert.deepEqual(ids({ sortBy, order: 'asc' }), ['a', 'b', 'c', 'd', 'e'], sortBy);
    const descending = sortBy === 'dueDate' ? ['c', 'a', 'b', 'd', 'e'] : ['d', 'e', 'c', 'a', 'b'];
    assert.deepEqual(ids({ sortBy, order: 'desc' }), descending, sortBy);
  }
  assert.deepEqual(ids(), ['d', 'e', 'c', 'a', 'b']);
  repository.update('b', { isCompleted: true });
  assert.deepEqual(ids({ status: 'overdue', today: '2026-10-06', sortBy: 'dueDate', order: 'desc' }), ['a']);
  assert.deepEqual(ids({ status: 'completed' }), ['b']);
  assert.deepEqual(ids({ status: 'incomplete' }), ['d', 'e', 'c', 'a']);
  assert.deepEqual(ids({ status: 'overdue', today: '0001-01-01' }), []);
  assert.throws(() => repository.list({ sortBy: 'title; DROP TABLE todos' }), /Unsupported list options/);
  assert.throws(() => repository.list({ status: '__proto__' }), /Unsupported list options/);
  assert.deepEqual(ids(), ['d', 'e', 'c', 'a', 'b']);
});
