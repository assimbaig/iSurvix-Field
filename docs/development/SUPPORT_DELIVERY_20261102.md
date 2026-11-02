# Support workflow delivery evidence

Feature branch: `feat/gpt-support-workflow-20261102`, based on owner-merged PR30
`a811130`. Application changes are in [draft PR31](https://github.com/assimbaig/iSurvix-Field/pull/31).
Implementation commits: `9824a38`, then approved SS1/upgrade repair `e5490a6`.
Later documentation commits do not change the executable source fingerprint.
No merge or deployment was performed.

## Implemented behavior

The existing Django application now has scoped `/support/` pages, current health,
immutable saved reports, an allowlisted offline ZIP, owner-only maintenance
decisions and append-only history. Existing project permissions and governance
audit controls are reused. The interface clearly labels operator-attested
evidence. Its web process cannot execute patches, call models or deploy a release.
Additive migration `0058_support_cases` was exercised only in isolated databases.

The separate host operator validates exact source/case/report/patch identities,
rejects private runtime artifacts, and stages fresh tracked-source workspaces.
Its supported business adapter runs in bounded offline Linux Docker. The host
owns the assertions; candidate console summaries cannot certify passing tests.
Generic arbitrary Django repair execution is deliberately disabled until a
protected external adapter is implemented and independently reviewed.

The real0057-to-0058 upgrade initially rolled back because two Django content
types and eight default support permissions violated the older row-count rule.
The repaired reviewed-host comparator permits only those exact unassigned
framework additions. Old rows and every user/group grant remain strict. Eight
new regressions and seven independent real-migration/tamper checks passed.
The corrected real Linux update, rollback, interruption recovery and replay
passed in run `41476832604` on `e5490a6`.

## Executed tests

From the feature worktree using the existing project Python3.12 environment:

```text
F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe scripts\run_backend_tests.py --verbosity 1
```

Local final2: **1,672 run,1,671 passed,zero assertion failures,one error,zero
skips**,671.209s. The error is the existing L1 Windows fixture's symlink creation
(`WinError1314`), before application behavior executes. It remains unapproved
for repair and was not altered, skipped or elevated. This local run is not green.
Zero external network attempts;103 connections to controlled in-process fixtures.

All19 existing frontend check scripts passed. Django checks, migration drift,
`pip check`, static collection, Python compilation, JavaScript parsing and the
reviewed deployment shell syntax checks passed. The final runner's before/after
executable-source fingerprint is identical:
`3c09818d4896a47b4ded828f15c3735ac2e5c46e525a8cedd3882a99c159d5c8`.
Exact commands, durations and logs are in
`.local/support-development-20261102/final2/receipt.json`.

All five exact-source hosted gates passed on `e5490a6`:

| Gate | Run | Result |
| --- | --- | --- |
| Application verification |41476832696|Windows1672passed/654.184s; Linux1670passed+2existing skips/504.225s; frontend Chromium passed; migration/dependency checks clean|
| Disposable staging |41476832605|Success|
| Customer install/upgrade/recovery |41476832604|Success;0057→0058;73retained tables/374rows; actual TLS/rollback/interruption/replay|
| Shared immutable candidate |41476832664|Success; verified exact-source package/images, consumer and provenance gates|
| Offline isolated support repair |41476832662|Success with repaired host-owned controller|

The hosted Windows success is separate from the unchanged local privilege error.
Later documentation-head checks must be observed separately on PR31; these run
identities attest the executable implementation source, not an unknown future SHA.

The actual shared candidate artifact13158552615 was downloaded and checked
against its GitHub SHA256
`2b7dcad41a65d667d24b8fe8f961be1846eab20b81ba8d4b07012f24a2698140`.
CRC/path checks passed. Its static consumer proof binds sourcee549 and manifest
`1893c6c9dc99971ea15214f616b9efb8829b6581d752415f565a973297c6b70b`;
this consumer step does not itself claim another Docker execution. The shared
record binds the already verified customer/staging/application runs and keeps
`candidate_only=true`, `owner_release_approved=false` and all eight old holds.
Artifact retention is seven days; preserve a trusted private copy before expiry.

Relevant tests include17backend,9UI,25operator,2delivery/schema and8actual
metadata-migration checks. Independent evidence sets overlap ordinary tests:
13unit/HTTP,42initial browser assertions,15SS1closure,13retained security and
7migration/tamper checks. They must not be summed into a unique product total.

The local frontend/build checks use these existing commands, without adding a
new application or build system:

```text
node frontend/check-*.cjs     # execute each existing script separately
python backend/manage.py check --settings=checklist.settings_local
python backend/manage.py makemigrations --check --dry-run --settings=checklist.settings_local
python -m pip check
```

The first line describes the set; the exact nineteen individual commands are
recorded in the final runner receipt. Shell wildcard execution is not claimed.

## Real saved-case acceptance

Controlled report `8f43f59c-9c2b-4e59-8efe-0877a0863e14` was saved/exported using
the actual browser while the lab ran BASE `9365df1186d17cfb7a82a7d3ad7f8c815d93354e`.
TESTS `1a0c7bf` executed three actual unit/file-CLI regressions:two assertion
failures and one pass. FIX `983f8c7b78a545cfbd27437246bc11be1d7f7cdc` changed only
the synthetic counter; all three regressions passed with unchanged test files.

[Draft PR32](https://github.com/assimbaig/iSurvix-Field/pull/32) is a separate
**TEST ONLY,DO NOT MERGE** rehearsal. Its actual offline Docker run `41477079364`
passed. Artifact `13157808151` SHA256:
`461850434351ab07617b0dbfbf7fe6d2a3603f230fe5c91abe0fe329f158d205`.
Both exported JSON member payloads are byte-identical; CI repackages their ZIP
container, so the ZIP archive bytes themselves differ.

The real receipt was linked to that real PR and imported into the original saved
case through the owner UI. Separate repair and release approvals were recorded.
Installation was refused against BASE with HTTP400. The owned lab server was
then stopped and restarted from actual FIX source against the same isolated DB;
installation confirmation succeeded and survived refresh. Six immutable events
remain. Root48browser assertions passed; independent QA separately checked35
artifact/Git/database bindings and28read-only live browser assertions. Screenshots
cover1920×1080,1366×768 and390×844. No JavaScript errors, unexpected HTTP errors or
external requests were observed. These counts describe overlapping executions.

The lab was stopped on2November16:06:24UTC. Only owned PID21484/listener8980 was
stopped. SQLite integrity is `ok`; all six events, source worktrees, exports and
screenshots remain under `.local/sl7`. This is not a customer/production install
or engineering approval.

## Startup and review

No new background worker is needed for support diagnostics. The existing survey
workers and native Ollama were not started or modified by this task. Do not run
the normal launcher against operational data merely to test migration0058.

To reopen only the retained synthetic acceptance lab on this PC:

```text
F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe F:\iSurvix\iSurvix-Field\.local\sl7\launch.py F:\iSurvix\iSurvix-Field\.local\srf7
```

Open `http://127.0.0.1:8980/support/`. Synthetic credentials are retained only in
the private `.local/sl7/credentials.json`; they are not production accounts or
included in Git. The helper binds the running release to actual committed Git
source, rejects dirty tracked files, and uses only the isolated lab settings.
Preserve its database. Owner installation confirmation is already recorded; do
not create new events just to recheck the page.

Follow [the team guide](SUPPORT_TEAM_GUIDE_20261102.md) and
[operator procedure](SUPPORT_REPAIR_OPERATOR_20261102.md) for the actual workflow.
Independent reports: [QA](SUPPORT_INDEPENDENT_QA_20261102.md),
[AppSec](SUPPORT_SECURITY_REVIEW_20261102.md).

## Preservation and remaining gates

Full recovery checkpoint `project-checkpoint-20261102-180503` has verified archive
CRC, consistent SQLite integrity and source/Git recovery artifacts. The final
preservation check rehashed3595protected files and all70operational tables,
including original evidence, private settings, credentials and branding. Both
pre-existing untracked audit reports are unchanged. Operational checkout remains
`fd365f1`/schema0053; no operational migration was applied. Checkpoint integrity
is not an off-device recovery or physical target acceptance test.

The owner-approved SS1 repair has independent bounded closure. Earlier
`A12/BR1/D1/D2/L1/CS1/CS2/AI1` remain unapproved/unfixed, including the two High
public-release dependencies. Generic Django repair needs a reviewed external
adapter. The optional credit-promo MCP connector is disabled in validated Codex
configuration; a full Codex restart/upstream403 repair was not claimed.

Task25 remains Blocked on actual pilot/native/physical/customer, licensing,
security disposition and exact owner release acceptance. No public launch,
manufacturer accuracy, universally secure operation or bug-free claim is made.
Current exact-head hosted workflow conclusions and final artifact identities
must be checked on PR31; running checks must never be presented as passed.
The requirements register has12Verified acceptance rows and1Blocked release row;
the overall27task ledger keeps release/handover gates separate from this feature.
