# SQLite persistence

The API opens `database/data/todos.sqlite` by default; `DATABASE_PATH` overrides it. Tests exclusively use temporary files or in-memory databases. Node 24.15+ in the 24.x line provides `node:sqlite`, a release-candidate API. This avoids a native dependency or separate server for the interview scope.

Initialization applies `migrations/001_create_todos.sql` transactionally and records version 1 in `schema_migrations`. Repeated initialization preserves rows. Future migrations should be appended to the ordered list in `apps/api/src/repository.js` with preservation tests. An unexpected newer schema fails startup.

`migrate(db, 0)` applies `001_create_todos.down.sql`. **This drops the todos table and permanently deletes its tasks.** There is deliberately no application rollback command. Rollback is tested only against an isolated in-memory database; do not run it against a real database. Before operational rollback, create and verify a backup or implement a data-preserving migration.
