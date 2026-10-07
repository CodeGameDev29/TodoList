import { DatabaseSync } from 'node:sqlite';
import { readFileSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';

const migrations = [{
  version: 1,
  up: readFileSync(new URL('../../../database/migrations/001_create_todos.sql', import.meta.url), 'utf8'),
  down: readFileSync(new URL('../../../database/migrations/001_create_todos.down.sql', import.meta.url), 'utf8'),
}];

const listFilters = {
  all: '', incomplete: 'WHERE is_completed = 0', completed: 'WHERE is_completed = 1',
  overdue: 'WHERE is_completed = 0 AND due_date < ?',
};
const listSorts = { createdAt: 'created_at', dueDate: 'due_date', title: 'title COLLATE NOCASE' };
const listOrders = { asc: 'ASC', desc: 'DESC' };

export const defaultDatabasePath = fileURLToPath(new URL('../../../database/data/todos.sqlite', import.meta.url));

export function migrate(db, targetVersion = migrations.length) {
  if (!Number.isInteger(targetVersion) || targetVersion < 0 || targetVersion > migrations.length) {
    throw new Error('Unsupported migration version');
  }
  db.exec('CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)');
  let version = db.prepare('SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations').get().version;
  if (version > migrations.length) throw new Error('Database version is newer than this application');
  db.exec('BEGIN');
  try {
    while (version < targetVersion) {
      const migration = migrations[version];
      db.exec(migration.up);
      db.prepare('INSERT INTO schema_migrations (version) VALUES (?)').run(migration.version);
      version = migration.version;
    }
    while (version > targetVersion) {
      db.exec(migrations[version - 1].down);
      db.prepare('DELETE FROM schema_migrations WHERE version = ?').run(version);
      version--;
    }
    db.exec('COMMIT');
  } catch (error) {
    db.exec('ROLLBACK');
    throw error;
  }
}

function serialize(row) {
  if (!row) return null;
  return {
    id: row.id, title: row.title, description: row.description, dueDate: row.due_date,
    isCompleted: Boolean(row.is_completed), createdAt: row.created_at,
  };
}

export function createRepository(databasePath = defaultDatabasePath) {
  if (databasePath !== ':memory:') mkdirSync(dirname(databasePath), { recursive: true });
  const db = new DatabaseSync(databasePath);
  try { migrate(db); } catch (error) { db.close(); throw error; }
  const get = (id) => serialize(db.prepare('SELECT * FROM todos WHERE id = ?').get(id));
  return {
    list({ status = 'all', sortBy = 'createdAt', order = 'desc', today = new Date().toISOString().slice(0, 10) } = {}) {
      if (!Object.hasOwn(listFilters, status) || !Object.hasOwn(listSorts, sortBy) || !Object.hasOwn(listOrders, order)) {
        throw new Error('Unsupported list options');
      }
      // Only fixed whitelist expressions enter SQL; the date remains a bound value.
      const nullsLast = sortBy === 'dueDate' ? 'due_date IS NULL ASC, ' : '';
      const statement = db.prepare(`SELECT * FROM todos ${listFilters[status]} ORDER BY ${nullsLast}${listSorts[sortBy]} ${listOrders[order]}, id ASC`);
      return (status === 'overdue' ? statement.all(today) : statement.all()).map(serialize);
    },
    get,
    create(input) {
      const id = randomUUID();
      db.prepare('INSERT INTO todos (id, title, description, due_date, created_at) VALUES (?, ?, ?, ?, ?)')
        .run(id, input.title, input.description ?? null, input.dueDate ?? null, new Date().toISOString());
      return get(id);
    },
    update(id, input) {
      const current = get(id);
      if (!current) return null;
      const task = { ...current, ...input };
      db.prepare('UPDATE todos SET title = ?, description = ?, due_date = ?, is_completed = ? WHERE id = ?')
        .run(task.title, task.description, task.dueDate, Number(task.isCompleted), id);
      return get(id);
    },
    delete: (id) => db.prepare('DELETE FROM todos WHERE id = ?').run(id).changes > 0,
    close: () => db.close(),
  };
}
