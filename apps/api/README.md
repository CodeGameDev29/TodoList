# TodoList REST API

JavaScript ESM, Express 5, and Node's built-in SQLite. Run root `npm run dev` for both apps, or `npm run dev --workspace @todolist/api` for the API. Tests: `npm test --workspace @todolist/api`.

`src/app.js` builds the HTTP application without opening storage or listening, so tests inject isolated storage. `src/server.js` opens storage and binds `127.0.0.1:3001`. Set `PORT`, `HOST`, or `DATABASE_PATH` when needed. `npm start` serves the built SPA from `apps/web/dist` on the same origin; `NODE_ENV=production` also enables this mode.

Routes under `/api/todos`: GET list, POST create, GET `/:id` details, PATCH `/:id` partial update, DELETE `/:id`. Errors use `{ "error": { "message": "...", "fields": {} } }`, with fields only for validation. See `qa/acceptance.md` for the contract and `database/README.md` for migrations.
