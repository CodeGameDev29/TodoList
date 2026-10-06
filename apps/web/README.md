# TodoList frontend

JavaScript React SPA built with Vite. See the [root README](../../README.md) for installation, Node requirements, application startup, architecture, and tradeoffs.

From the repository root, after `npm ci`:

```sh
npm run dev --workspace @todolist/web
npm run test --workspace @todolist/web
npm run build --workspace @todolist/web
```

The development server uses `http://127.0.0.1:5173` and proxies `/api` to the API at `http://127.0.0.1:3001`. Run the API alongside it. Production builds go to `apps/web/dist` and are served by Express.

Frontend tests cover task interactions, validation, retry and retained drafts, saving state, and API error feedback.
