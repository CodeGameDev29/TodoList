# TodoList agent contract

The user approved a JavaScript React SPA in `apps/web`, a Node.js/Express REST API in `apps/api`, and SQLite persistence with migrations in `database`. The interview scope is 4–6 hours: task creation, listing, details, editing, completion/reopening, deletion, validation, persistence, tests, and documentation. Acceptance criteria are in `qa/acceptance.md`. Do not add authentication, filtering/sorting controls, Docker, deployment, or other product scope without approval. `packages/contracts` is reserved for shared code only when needed.

Canonical harness sources are this file, `.claude/agents/`, `.claude/skills/`, `.claude/project/GOLDEN-RULES.md`, and `.claude/hooks/`. Generated mirrors are `AGENTS.md`, `.agents/skills/`, and `.codex/agents/`; never hand-edit them. Run `python scripts/harness/sync_agent_harness.py --check`.

Claude uses `claude-fable-5-1` high for orchestration and `claude-opus-5-5` for roles. Codex uses `gpt-6-astra` high for orchestration and `gpt-6.1-sol` for roles. The orchestrator scopes and decides; workers produce evidence; authors never judge their own work.

QA assets are under `qa/`; run artifacts go to ignored `.qa-artifacts/` or `TODOLIST_QA_ARTIFACTS`. Headed Playwright MCP journeys preserve title, wall-clock time, screenshots, trace, console, and network evidence. Run `python qa/harness.py status`, `python scripts/harness/validate_harness.py`, and `python -m unittest discover -s tests` before handoff. Keep secrets out of repository, prompts, logs, fixtures, and screenshots.
