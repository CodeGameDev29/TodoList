# TodoList

A React single-page application with an Express REST API and SQLite persistence. Create, view, edit, complete/reopen, and delete tasks. The UI includes selectable filters and sorting, validation, loading and saving feedback, empty states, and retryable errors. Docker runs the production SPA and API together with persistent storage.

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

After building, `npm start` serves the API and built SPA together at `http://127.0.0.1:3001`. Development and production use the same persistent database by default.

The API accepts environment variables `DATABASE_PATH`, `PORT`, and `HOST`. The default database is `database/data/todos.sqlite`, created automatically; the default host is loopback. For an isolated database, set `DATABASE_PATH` before starting, for example in PowerShell:

```powershell
$env:DATABASE_PATH = 'C:\temp\todolist-demo.sqlite'
npm start
```

Remove that environment override with `Remove-Item Env:DATABASE_PATH` when done. Tests create isolated databases and never use the default application database.

## Filter and sort tasks

Use **Filter** to select All tasks, Incomplete, Completed, or Overdue. Overdue means an incomplete task with a due date strictly before today's **UTC** calendar date, as evaluated by the server. Tasks due today, completed tasks, and tasks without a due date are excluded from Overdue.

Use **Sort by** to select Created date, Due date, or Title, and **Order** to select Ascending or Descending. The default is All tasks, Created date, Descending. Tasks without due dates appear last in both directions. Title ordering uses SQLite `NOCASE`, which is case-insensitive for ASCII letters. Equal sort values use ID ascending as a stable tie-breaker.

Filters and sorting combine and remain selected during task changes in the current session. The interface distinguishes no matching tasks from an empty task collection. List refresh failures are retryable; successful saves are kept even if the following refresh fails.

## Docker

Install Docker with Compose and start the Docker engine. From the repository root:

```sh
docker compose up --build -d
```

Open `http://localhost:8080`. Compose binds the host port to loopback. The image builds the React production bundle and serves it alongside `/api` from one Node process. Its runtime includes production dependencies, runs as the non-root `node` user, and checks API health. It listens internally on `0.0.0.0:3001` and stores SQLite at `/data/todos.sqlite`.

The `todo-data` named volume persists across container replacement and `docker compose down`. Restart with `docker compose up -d`. **`docker compose down -v` deletes the volume and its tasks.** Container storage is separate from the local development database. The build context allows only required manifests, source files, and migrations; local databases, secrets, dependencies, and QA captures are excluded.

To build and run without Compose:

```sh
docker build -t todolist:local .
docker volume create todolist-data
docker run -d --name todolist-local -p 127.0.0.1:8080:3001 --mount type=volume,source=todolist-data,target=/data todolist:local
docker inspect --format '{{.State.Health.Status}}' todolist-local
docker logs todolist-local
```

Use `docker stop todolist-local` and `docker rm todolist-local` to remove the container; the named volume remains. Stop Compose first if it is already using port 8080.

Container verification uses an isolated temporary container and volume, checks the production SPA and API health, verifies the runtime user and dependency pruning, then replaces the container and checks that its task survives:

```sh
docker build -t todolist:smoke .
node scripts/docker/smoke.mjs todolist:smoke
```

The smoke script cleans up only resources unique to that invocation. GitHub Actions runs this check alongside application tests and builds.

## Architecture and tradeoffs

- `apps/web`: React components, local state, a small API client, Vite, and Vitest component tests. Form values remain available after failed saves; server-confirmed responses update the list.
- `apps/api`: Express routes, task validation/service logic, and a SQLite repository; API and storage tests use Node's test runner.
- `database/migrations`: versioned SQL schema changes. Initialization preserves existing data and is repeatable. Migrations run in a transaction; failures roll back. The initial down migration is destructive and intended only for isolated tests. There is no application rollback command; restore a backup for real data.
- `qa`: acceptance criteria, browser journeys, and the independent review harness. `.qa-artifacts` contains ignored execution evidence.

Node's built-in `node:sqlite` avoids an ORM, database server, or native package build. It has [release candidate stability in Node 24.15](https://nodejs.org/download/release/v24.15.0/docs/api/sqlite.html); that tradeoff is deliberate for this small local exercise. Synchronous database access keeps the repository simple but is not intended for large concurrent workloads.

The app assumes one local user with no login. Duplicate titles and past due dates are allowed. Titles are trimmed and limited to 200 characters; descriptions to 5,000. Due dates are calendar dates (`YYYY-MM-DD`, years 0001–9999), and creation timestamps are server-generated UTC values. Optional fields serialize as `null`. Filtering and sorting are performed by the API with bound filter values and whitelisted ordering expressions.

Authentication and multi-user behavior are outside the application scope. External hosting is not configured. A larger production service would require a fresh review of authorization, concurrency, and database requirements.

## REST API

Base path: `/api`. Requests use `Content-Type: application/json`.

| Method and path     | Result                                     |
| ------------------- | ------------------------------------------ |
| `POST /todos`       | `201`, created task, and `Location` header |
| `GET /todos`        | `200`, filtered and sorted task array      |
| `GET /todos/:id`    | `200`, task                                |
| `PATCH /todos/:id`  | `200`, updated task                        |
| `DELETE /todos/:id` | `204`, no body                             |

Examples using curl in a POSIX shell:

```sh
curl -X POST http://127.0.0.1:3001/api/todos -H 'Content-Type: application/json' -d '{"title":"Prepare interview","description":"Review architecture","dueDate":"2026-10-10"}'
curl http://127.0.0.1:3001/api/todos
curl 'http://127.0.0.1:3001/api/todos?status=overdue&sortBy=dueDate&order=asc'
curl 'http://127.0.0.1:3001/api/todos?status=incomplete&sortBy=title&order=asc'
curl -X PATCH http://127.0.0.1:3001/api/todos/REPLACE_WITH_ID -H 'Content-Type: application/json' -d '{"isCompleted":true,"dueDate":null}'
curl -X DELETE http://127.0.0.1:3001/api/todos/REPLACE_WITH_ID
```

In Windows PowerShell, create a task using a serialized request body:

```powershell
$taskBody = @{ title = 'Prepare interview'; description = 'Review architecture'; dueDate = '2026-10-10' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:3001/api/todos' -ContentType 'application/json' -Body $taskBody
Invoke-RestMethod -Uri 'http://127.0.0.1:3001/api/todos?status=completed&sortBy=createdAt&order=desc'
```

Tasks contain `id` (UUID), `title`, `description`, `dueDate`, `isCompleted`, and `createdAt`. POST accepts title, description, and due date; completion starts false. PATCH also accepts `isCompleted`; omitted fields remain unchanged and `null` clears optional fields. Repeating a completion state succeeds. Empty PATCH requests, unknown fields, invalid types, blank titles, impossible dates, and malformed JSON return `400`; missing tasks return `404`.

Errors have the shape `{"error":{"message":"...","fields":{"title":"..."}}}`; field details are optional. The UI asks for confirmation before deletion.

List parameters are optional and accept the following values:

| Parameter | Values                                      | Default     |
| --------- | ------------------------------------------- | ----------- |
| `status`  | `all`, `incomplete`, `completed`, `overdue` | `all`       |
| `sortBy`  | `createdAt`, `dueDate`, `title`             | `createdAt` |
| `order`   | `asc`, `desc`                               | `desc`      |

Unknown, repeated, or invalid query parameters return `400` using the same error shape. Listing continues to return a JSON task array.

## Verification

`npm test` runs API/storage integration tests and React/API-client tests. Coverage includes task lifecycle, write and query validation, overdue boundaries, combined filtering and sorting, undated tasks last in both directions, stable ties, persistence, active-view refreshes, and failed request recovery. `npm run build` verifies the production frontend bundle. Browser acceptance and independent review follow [qa/acceptance.md](qa/acceptance.md) and [qa/optional-enhancements.md](qa/optional-enhancements.md).

## Formatting and code review

The repository is formatted for human review with pinned Prettier and Ruff versions. Prettier covers JavaScript/JSX, CSS, HTML, JSON, YAML, and Markdown; Ruff formats Python and sorts its imports. Install the development tools with Node.js and Python 3.11 or newer:

```sh
npm ci
python -m pip install -r requirements-dev.txt
npm run format:check
```

Use `npm run format` to apply formatting and regenerate harness mirrors. JavaScript uses two-space indentation and a 100-column wrapping target; Python uses four spaces and an 88-column target. Formatter checks also run in CI. Generated mirrors are excluded from direct formatting and checked against their canonical sources; lockfiles, dependencies, build output, user files, and execution artifacts are excluded. SQL, TOML, Dockerfile, and command wrappers receive manual layout review.

The harness requires an independent, read-only `code-reviewer` before handoff. Reviewers apply [the researched code-review rubric](.claude/project/CODE-REVIEW-RUBRIC.md), prioritizing indentation and readability, then correctness, robustness, and maintainability. Every applicable rule receives a verdict with evidence, and findings identify their rule IDs and severity. Formatting checks complement code review and tests; they do not establish correctness on their own.

## Harness checks

The agent harness remains part of this repository. Its CLI pins are separate from application dependencies; see [CLAUDE.md](CLAUDE.md) and [qa/README.md](qa/README.md). To configure the harness, run `python scripts/harness/setup.py` and follow its printed trust/login instructions.

```sh
python scripts/harness/sync_agent_harness.py --check
python qa/harness.py status
python scripts/harness/validate_harness.py
python -m unittest discover -s tests
```

Full harness validation requires the pinned Codex CLI `0.160.1`. Browser acceptance uses headed Playwright MCP evidence and independent judgment. User-owned `.idea` files, secrets, dependencies, build outputs, databases, and run artifacts are ignored.

Semantic CLI checks use a disposable, credential-free home under `.qa-artifacts/harness-validation`, leaving your normal CLI configuration untouched. Cleanup retries brief file locks and fails with the fixture path if it cannot finish. CI limits harness/application jobs to 10 minutes and container verification to 20 minutes; a timeout does not count as a passing check.
