# iSurvix Field delivery ledger

28 October 2026. Owner names, tasks and acceptance checks retain the supplied
list. **Two acceptance checks are Verified; task03 remains Blocked.** Due dates
were not supplied and remain blank. A blocked investigation has no completed date.

| ID | Phase | Task | Status | Owner | Due date | Completed date | Acceptance check | Notes / evidence / PR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 01 | 0 Baseline | Reconcile source and environment | Verified | Dot |  | 2026-10-28 | Baseline branch, source and tests recorded. Operational data unchanged. | Main source reconciled to merged PR23 fd365f1 on review/pr23-local-20261028. Earlier refs and uncommitted audits preserved. Full1237 tests recorded:1236 passed,1 Windows symlink-privilege error;19 frontend checks passed. See BASELINE_SOURCE_ENVIRONMENT_20261028 and BASELINE_QA_20261028. Baseline verification is not release acceptance. |
| 02 | 0 Baseline | Create the delivery ledger and recovery procedure | Verified | Dot |  | 2026-10-28 | Restore a disposable backup. Verify originals and review history. | Fresh trusted checkpoint restored to .local/r0:4657 file hashes and70 tables match;862 originals/862 previews/1 document/2 logos verified through readonly restored Django. BR1Low is reported/unfixed; same-drive and ACL/off-device limits remain. See BASELINE_RECOVERY_PROCEDURE_20261028 and BASELINE_QA_20261028. |
| 03 | 0 Baseline | Investigate native AI crash A12 on the actual target PC | Blocked | Dot |  |  | Identify crash cause and pass real image tests on the target PC. | Historical Linux Python139 lacks native core/backtrace and failing build environment. Five Windows named regressions pass but do not identify cause. Standard Ollama500 missing runner; project runtime completed3 image requests but0/3 labels correct. No repair/installation performed. See A12_NATIVE_INVESTIGATION_20261028. |

## Evidence and scope

The tested product baseline is merged PR23 `fd365f1`. The main local checkout is
now on `review/pr23-local-20261028` at that revision. Audit documentation is on
`audit/baseline-recovery-a12-20261028` in `.local/b0`. Earlier PR22/PR23 references,
the previous preview worktree and the two uncommitted audit reports are retained.
No application code, data migration, operational approval or deployment changed.

- `BASELINE_SOURCE_ENVIRONMENT_20261028.md` records source/environment reconciliation.
- `BASELINE_QA_20261028.md` and JSON record exact tests and independent review.
- `BASELINE_RECOVERY_PROCEDURE_20261028.md` and JSON document the actual restore.
- `A12_NATIVE_INVESTIGATION_20261028.md` and JSON separate historical A12, the
  current missing runner and incorrect image outputs.

The full suite is **not green**: the unchanged symlink test could not construct
its fixture because Windows denied privilege (WinError1314). Its security
assertion did not run. This is not the historical native process crash.

**BR1 / Low**: malformed file/directory prefix or Windows filename-alias conflicts
can leave partial files inside a newly created disposable restore destination.
No operational path was overwritten. Recommendation: reject these conflicts in
preflight. The finding is reported and **not fixed without owner approval**.
Use only the verified self-created checkpoint and mark failed targets incomplete.
Other previously held security findings remain under their original approval rules.

Task03 needs the original Linux crash core/native backtrace and matching failing
native environment to establish A12's cause. The standard Windows Ollama also
needs its missing compatible runner restored, followed by correct source-backed
image results. HTTP completion alone is insufficient; current diagnostic labels
passed0/3. No extra model, runtime repair or paid/cloud fallback was introduced.

This same-drive drill proves restoration of the checked source/data, not off-device
disaster recovery, Windows ACL restoration, credential revocation or engineering
acceptance. Read-only restored Django used the existing installed environment.
The app and workers stayed stopped; only the original loopback Ollama remains.
