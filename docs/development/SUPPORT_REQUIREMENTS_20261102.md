# System Health & Support: tasks 22–25

Worktree `.local/b7`, branch `feat/gpt-support-workflow-20261102`, starts at
merged PR30 `a811130cc6e722a74594d713be85e522111665a5`. Its tree matches verified
PR30 head `b86b8a2`. The five existing report edits were preserved and carried
forward. Full source/data checkpoint: `.local/backups/project-checkpoint-20261102-180503`.
The operational checkout and schema0053 remain unchanged.

| ID | Expected behavior | Owner / implementation | Verification | Actual result | Status |
| --- | --- | --- | --- | --- | --- |
|22.1|Current company Admin sees only permitted company/project health; platform owner has administrative scope; other roles denied|Backend: support service/views|Unit and authenticated HTTP positives/foreign/revoked negatives|17 backend tests;13 independent HTTP/unit checks re-passed on e549; foreign/revoked/same-company unassigned access denied|Verified|
|22.2|Health and offline diagnostic ZIP use a bounded allowlist; omit secrets, raw logs, paths, evidence and free-text descriptions|Backend: report snapshot/export|Canary secrets, ZIP inspection, no-network tests|Independent canaries/digests pass; actual saved export has exactly two allowed JSON members; no description/evidence/credential data|Verified|
|22.3|Saved reports and compact real support workspace, clear errors and responsive controls|Frontend: support templates, scoped menu|Saved-data desktop/mobile browser and keyboard checks|42 independent browser assertions;48 actual report-to-install assertions and28 independent live rechecks at1920/1366/390; scoped Appearance overlap RED→GREEN|Verified|
|22.4|No background model/network calls, purchases or false GPT replies; offline workflow remains useful|All components|Network isolation and source/runtime checks|No model/API call; isolated ordinary tests and actual browser external-request controls pass; disconnected model reported honestly|Verified|
|23.1|Validate report/version/digests; stage only exact tracked source into fresh isolated workspace|DevOps: scripts/support_repair.py|Malformed bundles, traversal, source/patch mismatch tests|25 operator tests pass; actual saved-case BASE/report/patch/test/FIX bindings independently checked; source scans reject private runtime artifacts|Verified|
|23.2|Execute candidate code only in an OS-isolated, resource-bounded container without internet, credentials or production mounts|DevOps: repair runner/CI|Negative local preflight plus actual disposable Linux container|Actual corrected Docker runs41476832662/41477079364 pass host-owned probes; original synthetic sentinels unchanged; local unsupported execution fails closed|Verified|
|23.3|Synthetic regression fails for the intended bug, patched unit/integration tests pass, exact tested commit produces a real draft PR|DevOps + lead publisher|Separate test-only rehearsal branch, actual CI and actual draft PR|Actual saved report8f43f59c…→BASE9365df1→TESTS1a0c7bf executed2fail/1pass→FIX983f8c7 all3pass→real draftPR32; published-mode Docker and independent artifact review pass; do not merge fixture|Verified|
|24.1|Immutable case/report and append-only events link report, tested PR, owner approval, release and installation|Backend: support models/services|Unit/HTTP persistence, replay and mutation denials|Same actual saved report retains six events through real lab BASE→FIX restart; independent SQLite/browser/source checks pass; no operational installation|Verified|
|24.2|Current permissions, expected version and idempotency enforced; company Admin cannot approve platform repair/release|Backend|Role, cross-company, stale/concurrent/replay tests|Independent unit/HTTP/CSRF/role/revocation/replay/stale/audit-rollback checks pass; Admin live UI remains read-only for owner actions|Verified|
|24.3|Strict operator-attested receipts remain labelled as such; no web shell, arbitrary URL fetch or self-approval|Backend + DevOps|Receipt tamper/binding tests and source/runtime review|Exact realPR32 receipt imported into original case; forged/malformed/foreign/stale evidence rejected; provenance visible and independent AppSec controls pass|Verified|
|24.4|Installation can be recorded only against the actual configured runtime release matching the owner-approved commit|Backend|Mismatch/unknown/stale rejection and controlled matching-release positive|Actual BASE runtime refused installation400; same isolated DB restarted from actual approved FIX source then confirmed, reloaded and independently checked|Verified|
|QA|Executed RED/GREEN, unit/integration, actual browser/hosted sandbox, independent QA and separate security review|Lead + Agency reviewers|Focused checks, full final suite, source freeze and evidence review|e549 all5hosted gates passed:Windows1672pass, Linux1670pass+2existing skips,19frontend; local1671pass+1existing Win1314error retained; separate QA/AppSec and actual Docker passed; no local-all-green claim|Verified|
|25|Complete cloud/customer/AI/update/recovery release acceptance|Owner/operator + lead|Actual approved pilot, devices/native runtime, target/off-device recovery, licence/security disposition and exact owner release approval|Missing target/pilot/native/physical/licensing/approval evidence; controlled tests cannot substitute|Blocked|

## Ownership and boundaries

- Backend Architect owns `support_*` backend modules, model/URL registration,
  migration0058 and backend tests.
- Frontend Developer owns support templates/assets, the role-scoped menu link and
  focused UI tests. It uses real backend data and existing branding.
- DevOps Automator owns the host-only repair tool, its tests and disposable CI.
- The lead owns integration, delivery evidence and the working ledger. Independent
  QA and a separate Application Security Engineer review the implemented result.

No application process executes a patch. An authorised operator stages a report
and code patch outside the web process. A local Git worktree alone is not an OS
sandbox. The actual synthetic demonstration must execute in disposable Docker CI
without production data or secrets and create a clearly labelled review-only PR.
Operator-attested evidence, owner approval and engineering acceptance are distinct.

Existing A12/BR1/D1/D2/L1/CS1/CS2/AI1 findings keep their approval status. This
request does not authorise their repair, a public deployment or engineering
approval. New findings from the separate security review must be reported first.

Separate review confirmed **SS1 Medium**: candidate application code could forge
a passing test summary before unchanged assertions ran. The owner explicitly
approved its repair. A trusted host controller now checks bounded business
responses; candidate verdicts are ignored. Generic Django repair execution fails
closed until a separately reviewed external adapter exists. The 25 functional
tests and 15 independent attack/positive controls passed. Original RED probes
are retained unchanged; their legacy no-executor API now fails closed rather
than being presented as two green tests. Actual new-source Docker verification
and the saved-case-to-PR demonstration remain pending. See the separate review.

The first candidate's real Linux customer upgrade exposed a functional
0057-to-0058 regression: Django adds two content types and eight default support
permissions. The strict old comparator rejected these additions and safely
rolled back. Eight new tests executed a real isolated migration and negative
grant/mutation checks; all 37 affected metadata/retention/updater tests passed.
Only those exact unassigned framework metadata rows are allowed; retained rows
and every user/group grant remain protected. Re-run actual Linux upgrade CI on
the fixed source before claiming upgrade acceptance.

## Separate Codex startup repair

The optional OpenAI Developers `openai-api-credit-promo` MCP connector received a
Cloudflare HTTP403 browser challenge at the ChatGPT account-link endpoint. The
documented plugin-scoped policy now disables only that optional connector. Codex
0.166.0 accepted the configuration and its effective MCP list reports it disabled.
Backup/receipt: `.local/codex-mcp-repair-20261102-150256` in the canonical project.
The upstream service was not repaired; full Codex restart verification remains
separate. No key, billing, model or iSurvix connection change was made.
