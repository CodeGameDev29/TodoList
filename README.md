# TodoList

An intentionally empty future full-stack web application. The agent harness is ready; application, backend, database, and dependency choices are deliberately unmade.

## Setup and checks

`python scripts/harness/setup.py` configures this clone's hooks and synchronizes generated harness files. Then complete the printed Codex `/hooks` trust and login steps manually.

`python scripts/harness/sync_agent_harness.py --check`
`python scripts/harness/validate_harness.py`
`python scripts/harness/quick_validate.py`
`python -m unittest discover -s tests`

See [CLAUDE.md](CLAUDE.md) for the working contract and [qa/README.md](qa/README.md) for QA evidence.
