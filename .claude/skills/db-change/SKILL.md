---
name: db-change
description: 'Plan and validate database changes without touching production data.'
---

# Database change

Precondition: selected database technology and explicit change request. Use only an isolated test database. Define forward migration, preservation checks, rollback when supported, and acceptance rows before edits. Never use production data or credentials. Done means independently verified migration evidence.
