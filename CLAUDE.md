# TodoList agent contract

This is an intentionally empty future full-stack repository. Future boundaries are `apps/web` (React), `apps/api`, `database`, and `packages/contracts`; the latter technologies are undecided. Do not implement an app, select a stack, add dependencies, or create product behavior unless requested.

Canonical harness sources are this file, `.claude/agents/`, `.claude/skills/`, `.claude/project/GOLDEN-RULES.md`, and `.claude/hooks/`. Generated mirrors are `AGENTS.md`, `.agents/skills/`, and `.codex/agents/`; never hand-edit them. Run `python scripts/harness/sync_agent_harness.py --check`.

Claude uses `claude-fable-5-1` high for orchestration and `claude-opus-5-5` for roles. Codex uses `gpt-6-astra` high for orchestration and `gpt-6.1-sol` for roles. The orchestrator scopes and decides; workers produce evidence; authors never judge their own work.

QA assets are under `qa/`; run artifacts go to ignored `.qa-artifacts/` or `TODOLIST_QA_ARTIFACTS`. Headed Playwright MCP journeys preserve title, wall-clock time, screenshots, trace, console, and network evidence. Run `python qa/harness.py status`, `python scripts/harness/validate_harness.py`, and `python -m unittest discover -s tests` before handoff. Keep secrets out of repository, prompts, logs, fixtures, and screenshots.
