# PR21 repair and verification register

Owner authorization: 26 October 2026, "Run the fixation with sequence ... create a pr".
Base: merged PR21, `37acc72cc5d25874eca56bbd05d7e1285d745b49`.
Branch: `fix/pr21-readiness-20261026`.

The owner authorized the previously listed S1/C1/M1/W1/S2/S3/R1/R2 repairs.
Historical approval-hold statements in older reports remain historical records.
New findings from the separate closing security review require their own approval.
No operational data, installed models, existing desktop services or live VPS are changed.

## Sequence and acceptance

| Order | Item | Status | Required evidence |
| --- | --- | --- | --- |
| 1 | S1: control generation and retry idempotency | Implemented; focused GREEN | 35 backend tests and 7 frontend checks; stale/forged tokens denied, exact retries harmless |
| 2 | M1: source-backed suggestions | Implemented; focused GREEN | Empty/generated-only findings withheld; real zero/False supported; 61 regression tests |
| 3 | C1: current mapping context | Implemented; focused GREEN | 99 mapping/worker tests; stale receipts hidden, valid partial advice retained, no inference on GET |
| 4 | R1: submission-scoped progress | Implemented; focused GREEN | 10 tests; outside-revision same-task photo denied, scalar ticks remain snapshot-free |
| 5 | R2: partial startup cleanup | Implemented; portable logic GREEN | 7 lifecycle tests; actual Windows process-tree validation remains pending |
| 6 | W1: PDF preview integrity | Implemented; focused GREEN | Signed manifests/hash/context, corrupt-cache recovery, original preservation, TOCTOU probes |
| 7 | S2: consistent retained-file access | Implemented; focused GREEN | Active-or-explicit-authorized-historical access on both routes; malformed IDs denied |
| 8 | S3: missing-task handling | Implemented; focused GREEN | Missing/foreign removal denied without mutation; six new document repair tests pass |
| 9 | QA collection restore | Implemented; GREEN | Four collection/checkpoint/category refresh checks, plus existing guided/gallery regressions |
| 10 | Worker endpoint and startup guidance | Implemented; metadata checks GREEN | 35 combined startup/runtime tests, 2 Windows-only skips; no model downloads/inference |
| 11 | Test automation and documentation | Configured; local checks GREEN | Linux/Windows backend and Chromium CI jobs; hosted CI results recorded separately |
| 12 | Mobile evidence access | Implemented; browser geometry GREEN | 109 assertions, 1920/1366/1024/390 widths; physical phone acceptance remains pending |
| 13 | A12 native crash | Requires actual PC | Capture diagnostics and reproduction; no root-cause closure without native evidence |
| 14 | Full-site, phone and VPS acceptance | Requires target environments | Real-site accuracy/time, interrupted transfers, HTTPS worker and restore rehearsal |

## Verification policy

Execute meaningful failing tests before each code repair, then focused unit/integration
checks. Run the final whole suite after integration, followed by a separate adversarial
review. Do not label unavailable Windows/browser/native/production checks as passed.
Open a reviewable PR; do not merge or deploy automatically.

## Final gate

All eight approved code repairs are implemented. Final backend: 1,190 run,
1,188 passed, 2 explicit Windows-only skips, zero failures/errors. Frontend:
14/14 scripts and 109 responsive geometry assertions passed. Sixteen independent
backend security probes passed; the separate review established no new finding.
All 327 frozen product-source files stayed unchanged during final verification.
See `PR21_REPAIR_VERIFICATION_20261026.md` for commands, scope and open target checks.
