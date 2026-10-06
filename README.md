# TodoList

A React single-page application with an Express REST API and SQLite persistence, scoped to a 4–6 hour interview exercise. Create, view, edit, complete/reopen, and delete tasks. The UI includes validation, loading and saving feedback, empty states, and retryable errors.

## Run

Install **Node.js 24.15 or newer within the 24.x line**, with npm. From the repository root:

```sh
npm ci
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to the API at `http://127.0.0.1:3001`. Both processes stop with Ctrl+C. Port 3001 must be available for the default proxy configuration.

```sh
npm test
npm run build
npm start
```

After building, `npm start` serves the API and built SPA together at `http://127.0.0.1:3001`. Development and production use the same persistent database by default. The application does not include deployment configuration.

The API accepts environment variables `DATABASE_PATH`, `PORT`, and `HOST`. The default database is `database/data/todos.sqlite`, created automatically; the default host is loopback. For an isolated database, set `DATABASE_PATH` before starting, for example in PowerShell:

```powershell
$env:DATABASE_PATH = 'C:\temp\todolist-demo.sqlite'
npm start
```

Remove that environment override with `Remove-Item Env:DATABASE_PATH` when done. Tests create isolated databases and never use the default application database.

## Architecture and tradeoffs

- `apps/web`: React components, local state, a small API client, Vite, and Vitest component tests. Form values remain available after failed saves; server-confirmed responses update the list.
- `apps/api`: Express routes, task validation/service logic, and a SQLite repository; API and storage tests use Node's test runner.
- `database/migrations`: versioned SQL schema changes. Initialization preserves existing data and is repeatable. Migrations run in a transaction; failures roll back. The initial down migration is destructive and intended only for isolated tests. There is no application rollback command; restore a backup for real data.
- `qa`: acceptance criteria, browser journeys, and the independent review harness. `.qa-artifacts` contains ignored execution evidence.

Node's built-in `node:sqlite` avoids an ORM, database server, or native package build. It has [release candidate stability in Node 24.15](https://nodejs.org/download/release/v24.15.0/docs/api/sqlite.html); that tradeoff is deliberate for this small local exercise. Synchronous database access keeps the repository simple but is not intended for large concurrent workloads.

The app assumes one local user with no login. Duplicate titles and past due dates are allowed. Titles are trimmed and limited to 200 characters; descriptions to 5,000. Due dates are calendar dates (`YYYY-MM-DD`, years 0001–9999), and creation timestamps are server-generated UTC values. Optional fields serialize as `null`. There are no filtering/sorting controls; the API returns newest tasks first with an ID tie-breaker.

Authentication, multi-user authorization, deployment, Docker, and richer querying are outside the approved interview scope. A production extension would require those decisions and a fresh review of concurrency and database requirements.

## REST API

Base path: `/api`. Requests use `Content-Type: application/json`.

| Method and path | Result |
| --- | --- |
| `POST /todos` | `201`, created task, and `Location` header |
| `GET /todos` | `200`, task array |
| `GET /todos/:id` | `200`, task |
| `PATCH /todos/:id` | `200`, updated task |
| `DELETE /todos/:id` | `204`, no body |

Examples using curl in a POSIX shell:

```sh
curl -X POST http://127.0.0.1:3001/api/todos -H 'Content-Type: application/json' -d '{"title":"Prepare interview","description":"Review architecture","dueDate":"2026-10-10"}'
curl http://127.0.0.1:3001/api/todos
curl -X PATCH http://127.0.0.1:3001/api/todos/REPLACE_WITH_ID -H 'Content-Type: application/json' -d '{"isCompleted":true,"dueDate":null}'
curl -X DELETE http://127.0.0.1:3001/api/todos/REPLACE_WITH_ID
```

In Windows PowerShell, create a task using a serialized request body:

```powershell
$taskBody = @{ title = 'Prepare interview'; description = 'Review architecture'; dueDate = '2026-10-10' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:3001/api/todos' -ContentType 'application/json' -Body $taskBody
```

Tasks contain `id` (UUID), `title`, `description`, `dueDate`, `isCompleted`, and `createdAt`. POST accepts title, description, and due date; completion starts false. PATCH also accepts `isCompleted`; omitted fields remain unchanged and `null` clears optional fields. Repeating a completion state succeeds. Empty PATCH requests, unknown fields, invalid types, blank titles, impossible dates, and malformed JSON return `400`; missing tasks return `404`.

Errors have the shape `{"error":{"message":"...","fields":{"title":"..."}}}`; field details are optional. The UI asks for confirmation before deletion.

## Harness checks

The agent harness remains part of this repository. Its CLI pins are separate from application dependencies; see [CLAUDE.md](CLAUDE.md) and [qa/README.md](qa/README.md). To configure the harness, run `python scripts/harness/setup.py` and follow its printed trust/login instructions.

```sh
python scripts/harness/sync_agent_harness.py --check
python qa/harness.py status
python scripts/harness/validate_harness.py
python -m unittest discover -s tests
```

Full harness validation requires the pinned Codex CLI `0.160.1`. Browser acceptance uses headed Playwright MCP evidence and independent judgment. User-owned `.idea` files, secrets, dependencies, build outputs, databases, and run artifacts are ignored.
