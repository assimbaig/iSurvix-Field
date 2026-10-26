# PR21 repair verification — 26 October 2026

Base: merged PR21 `37acc72cc5d25874eca56bbd05d7e1285d745b49`.
Branch: `fix/pr21-readiness-20261026`.
Scope: the owner's approved S1/C1/M1/W1/S2/S3/R1/R2 fixes, collection refresh,
phone navigation, explicit runtime setup, diagnostics and repeatable verification.
No live deployment, model download, operational data change or engineering approval.

## Final regression gate

| Check | Observed result |
| --- | --- |
| Full isolated backend suite | 1,190 tests run in 179.008 s: 1,188 passed, 2 explicitly skipped, 0 failures/errors |
| Isolation | Temporary database/media/model cache; zero external attempts recorded; 50 connections to in-process fixtures |
| Frontend | 14/14 scripts passed, including collection restoration and responsive geometry |
| Responsive navigation | 109/109 assertions at 1920/1366/1024/390 px, using portable Chromium 153 on Linux |
| Independent AppSec regressions | 16/16 backend probes passed; preserved in `core.test_repair_independent_security` |
| Independent PowerShell review | 3 cleanup probes and 1 wrapper failure/environment-restoration probe passed |
| Deployment checks | Django `check --deploy` with isolated production configuration: no issues |
| Schema | `makemigrations --check --dry-run`: no changes |
| Dependency consistency | `pip check`: no broken requirements |
| Static collection | 215 files collected to a disposable directory |
| Syntax/patch | Changed JS syntax, five PowerShell parses, Python compilation and `git diff --check` passed |
| Product source freeze | 327 product files unchanged throughout final gate; digest `5c4d75d724e9619359e8514987c62aaa47148755f930e4a709bd5102a3933cec` |
| Security-review source | Reviewed backend/runtime hashes still matched the separate review after final tests |

The full suite command was `python scripts/run_backend_tests.py --verbosity 1`.
The portable PowerShell runtime was supplied through `ISURVIX_TEST_POWERSHELL`.
`npm ci` and the committed `frontend/run-checks.cjs` ran the frontend checks.
Browser executable/arguments/font paths were isolated test-environment overrides;
neither GPU nor browser-security settings in the application were changed.
GitHub Actions is configured for Linux/Windows backend and Chromium frontend;
configuration does not itself establish a successful hosted CI execution.

## Executed failing tests before repairs

- S1: six initial control tests established five failed secure expectations:
  old Resume/Pause replay, missing token and forged token acceptance. Final focused
  control/HTTP/local/remote/progress regressions: 35 passed; pause frontend: 7 passed.
- M1: five new tests first established three failures, including two unsupported
  links from a real isolated worker flow. Source-support and existing mapping
  regression gate: 61 passed; meaningful zero/False and unanswered observations retained.
- C1: three initial failures established stale model/batch advice and receiptless
  partial advice. Final M1/C1/local/remote mapping gate: 99 passed.
- R1: a same-task photo absent from the frozen submission was incorrectly returned.
  New regression plus scalar progress tests: 10 passed.
- R2: the second survey-worker launch failure left its first owned process behind.
  Seven controlled PowerShell lifecycle cases passed after immediate-handle
  retention, partial rollback and one app/worker cleanup scope.
- W1/S2/S3: initial document gate reproduced serving a replaced PNG, Admin's old
  route bypass and an unhandled missing-task lookup. Final focused document/hosted
  gate passed; six new repair tests cover corrupt/forged cache, original integrity,
  current/historical access, malformed revision identifiers and missing tasks.
- QA collection: unassigned/suggestions restoration failed before repair. Four
  restoration checks passed afterward, with existing guided/gallery checks retained.
- Phone header: six new phone assertions failed while the original 103 passed.
  A single scrollable navigation row with 44 px targets passed all 109 assertions.

An early historical-access test probe omitted the route's `return_to` and received
the legitimate 302 redirect; the test was corrected to exercise the existing JSON
decision contract. Malformed revision inputs previously failed closed as 400;
bounded ASCII parsing now returns the same 404 policy as other invalid revisions.
Neither probe correction is represented as a separate security vulnerability.

## Independent security phase

A separate read-only reviewer inspected the completed repairs and attempted
cross-actor/revision/control-generation replay, post-receipt mapping mutation,
no-inference GETs, foreign/Client document access, cache corruption/path redirection,
post-read replacement, same-task/outside-revision sources, foreign removal,
startup cleanup failures, URL obfuscation, environment proxies, diagnostic symlinks
and worker-failure environment restoration. No new security finding was established.
The reviewer made no product edits. Installed Agency profiles were unavailable;
implementation and independent review roles were assigned separately.

## Explicitly open target-machine acceptance

Two tests are skipped here because they require actual Windows PowerShell:
native owned parent/child process-tree cleanup and the existing Windows launcher
endpoint-alignment test. Portable PowerShell logic checks are not substituted for
these OS-specific checks. Windows ACL behaviour must also be verified on target.

A12's original native crash is not resolved by this batch. The new diagnostic
collector records private versions/metadata/crash-signal categories without
inference or raw log upload; obtain a supported native reproduction/backtrace.
Real GPU accuracy/time, a full-size site, physical phones/interrupted networks,
CAD/engineering output acceptance, actual VPS/HTTPS worker access, concurrency and
consistent restore remain open. Automatic cloud fallback is not implemented.

Use [local acceptance](PR21_LOCAL_ACCEPTANCE_20261026.md) before running this
release on the PC. Do not replace local data, weaken version checks, merge or
deploy automatically. Earlier approval-held reports remain historical; the owner
explicitly authorized these eight repairs. New security findings require new approval.
