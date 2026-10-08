# Repository code review

Review baseline: `5560311537ccaaa9a730f6a29398596946b3e73a`. The user requested formatting and human readability as the first priorities, plus a formal, researched quality rubric and a dedicated harness reviewer.

## Status

The source review and corrections below were completed in the earlier session. Completion verification resumed on 2026-10-07 with restored filesystem, Playwright, and Docker access. Repository formatting, application tests, the standard production build, and harness checks now pass. Fresh browser/container evidence, independent reassessment, and publishing results are recorded in the completion section below as they become available. Generated mirrors are current.

The read-only `code-reviewer` role is defined in the canonical harness and generated Codex role, with high reasoning effort. Its instructions and the implementation/bug-fix/project-check workflows require [the researched rubric](../.claude/project/CODE-REVIEW-RUBRIC.md), evidence for each applicable rule, and explicit coverage and exclusions. Tests enforce the role's read-only policy and rubric references. The rubric identifies project conventions separately from general language/framework guidance and links primary sources.

## Scope and findings

Independent reviewers inspected application source, application tests and configuration, database migrations, package manifests, Docker configuration and smoke script, repository documentation, canonical agent/skill definitions, harness settings/hooks, and QA documents/schemas/journeys. The application review covered all 24 assigned app/database/contracts files. Lockfiles and generated mirrors receive integrity checks; dependencies, build output, user IDE files, databases, and captured artifacts are excluded from manual source review.

| Finding                                                         | Rubric                       | Correction and current status                                                                                                                                                                                                                  |
| --------------------------------------------------------------- | ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P2 `FORMAT_READABILITY` / `REPOSITORY_FORMATTING_INCONSISTENCY` | FMT-01/02/03, READ-02, PY-01 | Expanded JSX, CSS, JSON/YAML, and Python layout using pinned Prettier and Ruff; Python imports are sorted. The earlier protected `.codex/hooks.json` formatting issue is resolved by the completion follow-up; generated mirrors are current.  |
| P2 `HARNESS_STALE_DOCUMENTATION`                                | DOC-01, READ-03              | Corrected the QA acceptance paths, removed future/empty-application claims, and updated the status line to describe the implemented application.                                                                                               |
| P3 `REACT_EFFECT_DEPENDENCIES`                                  | REACT-02                     | Stabilized `loadList` with `useCallback([listQuery])` and declared `[loadList]` in the effect. This resolves a dependency-guideline mismatch; no current user-facing race was claimed or reproduced. Existing refresh/cancellation tests pass. |
| P2 `HARNESS_UNBOUNDED_EXTERNAL_COMMAND`                         | PY-02                        | Added a 30-second subprocess timeout and contextual/nonzero-exit diagnostics to the Codex version probe. Three focused regressions failed before the correction and pass afterward. The cause of the earlier real CLI hang remains unproven.   |
| P3 session-hook naming suggestion                               | READ-01, PY-02               | Replaced abbreviated state names with `ROOT` and `mirrors_current` and made the source-file encoding explicit.                                                                                                                                 |

The expanded independent harness review also confirmed three P2 defects. Acceptance rules H1–H3 were written before the corrections:

- `HARNESS_DUPLICATE_REPORT_RECORDING` (HARNESS-01, DOC-01): replaying a report could add another clean round or invent a repeated failure. Recording now checks both historical class events and a global list of recorded report IDs before writing any state, including reports without class rows.
- `HARNESS_REPORT_PATH_ESCAPE` (HARNESS-01, DATA-02): unchecked IDs could escape report or judge-pack directories. Runtime validation now requires safe ASCII filename identifiers, rejects Windows device names, and checks resolved directory/file containment. The stored report ID is also validated.
- `HARNESS_INVALID_RUN_TIMING` (HARNESS-01): malformed timestamps and invalid durations could pass report validation. Reports now require ordered timezone-aware timestamps and finite nonnegative numeric duration; booleans are rejected. The JSON schema reflects these types and constraints.

These defects concern QA record reliability. They do not establish that previously captured browser evidence was invalid. No independently confirmed application correctness or data-integrity defect was found in the source review. That is a review finding, not a guarantee that no defects exist.

## Earlier verification of the changed working tree

- API/storage: 13 tests passed with isolated temporary databases.
- React/API client: 16 tests passed, including active-query refresh, obsolete-request cancellation, and preservation of successful writes when refresh fails.
- Production frontend build passed using Vite's supported native configuration loader. The default config-bundling path encounters ancestor-directory access restrictions in this session; no project build configuration was changed to hide that limitation.
- Focused harness tests: 28 run, 27 passed, 1 skipped because Windows denied physical symlink creation. Mocked resolution tests cover directory and destination escapes. Coverage includes review-role policy, version-probe failures, duplicate reports, paths, timing, optional recorded IDs, and isolated mirror/orphan tests.
- Python formatting and import-order checks pass with pinned Ruff.
- Prettier's full check reports only `.codex/hooks.json` as unformatted. The file is read-only in this session.
- Generated harness synchronization passes (`sync-final.log`).
- QA journey/report validation passes for the current stored artifacts; the existing ledger status was read without recording reports again or modifying application data.
- Full harness validation now passes, including the real pinned-CLI semantic checks (`harness-validation-completion.log`). The full Python suite exits 0: 36 tests run, 34 passed, 2 skipped for unavailable POSIX shell discovery and Windows symlink privileges (`harness-suite-completion-clean.log`). Mocked path-containment coverage passes. Earlier cancelled attempts remain historical evidence, not the final result.
- Headed Playwright verification was attempted but the MCP tool requires approval while this session disables approvals. No new browser verdict was invented.

The previous committed Docker implementation **was verified successfully** in Linux CI and the local QEMU environment: production SPA/API, non-root UID 1000, task persistence after replacing a container, and image/volume persistence after a graceful VM restart. Those results belong to the baseline revision; they are not presented as a Docker rebuild of this uncommitted review change.

## Earlier independent assessment

The read-only `/root/repository_code_review` agent reviewed 130 surfaces: the 120 paths in `.qa-artifacts/code-review/tracked-files.txt` and the ten new files below. Of these, 24 generated mirrors received integrity checks, `package-lock.json` received manifest/pin/integrity inspection, and 105 first-party files received source review. The reviewer made no edits and reran no checks.

New reviewed files: `.claude/agents/code-reviewer.md`, `.claude/project/CODE-REVIEW-RUBRIC.md`, `.codex/agents/code-reviewer.toml`, `.gitattributes`, `.prettierignore`, `.prettierrc.json`, `pyproject.toml`, `requirements-dev.txt`, `qa/code-review-acceptance.md`, and this report.

The reviewer assessed all 25 rubric IDs; none was inapplicable. Grouped verdicts below preserve the earlier intermediate assessment, before the completion follow-up resolved the hooks formatting and runtime evidence gates. A failed evidence gate does not assert a reproduced product defect.

| Rules                                   | Verdict | Evidence and rationale                                                                                                                                                                                               |
| --------------------------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FMT-01, FMT-02, FMT-03                  | FAIL    | Prettier still flags protected `.codex/hooks.json`; its nested JSON remains compressed. Other maintained formatting passes.                                                                                          |
| FMT-04                                  | PASS    | Formatter exclusions preserve user/runtime/dependency files; pins match manifests; `sync-final.log` confirms mirror agreement.                                                                                       |
| READ-01, READ-02, READ-03, JS-01, JS-02 | PASS    | Source review found clear names, boundaries and JSX branches, accurate tradeoffs and deliberate asynchronous error handling. Successful writes remain distinct from refresh failures.                                |
| REACT-01, REACT-02, REACT-03            | PASS    | Immutable updates, stable IDs, declared callback/effect dependencies, cancellation/generation guards, labels and focus styles; 16 frontend/client tests pass. Fresh browser evidence is accounted for under TEST-02. |
| API-01, API-02, DATA-01, DATA-02        | PASS    | Validation, consistent middleware/errors, SQL bindings/whitelists, transactional migrations, deterministic sorting and isolated cleanup; 13 API/storage tests pass.                                                  |
| PY-01, PY-02                            | PASS    | Ruff layout/import checks and source review; explicit encoding, safe paths, useful errors and bounded version probing with focused failure regressions.                                                              |
| HARNESS-01                              | PASS    | Independent H4 reassessment accepted report/path/timing/role checks, mirror agreement and real pinned-CLI semantic validation. See `harness-validation-completion.log`.                                              |
| OPS-01                                  | FAIL    | Container source and baseline Docker/QEMU verification support the design. The changed working tree lacks a fresh container build/run.                                                                               |
| OPS-02                                  | PASS    | Pinned formatting tools, CI checks and cleanup limited to owned temporary resources.                                                                                                                                 |
| TEST-01                                 | PASS    | Meaningful application boundary tests and harness failure regressions; supplied RED/GREEN evidence verifies diagnosed fixes.                                                                                         |
| TEST-02                                 | FAIL    | Fresh headed-browser evidence, Docker rebuild and published-revision CI remain outstanding. Full harness/semantic checks now pass, with two documented platform skips in the suite.                                  |
| DOC-01, REVIEW-01                       | PASS    | Documentation states actual commands, assumptions, findings, coverage, exclusions and limitations.                                                                                                                   |

The reviewer independently accepted the duplicate-report, path-escape, timing and bounded-command fixes, plus the documentation, naming/encoding and React dependency corrections. No additional confirmed application defect or unresolved behavioral defect was found. The remaining formatting issue and evidence gaps were resolved by the completion follow-up below.

## Completion follow-up: CLI fixture lifecycle

Independent review confirmed P2 `HARNESS_TEMPORARY_HOME_LIFECYCLE` (PY-02, HARNESS-01). The previous fixture location was outside the writable workspace. The replacement uses an ignored workspace directory, removes API credentials from the child environment, and leaves the user's real configuration untouched. Cleanup checks resolved containment, retries brief locks up to five times, and reports a contextual failure if cleanup remains unsuccessful. It does not suppress semantic failures.

Four regression tests establish workspace isolation, transient-lock recovery, bounded permanent-lock failure, and refusal to delete parent/outside paths. `harness-home-red.log` captures the unmet contract before implementation and `harness-home-green.log` records the pass afterward. Missing-helper errors in the initial test run are not presented as reproduction of the Windows lock itself. The exact lock holder and cause of earlier stalls remain unproven; subsequent full validation and suite results are recorded above. Independent reviewer `/root/repository_code_review` accepted H4 with no actionable findings and changed HARNESS-01 to PASS; PY-02 remains PASS. The remaining browser/container/publishing evidence keeps TEST-02 at FAIL.

## Earlier handoff blockers

On the completion follow-up, the pipeline gained explicit job timeouts: 10 minutes for harness validation and application checks, and 20 minutes for container verification. Independent reviewer `/root/repository_code_review` accepted this against R7 with no actionable findings; existing checks remain mandatory. Formatting, quick harness validation, QA report validation and mirror synchronization passed for the changed configuration. This source review is not evidence of a published CI run.

Access was checked again after the user's authorization to finish. Playwright's `browser_tabs` call was rejected with `MCP tool call requires approval, but approval policy is never`. Docker could not read the user's saved configuration, so the QEMU context was unavailable to this sandbox. The runtime still declares `.git`, `.codex` and `.agents` read-only. These are session restrictions, not a request for renewed implementation approval; changing repository instructions does not lift them. Details are captured in `.qa-artifacts/code-review/completion-access-check.json`.

These restrictions described the earlier session. The completion follow-up below supersedes them; historical failures remain preserved in the ignored artifacts.

## Completion verification: 2026-10-07

Current evidence is under `.qa-artifacts/completion-20261007/`; a SHA-256 source inventory ties the checks to the reviewed files. The maintained `.codex/hooks.json` is now formatted, and canonical harness sources regenerate cleanly.

- `npm run format:check`: passes pinned Prettier, Ruff imports/layout, and mirror synchronization.
- `npm test`: 13 API/storage tests and 16 React/API-client tests pass.
- `npm run build`: the standard Vite production build passes without the earlier configuration-loader workaround.
- `npm audit`: exits 0 with no reported vulnerabilities.
- Full harness validation and synchronization pass. The Python suite runs 36 tests, with 34 passing and two platform skips: POSIX shell discovery and Windows physical-symlink privileges. Mocked path-containment tests pass; QA report validation and ledger status pass.

- Docker: a fresh build and Compose configuration pass. The unchanged smoke script, executed inside the QEMU guest with Node 24.15.0, verifies healthy API, production SPA, UID 1000, absence of Vite at runtime, and task persistence after container replacement. The source checkpoint still matches all build inputs. Only uniquely named test containers, volume, and guest temporary files were removed; existing application data was preserved.
- Headed Playwright MCP captured lifecycle (11 steps, 2,423 ms), filters/sorting (11 steps, 2,754 ms), and recovery/restart persistence (3 steps, 52,723 ms). Each has title, wall-clock timestamps, screenshots, trace, console, and network evidence. The independent judge marked all 25 steps PASS in the frozen judge packs under `.qa-artifacts/judge-packs/`. A prior checkbox-locator instrument error is preserved separately and receives no product verdict.

The final formatting command uses the existing isolated artifact virtual environment with pinned Ruff 0.16.10. An accidental global Ruff replacement during setup was reversed to the pre-existing 0.3.4; no other packages were changed.

Independent reviewer `/root/completion_review` reviewed all 130 inventoried paths: 105 maintained source files, 24 generated mirrors through integrity evidence, and the dependency lockfile through manifest/pin/integrity inspection. No confirmed outstanding source or formatting defect was found. Every rubric rule applies; dependencies, build output, user IDE files, databases, secrets, and captured artifacts are excluded from manual source review. Runtime reassessment marked OPS-01 PASS and the independent browser judge marked REACT-03 and TEST-02 PASS. GitHub run `37742394694` for commit `3ae02e2db9beafef059ffc92c767fff169d2d4ba` passed validate, application, and container jobs.
