# Golden rules

1. Orchestrate with Claude `claude-fable-5-1` at high (xhigh only when explicitly raised) or Codex `gpt-6-astra` at high. Delegate execution to Claude `claude-opus-5-5` or Codex `gpt-6.1-sol`: executor and qa-runner medium; executor-hard, verifier, qa-judge, and security-reviewer high. At most four concurrent agents and depth two.
2. The orchestrator decides scope and final response. Workers change or inspect only their assigned surface and report actual evidence.
3. Write acceptance rows before implementation. An author never judges their own output. QA judgment is PASS or FAIL; missing or blocked evidence is FAIL.
4. Browser QA is headed Playwright MCP and records title, wall-clock duration, screenshots, trace, console, and network evidence.
5. Database work uses an isolated test database, forward migration, preservation checks, and rollback when supported. Never use production data.
6. Secrets never enter repository files, prompts, logs, screenshots, or fixtures.
7. Every finding has a bug class: acceptance first, RED evidence, independent judgment/classification, fix, GREEN rerun, then verifier review. No notes-only limbo.
8. At 30% context hand off and do not begin long work; at 60% hand off immediately. Do not leave agents hanging.
9. Current scope forbids TodoList features, stack selection, app dependencies, and product source until requested.
