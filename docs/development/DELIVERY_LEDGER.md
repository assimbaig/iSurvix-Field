# iSurvix Field delivery ledger

31 October 2026. Four acceptance checks are Verified; task03 remains Blocked.
Task06 is In progress. Due dates were not supplied. Verification is not deployment.

| ID | Phase | Task | Status | Owner | Due date | Completed date | Acceptance check | Notes / evidence / PR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 01 | 0 Baseline | Reconcile source and environment | Verified | Dot |  | 2026-10-28 | Baseline branch, source and tests recorded. Operational data unchanged. | Main source reconciled to merged PR23 fd365f1 on review/pr23-local-20261028. Earlier refs and uncommitted audits preserved. Full1237 tests recorded:1236 passed,1 Windows symlink-privilege error;19 frontend checks passed. See BASELINE_SOURCE_ENVIRONMENT_20261028 and BASELINE_QA_20261028. Baseline verification is not release acceptance. |
| 02 | 0 Baseline | Create the delivery ledger and recovery procedure | Verified | Dot |  | 2026-10-28 | Restore a disposable backup. Verify originals and review history. | Fresh trusted checkpoint restored to .local/r0:4657 file hashes and70 tables match;862 originals/862 previews/1 document/2 logos verified through readonly restored Django. BR1Low is reported/unfixed; same-drive and ACL/off-device limits remain. See BASELINE_RECOVERY_PROCEDURE_20261028 and BASELINE_QA_20261028. |
| 03 | 0 Baseline | Investigate native AI crash A12 on the actual target PC | Blocked | Dot |  |  | Identify crash cause and pass real image tests on the target PC. | Historical Linux Python139 lacks native core/backtrace and failing build environment. Five Windows named regressions pass but do not identify cause. Standard Ollama500 missing runner; project runtime completed3 image requests but0/3 labels correct. No repair/installation performed. See A12_NATIVE_INVESTIGATION_20261028. |
| 04 | 1 Company access | Define and implement company boundaries | Verified | Dot |  | 2026-10-28 | Prove company A cannot access company B records, files or jobs. | Defined employer-Company scope; current authority/retained records and immutable worker-company pins implemented. CompanyA/B records/files/jobs HTTP+browser positives/denials passed. Full1287:1286passed,1existing Windows fixture error;19frontchecks. Migration0054 tested on disposable copy only. Implementation defc27d; draft PR25 https://github.com/assimbaig/iSurvix-Field/pull/25. No operational migration/deployment. PR25 subsequently merged upstream as 7d69e57; operational checkout was not deployed. |
| 05 | 1 Company access | Separate platform-owner and customer-administrator permissions | Verified | Dot |  | 2026-10-31 | Role tests reject privilege escalation. Audit privileged changes. | Platform/customer authority overrides rejected; transactional allowlisted privileged-change audit verified. Full1323:1322passed,1existing Windows symlink privilege error,0failures/skips.19frontend checks passed; independent unit/HTTP/browser/security checks passed within scope. Implementation81982db. Draft PR26 https://github.com/assimbaig/iSurvix-Field/pull/26. No operational migration/deployment. See PLATFORM_CUSTOMER_ADMIN_IMPLEMENTATION_20261031.md. |
| 06 | 1 Company access | Build Apply -> Review -> Provision -> Invite onboarding | In progress | Dot |  |  | Two companies onboard separately. Replayed requests create no duplicates. | Controlled platform-owner intake and separate review/provision/invite flow under implementation. Independent RED tests executed. No public registration or staging rollout. |

## Evidence and scope

The phase0 tested product baseline is merged PR23 `fd365f1`. The main local checkout is
now on `review/pr23-local-20261028` at that revision. Audit documentation is on
`audit/baseline-recovery-a12-20261028` in `.local/b0`. Earlier PR22/PR23 references,
the previous preview worktree and the two uncommitted audit reports are retained.
Phase0 changed no application code. Task04 code/migration changes are isolated on `feat/company-boundaries-20261028`, implementation `defc27d`, draft [PR25](https://github.com/assimbaig/iSurvix-Field/pull/25). Operational source/data were not deployed or migrated; no approval decision changed.

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

## Task04 evidence

Company-boundary definition, implementation report, acceptance JSON, worker migration guide and independent QA/security reports are under `COMPANY_BOUNDARIES_*`, `COMPANY_WORKER_BINDING_MIGRATION_20261028` and `INDEPENDENT_COMPANY_BOUNDARIES_QA_20261028`. The tested source fingerprint is `a563121f6519168c3c180b97bc90648b7a6f7299bebc50e633f4e672558fa0a5`. In-scope CompanyA/B acceptance is Verified; wider Windows symlink, A12/native-image and production proxy/rollout gates are explicitly not claimed complete. Unknown legacy worker pins fail closed until authorized reissue; current local credentials0. No new exploitable finding was established by the scoped separate security phase; prior approval-held findings remain untouched.


## Task05 evidence

See PLATFORM_CUSTOMER_ADMIN_IMPLEMENTATION_20261031.md and independent QA/security reports. Draft PR26 remains for review. The Windows symlink fixture remains blocked; no full-green or deployment claim is made.
