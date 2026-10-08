# Public repository publishing checks

The user requested a new public `CodeGameDev29/TodoList` repository with the existing verified implementation and history.

| ID  | Acceptance                                                                                                                               | Evidence                                          |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| P1  | Public GitHub repository exists at the requested owner/name and main matches the local committed source.                                 | GitHub repository metadata and remote SHA         |
| P2  | GitHub Linux CI runs the full harness validation without weakening checks, bypassing failures, or relying on interactive login.          | GitHub Actions validate job                       |
| P3  | GitHub application job installs, runs all application tests and builds the SPA.                                                          | GitHub Actions application job                    |
| P4  | The identified shell-quote advisory is removed from the development dependency tree; the development command still starts both services. | npm audit and isolated development-start evidence |

Initial P2 failure: run 37496723841, validate job 112383039302. The semantic Codex check failed; stderr reported refusal to create helper binaries under the system temporary directory. Preserve diagnostic evidence in ignored `.qa-artifacts/publish/`. Fix only the diagnosed harness portability issue and add an appropriate regression check; no product scope changes.

Diagnosis: an isolated credential-free reproduction showed that `doctor` also fails its authentication health check even when configuration loading succeeds. Configuration validation must not require a personal Codex login. The replacement must perform real strict configuration loading, reject unknown configuration fields, retain prompt rendering validation, and exit without any model request. Both stdout and stderr must be available for failures. Validation homes must be isolated, automatically cleaned up, and outside the system temporary directory.
