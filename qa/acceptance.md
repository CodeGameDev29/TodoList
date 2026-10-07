# Approved TodoList acceptance

Scope approved by the user: JavaScript React SPA, Node.js/Express REST API, SQLite persistence, selectable filtering/sorting and Docker containerization. Optional-enhancement contracts and acceptance rows are in [optional-enhancements.md](optional-enhancements.md). Authentication, multi-user behavior and external hosting deployment are excluded.

| ID | Acceptance | Required evidence |
| --- | --- | --- |
| A1 | Empty list is usable; title is required; a new task has an ID, optional description/date, false completion, and server creation timestamp. | Browser creation and API tests |
| A2 | List shows titles, due dates and completion; selecting a task loads its full details by ID. | Browser list/detail and API tests |
| A3 | Editing preserves omitted fields; description/date can be cleared explicitly. | Browser edit/clear and API tests |
| A4 | Complete and reopen persist; repeating the same state succeeds. | Browser toggle and API tests |
| A5 | Delete requires UI confirmation and removes the task; cancelled deletion preserves it. | Browser delete/cancel and API tests |
| A6 | Invalid types, blank titles, impossible dates and malformed bodies produce consistent 400 errors; unknown IDs produce 404. | API tests; browser invalid form |
| A7 | Database reopen preserves tasks; initialization is repeatable and preserves existing rows; versioned forward migration and explicit rollback behavior are documented and tested on isolated databases. | Storage migration tests |
| A8 | Loading, empty, saving and error states are visible; failures retain form input and permit retry; labels, keyboard access and narrow layout work. | Frontend tests and headed browser evidence |
| A9 | A clean install can run, test and build using README commands; no secrets or runtime database committed. | Command logs and independent review |
| A10 | All rows have independent judgment and exact implementation receives verifier review. | Judge and verifier reports |

## API contract

Base URL `/api`. Routes: POST /todos (201 and Location), GET /todos (200 array), GET /todos/:id (200), PATCH /todos/:id (200), DELETE /todos/:id (204). Missing IDs return 404. Errors use `{ "error": { "message": "...", "fields": { "title": "..." } } }` with fields optional. JSON task: `{ id, title, description, dueDate, isCompleted, createdAt }`. ID is a UUID string; optional fields serialize as null. Dates are strict real YYYY-MM-DD dates, years 0001–9999; timestamps are UTC ISO strings. Title is trimmed, 1–200 characters; description max 5000 characters. Duplicate titles and past dates are allowed. Create accepts only title, description, dueDate; status defaults false. PATCH accepts these fields plus boolean isCompleted; omitted fields unchanged and null clears optional fields. Unknown fields and empty PATCH rejected. List newest first, ID as deterministic tie-breaker. Single local user, no login.

## Boundaries

Frontend: `apps/web`; API: `apps/api`; SQL migration: `database`. Node 24.15+ within the 24.x line; built-in node:sqlite (release candidate in this runtime; document stability tradeoff). Vite development proxy sends /api to localhost:3001. Production Express serves the built SPA and /api on one origin. API binds loopback by default. Database defaults to `database/data/todos.sqlite`; DATABASE_PATH overrides it for isolated testing. Test data must never use a user's database.
