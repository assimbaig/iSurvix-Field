# Source and environment baseline - 28 October 2026

The fetched remote review branch contains merged PR23 at
`fd365f107b75c370caa2b765837d2a23f907a80c`. Before reconciliation the main
directory was on `review/pr22-local-20261026` at `2b05179`; the previous preview
was preserved at `0656dec`. The GitHub default branch is not assumed to be the
application's accepted release branch.

After a complete verified checkpoint and disposable restore, the main directory
was advanced by creating `review/pr23-local-20261028` at the pinned merged
revision. No reset, merge or deployment was performed. Earlier branch references
remain recoverable in the verified Git bundle. The two untracked audit reports
remain byte-identical; all restored operational tables/files also matched.

The audit worktree `.local/b0` uses branch
`audit/baseline-recovery-a12-20261028`. Its product code is exactly the tested
baseline; this task adds evidence/runbooks/ledger only. The existing `.local/wip`
preview source is preserved at `0656dec`, not silently discarded or repurposed.

Target environment: Windows11 build26300, Python3.12.10, Django6.1.2,
Node22.23.2, npm10.9.8 and the installed Edge browser. Package/version and exact
check receipts are in the companion JSON and `BASELINE_QA_20261028`.

The full1237-test run recorded1236 passes, no assertion failures, one unchanged
Windows symlink-privilege fixture error and no skips. All19 frontend scripts and
Django/migration/dependency/syntax/static checks passed. Source fingerprint:
`1bc667534b90fdb1aca80b02d5e8a9174bfa9d46463cd62af2ad1fa4c8ea86fb`.
The daemon-interrupted initial run was archived and not counted as successful.

No app/worker was running at the baseline start and none was launched. Existing
Ollama11434 reports0.40.10 but actual images fail because its runner is missing.
An existing project runtime temporarily on owned11436 completed3 requests but
misread all3 labels; that diagnostic service was stopped. These observations
neither fix nor establish the cause of historical Linux native crash A12.

No source-data migration, model/runtime/dependency download, engineering approval
or production rollout was performed. See `DELIVERY_LEDGER.md` for exact status,
the independent restore/security findings and remaining acceptance blockers.
