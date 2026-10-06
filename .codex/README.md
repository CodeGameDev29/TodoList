# Codex harness

`.codex/config.toml` uses Codex 0.160.1's project configuration shape: `gpt-6-astra` at high for orchestration and `gpt-6.1-sol` for generated roles. `.codex/agents/` is generated from the canonical Claude role frontmatter; do not edit it directly.

Run `python scripts/harness/sync_agent_harness.py --check` and `python scripts/harness/validate_harness.py`. Validation performs a strict semantic Codex load in a temporary `CODEX_HOME`, so runtime databases and helper files do not enter this repository. The only MCP service is pinned Playwright `@playwright/mcp@0.0.83`.
