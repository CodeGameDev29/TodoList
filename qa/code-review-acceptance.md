# Repository code review acceptance

The user requested a dedicated code-review harness agent and a full repository review, prioritizing formatting, followed by readability, correctness, quality, and robustness.

- R1: Add a read-only `code-reviewer` role to the canonical harness and generated Codex configuration, with independent review responsibilities and concrete, prioritized findings. Validate role registration, synchronization, and read-only enforcement.
- R2: Establish reproducible formatting for maintained JavaScript/JSX, CSS, HTML, JSON, YAML, Markdown, and Python. Format canonical sources and regenerate mirrors; never hand-edit generated files. Exclude dependencies, build outputs, user IDE files, databases, secrets, and execution artifacts. Document commands and enforce formatting in CI.
- R3: Review every tracked first-party application, database, test, harness, configuration, and documentation surface. Record review coverage and actionable findings with severity, source evidence, a bug class, and independent classification before behavioral fixes. Dependency lockfiles and generated mirrors receive integrity checks rather than manual code review.
- R4: Correct confirmed issues and unclear or stale documentation. Keep formatting changes behavior-preserving; scope behavioral changes to reproduced review findings, with focused regression checks. Preserve user data and the approved application requirements.
- R5: Run application tests, production build, formatting checks, harness synchronization/validation/tests, and Docker verification appropriate to changed files. Independently review the final diff and evidence. Use isolated data for regressions and headed browser evidence for changed UI behavior.
- R6: Deliver a review summary describing coverage, resolved findings, verification, and remaining limitations. Preserve a clean commit history and publish verified changes to the existing repository.
- R7: Give every CI verification job an explicit time limit so a stalled tool cannot occupy a runner indefinitely. A timeout must fail the job; do not skip or soften checks to obtain a passing result.

## Confirmed harness regressions from independent review

- H1: Recording the same report ID again must not alter the registry or ledger, add another clean round, or invent a repeated failure. Reject duplicate recording with a clear diagnostic. Distinct independently judged report IDs still drive the existing two-round closure and repeated-failure rules.
- H2: Report and judge-pack IDs must be safe single filename identifiers. Reject empty, absolute, separator-containing, parent-traversal, and reserved device identifiers before any read/write outside the designated artifact subdirectory. Validate the report's stored ID as well as CLI arguments.
- H3: A completed report requires valid timezone-aware timestamps with finish at or after start, and a nonnegative finite wall-clock duration of the schema's expected numeric type. Malformed, missing, reversed, negative, and boolean-as-number timing values must fail validation. Existing valid reports remain accepted.
- H4: Semantic validation creates its disposable, credential-free CLI home inside the ignored workspace artifact directory, leaving the user's real configuration untouched. Cleanup tolerates a briefly locked temporary directory with bounded retries; persistent cleanup failures produce a contextual failure identifying the owned fixture. Do not skip semantic validation or report success when cleanup fails.
