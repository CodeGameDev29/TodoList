# QA harness

This stdlib-only harness records the contract around a future application without claiming current runs. Acceptance definitions live in `acceptance/`; journey definitions in `journeys/`; only schemas, class registry, and ledger are committed. Actual screenshots, traces, console, network, titles, and timing go to `.qa-artifacts/` (or `TODOLIST_QA_ARTIFACTS`) and are never committed.

Use `python qa/harness.py preflight` to validate all recursive acceptance and journey definitions, then `new-report <id>` to create an unjudged report skeleton. `validate` checks reports and journeys; `judge-pack <id>` freezes only a complete, independently judgeable report; `add-class <json>` or `intake <id>` registers a valid proposed class; `record <id>` updates the per-class ledger; and `status` prints it.

Every runtime report records a foreground headed browser title and wall clock, exact step evidence, runner and different judge identities, PASS/FAIL rows, and a change ID. Evidence paths must exist inside the configured artifact root; trace, console, and network capture may explicitly be `captured-empty`. Invalid, incomplete, unjudged, or instrument-error runs are never recorded. A class closes only after all regression rows are green and two clean judged rounds; a later hit reopens it. Two consecutive hits on the same shipped change mark that class as a process failure.
