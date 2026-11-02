# System Health & Support: independent functional QA

2 November 2026. Independent Agency Reality Checker, worktree `.local/b7`,
branch `feat/gpt-support-workflow-20261102`, base `a811130`. The reviewer read
the repository instructions, installed Agency profile, original task22–25
acceptance and `SUPPORT_REQUIREMENTS_20261102.md`. This is functional QA,
separate from the later Application Security Engineer review.

**Latest result:** the 13 independently authored unit/real-Django-HTTP tests
passed again on fixed feature head `e5490a6038eac03a926a55de8cc3e669e15012bf`.
The real hosted Docker artifact and real draft PR32 now exist. The reviewer
independently verified35 artifact/Git/database bindings and28 read-only browser
assertions against the same saved synthetic case after its actual FIX runtime
restart. Tasks22–24 have bounded functional acceptance evidence. The local full
suite retains its existing L1 Windows privilege error. All five hosted feature
gates passed on exact `e5490a6`, including Windows/Linux, Chromium and the shared
candidate. A later documentation commit requires its own current-head gates.
Generic Django repair
execution is deliberately unsupported. Task25 remains Blocked. The earlier
checkpoint narrative below is preserved and superseded by the final addendum.

The new-page Appearance overlap found by independent visual QA was subsequently
reproduced RED, repaired by the lead and retested GREEN. The same42 saved-data
browser assertions passed again after that scoped fix; these repeat executions
are not42 additional unique checks. Final captures use `after-appearance-` names.

## Independence and scope

The reviewer owns only the private QA harness/logs under
`.local/support-development-20261102/qa` and this report. No application code,
implementer tests, operational account/data, source approvals, Git commits or
deployment was changed. Fresh synthetic TestCase records and the frontend
agent's explicitly synthetic browser database on loopback8977 were used.
The browser reviewer created its own report rather than accepting the
implementer's completion assertion or reusing its test script.

The backend and UI were functionally integrated while the host runner/CI
integration was still in progress. These executions are bounded evidence,
not a frozen-source full-release gate. Independent counts must not be summed
with overlapping ordinary/full-suite executions as unique product tests.

## Executed unit and authenticated HTTP verification

From the B7 root, using the existing project interpreter and private QA module
directory on `PYTHONPATH`:

```text
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py qa_independent --verbosity 2
```

**13 passed in0.906s** (complete command wrapper6.547s), no failures/errors/skips;
zero external network attempts and zero HTTP-fixture connections. Actual Django
migrations through0058 were applied only to the disposable test database.

Verified behavior:

- Health uses current accessible projects, not all projects in the same company;
  foreign-company and same-company/disjoint-project reports and exports are denied.
- Engineer, QA, Team Lead, Client, legacy Project Manager and a forged staff/
  `SUPER_ADMIN` profile without superuser authority cannot enter the workspace.
- Project revocation is rechecked after a previously successful request. A
  company-level report is visible only to its creator and the platform owner.
- Real create POST, exact-request replay, browser-refresh GET and conflicting
  changed-input POST preserve one report/event. Unexpected scope fields are
  rejected and CSRF remains required.
- The real ZIP export contains exactly `diagnostics.json` and `manifest.json`;
  its report bytes, SHA256, case ID and source release agree. Synthetic secret,
  company/project/site/model names, stack text and free-text report description
  do not enter that ZIP. The actual host tool's `read_bundle` accepted this real
  web export; this was not a hand-written lookalike fixture.
- The snapshot remains unchanged after a new job/status is added. Unknown job
  statuses are bucketed as `other`; diagnostics neither invoke a model nor run
  a command.
- Report/events are append-only through the ordinary ORM APIs. Governance audit
  binds the case/report digest; an injected audit failure rolls back both rows.
- Actual authenticated HTTP transitions require owner authority and explicit
  steps. A recorded receipt remains operator-attested and does not automatically
  approve a repair or engineering work.
- Case/source/report/PR tampering, duplicate JSON keys and unsupported JSON are
  rejected without changing saved history. Stale actions return409 and retain
  user input; exact action replay does not append another event.
- Installation confirmation rejects a runtime/version mismatch. A controlled
  matching-runtime setting permits the explicit final event; this is a test
  setting, not evidence of an installed customer release. The engineering
  checklist row remains byte-for-value identical across the support chain.

Private evidence: `qa/qa_independent.py`, `independent-unit-http.log` and
`independent-unit-http-receipt.json`.

## Independent real-browser workflow

Command:

```text
node .local/support-development-20261102/qa/qa-browser.cjs
```

**42/42 assertions passed** using installed Edge/Playwright at1920×1080,
1366×768 and390×844. The browser used private synthetic session cookies without
printing them. The reviewer exercised:

1. Open the actual company-Admin support workspace and create a new saved report.
2. Render potentially unsafe text as text, with no script execution.
3. Download the actual diagnostic ZIP; refresh the report and retain version1.
4. Confirm Admin sees no owner receipt/approval controls.
5. Open the same saved case as platform owner and request isolated repair.
6. Submit malformed receipt JSON; verify the400 error, original input, unchanged
   version2 and unchanged event count.
7. Import an explicitly controlled QA operator attestation; verify its label and
   that no approval occurs automatically.
8. Make separate synthetic owner repair/release decisions; reject a requested
   installed state because the running fixture release does not match.
9. Check all three viewport widths for no page-wide horizontal overflow, and
   mobile keyboard access to the readable Save control.

Observed: zero JavaScript page errors, zero unexpected console errors, zero
external request attempts, zero unexpected HTTP errors or failed requests.
There were two intentional400 responses and one expected `ERR_ABORTED` associated
with a completed Content-Disposition download. The saved ZIP separately passed
CRC, two-member, case-ID/digest and description-exclusion verification.

Seven independent screenshots are retained in the private QA folder:
`qa-admin-detail-1920.png`, `qa-admin-detail-1366.png`,
`qa-admin-detail-390.png`, `qa-owner-detail-1920.png`,
`qa-owner-detail-1366.png`, `qa-owner-detail-390.png`,
and `qa-admin-index-390.png`. The reviewer visually inspected the1366 Admin and
390 owner captures; geometric checks alone were not treated as visual proof.

Private receipt: `qa/independent-browser-receipt.json` and
`qa/independent-browser-zip-receipt.json`.

### UI observation found, repaired and retested

The existing fixed Appearance widget overlaps the report-digest area in the
390px full-page owner screenshot. No horizontal overflow or blocked primary
Save action was observed, but that overlapping evidence label should not be
described as perfect layout. The frontend owner and lead were notified. The
reviewer authored a real-browser regression before the lead's scoped repair.
This is a functional/visual observation, not the separate AppSec phase.

The deterministic390×844 regression measured the collapsed dock against
`.role-page-content` at top/middle/end (scrollY0/983/1966). All three cases failed
with3,902.625px² overlap, while Appearance opening/closing remained functional.
Original screenshots and `appearance-red2-receipt.json` are retained unchanged.
The test disables only browser smooth scrolling so those positions are exact.

The lead added a body class only to the two support pages and placed the shared
Appearance control in a separate in-flow footer for that workspace. No unrelated
screen was redesigned. An initial retest still saw the old cached template in
the `--noreload` fixture; this was not counted as a successful retest. The lead
authorised a verified restart of only the owned synthetic8977 fixture. Its
existing database/cookies were preserved; no setup/reseed or operational change
occurred.

The **same deterministic regression then passed** at all three positions with
zero overlap, working open/close and zero JavaScript errors. Current private
evidence is `appearance-green2-receipt.json` plus three viewport screenshots.
The affected42 saved-data/browser assertions also passed again with zero
unexpected JavaScript/console/network/HTTP errors, two intentional400s and one
expected successful-download abort. The reviewer visually inspected the new390
owner and1366 Admin captures; the control now remains outside content. All seven
final screenshots have prefix `after-appearance-`. The original seven, original
receipts and original downloaded ZIP remain preserved.

## Earlier checkpoint: acceptance disposition and remaining evidence

| Requirement | Independent result | Remaining limit |
| --- | --- | --- |
|22 scoped health and secret-free offline export|Verified in the tested synthetic unit/HTTP/browser scope|Final source/full-suite and separate AppSec gates belong to the lead|
|22 compact real workspace|Saved-data browser checks passed at three widths; scoped Appearance regression RED→GREEN and affected-flow rerun passed|Full final source/release acceptance remains separate|
|23 isolated repair|Real web ZIP accepted by actual host consumer; no local Docker execution claimed|Actual Docker/no-network proof and an actual tested draft PR remain outstanding|
|24 report→PR→approval→release→installation audit|Actual saved-data HTTP/browser lifecycle verified with explicit attestation and runtime checks|Browser receipt was controlled QA data, not task23's real CI artifact; no customer deployment or owner release approval inferred|
|25 complete release acceptance|Blocked|Approved pilot/target/native/physical tests, off-device recovery, licensing/security disposition and exact owner release approval remain separate|

The old A12/BR1/D1/D2/L1/CS1/CS2/AI1 holds were not repaired or waived. No new
Ollama, paid API or provider request was made. A green bounded QA result does
not establish universal correctness or complete production acceptance.

## Earlier reviewer handoff

The separate Application Security Engineer review subsequently reported
SS1/Medium in host-runner test-result interpretation. The lead reported that
finding as unfixed pending owner approval. This functional reviewer did not
repair that parser, alter its adversarial test or waive that review finding.
Task23 must retain that separate disposition alongside its pending actual
sandbox/PR evidence.

After the lead authorised cleanup, the reviewer stopped only the verified
synthetic8977 wrapper41856 and verified its HTTP listener closed. Existing
database, session-cookie fixture and screenshots were retained. The database
integrity check returned `ok` with seven saved synthetic support cases. No
operational server, worker, model or port was stopped. Private evidence:
`qa/fixture-shutdown.json`. `qa/verified-source-observation.json` records eight
current source hashes; it is an observation, not a fabricated before/after
freeze claim for the earlier executions.

## Final independent addendum: actual saved case, sandbox and installed FIX

The reviewer resumed after the owner's explicit SS1 approval and the separate
AppSec closure. The AppSec report records15 new adversarial closure checks,
13 retained controls and unchanged source hashes; those are separate evidence,
not the functional reviewer's tests. The host runner SHA observed independently
is `54c478b58bd86a334bc44dfa807d7d259653a5f7651225fe587b34359c90ec00`.
The new real CI artifact uses a trusted host black-box business controller,
not candidate-authored console verdicts. The eight older holds remain separate.

The final ordinary test command was run from B7, with the private QA directory
on `PYTHONPATH`:

```text
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py qa_independent --verbosity 2
```

Result: **13 passed, zero failures/errors/skips**,0.936seconds; isolated memory
database/media and zero external network attempts. This reruns the same13
independent tests, not26 unique tests. Log:
`qa/final-ci/independent-unit-http-final.log`.

The actual synthetic case is `8f43f59c-9c2b-4e59-8efe-0877a0863e14` in the
separate `.local/sl7` database/media. Its original running BASE was
`9365df1186d17cfb7a82a7d3ad7f8c815d93354e`. The test commit is `1a0c7bf`;
the reviewed FIX is `983f8c7b78a545cfbd27437246bc11be1d7f7cdc`. The retained
real local regression log shows3 tests with2 failures before the fix and3
passing afterward. Source changes between BASE and FIX are confined to the
explicitly synthetic fixture directory.

Actual review-only [draft PR32](https://github.com/assimbaig/iSurvix-Field/pull/32)
was independently checked open, draft and unmerged, with that exact BASE/FIX.
It must not be merged. Real Linux
[run41477079364](https://github.com/assimbaig/iSurvix-Field/actions/runs/41477079364)
completed successfully; job125385389643 executed the offline-container stage.
The reviewer independently downloaded artifact13157808151, verified its
GitHub-published SHA256
`461850434351ab07617b0dbfbf7fe6d2a3603f230fe5c91abe0fe329f158d205`,
ZIP CRC and six allowed artifact members. No artifact source was executed.

The artifact's trusted controller records baseline unit and integration
failures (five business probes each, two failures each), and candidate unit
and integration passes (five probes each, no failures/errors/skips). All four
probes report read-only inputs, blocked network, absent credentials and absent
Docker socket. Execution explicitly reports no production mounts or forwarded
credentials. This is real hosted Docker evidence; no local Windows Docker
execution is claimed.

The reviewer caught and corrected an evidence wording overclaim: the downloaded
web ZIP is736bytes and the CI repacked ZIP is1,116bytes, so the ZIP containers
are **not** byte-identical. Both `manifest.json` and `diagnostics.json` payloads
are byte-identical. The original ZIP remains unchanged with SHA256
`dae0e9bfe4f0bd8fbefc10e427742075cefac7ccafd7e63f64d0605e1497fbb8`.
The report SHA is
`e02a6ff28e78cbfc38196e85e865f78de47950378f23e00025e1b1e37b0a291b`.
The lead corrected its receipt/guide to distinguish container repackaging from
unchanged member data. No source data or approval was altered for this finding.

Independent `check_actual_chain.py` passed35 assertions: actual artifact and
saved-case bindings; report/base/tested-commit identity; linked receipt differing
only by the actual PR URL; host verdict ownership and four isolation probes;
real Git patch/regression/test-source hashes; retained original export; database
integrity; and the six persisted ordered events:

1. Reported.
2. Isolated repair requested.
3. Tested PR receipt recorded.
4. Tested repair approved by the synthetic owner.
5. Exact release approved by the synthetic owner.
6. Exact installed release confirmed.

The same database still has one saved synthetic case. The reviewer opened it
read-only and did not create any approval or installation event. Before the
restart, the lead's actual browser receipt records HTTP400 when BASE did not
match the approved FIX, with no false installation event. The live listener
PID21484 was independently observed running the actual
`.local/srf7/backend/manage.py` on loopback8980; its Git HEAD matches the FIX.
Only the synthetic lab was restarted; operational installation is not claimed.

Independent `check_actual_browser.cjs` then passed28 read-only assertions using
actual owner/Admin logins, real Django pages and the same saved case. It checked
CSRF login fields, private/no-store responses, persisted installed state and six
history rows, exact BASE/FIX/PR references, Admin absence of owner controls,
refresh persistence, and1920/1366/390 layouts. No JavaScript errors, failed HTTP
responses or external requests occurred. Six new screenshots are retained in
`qa/final-ci/independent-installed-{owner,admin}-{1920,1366,390}.png`.
The reviewer visually inspected the390owner and1366Admin captures.

The lead's separate actual write-path browser receipts record16 create/export,
17 receipt/approval/runtime-mismatch and15 actual-FIX/install checks. The
reviewer read those receipts and the actual six-event database; they are not
relabeled as independently executed actions. The independent28 read-only
assertions supplement the earlier42 saved-data browser assertions and exact
Appearance RED2→GREEN2 regression. These overlapping evidence sets are not a
single unique product-test total.

| Task | Final independent functional disposition | Precise boundary |
| --- | --- | --- |
|22|Verified for authorized scoped health, immutable saved reports and offline allowlisted export|No live GPT/API or native-AI claim; secret canaries and role/scope negatives tested|
|23|Verified for the explicitly synthetic protected repair profile, actual offline Docker execution and real unmerged draft PR32|Generic Django repair adapters are unsupported and fail closed; no operational patch applied|
|24|Verified for actual case→tested PR→separate synthetic owner approvals→actual matching lab runtime installation, retained in six audit events|Operator attestation stays labeled; synthetic owner actions are not production release approval|
|25|Blocked|Actual approved pilot, customer/native/physical targets, off-device recovery, licence/security disposition and exact production release approval remain external|
|Final regression gate|All five hosted gates passed on exact e5490a6|Local full suite retains the explicit L1 privilege error; a later documentation commit still requires its own current-head gates; no global all-green claim|

### Independent customer-upgrade artifact check

The reviewer independently downloaded artifact13157773844 from successful
feature-head customer-package
[run41476832604](https://github.com/assimbaig/iSurvix-Field/actions/runs/41476832604).
The95,790-byte archive matches GitHub SHA256
`efcc2b9529877695e466c490d910829c2e0fb58036023ccf4a3e4db4f77dc947`;
CRC and archive paths were checked before inspection. The reviewer read actual
package/recovery/client receipts and startup/shutdown logs, rather than treating
the workflow badge alone as retention proof.

Thirty-seven read-only cross-artifact consistency assertions passed. These are
artifact assertions, not37 new unit tests. They check exact `e5490a6` provenance,
schema0057→0058, identical retained73-table/374-row digests, package metadata
hashes, common app/Nginx image identities, caught-failure rollback, interrupted
recovery, successful completion, no automatic downloads, preserved source,
original evidence hash, anonymous original denial and owner operational-access
denial. Source/target retained digest:
`31261cf7f79307574718c07183a3e98d7ba59488918bbfa0a0f9f8533fe20eee`.

Receipts explicitly preserve the limits: the separate client is an isolated
container namespace, not a physical customer device; no native AI, physical LAN,
customer deployment or owner release approval is claimed. Existing approval
holds remain in the package manifest. Evidence is in
`qa/final-ci/customer-verification` and `independent-customer-checks.json`.

### Full-run issue requiring disposition

The lead's final2 ordinary backend execution finished with1,672 tests in
671.209seconds, zero assertion failures and one error. The reviewer inspected
the actual traceback, not just the run summary:
`RuntimeAdversarialTests.test_diagnostic_directory_symlink_is_rejected_without_touching_target`
raises `OSError: [WinError 1314]` in its fixture's `Path.symlink_to` call before
the application-under-test runs. This Windows process lacks symlink privilege.
That result establishes a test-environment dependency, not successful behavior
and not an observed application assertion failure. The original security
acceptance must remain intact; silently skipping it would not close the gate.
The lead identified this as the existing, unapproved L1 environment hold, so
the fixture was not altered or skipped and the process was not elevated. Exact
source Windows/Linux hosted application results remain separate evidence;
they cannot retroactively make this local execution green. The source final
log and L1 disposition remain preserved.

The lead's finished `final2/receipt.json` records unchanged source before/after,
fingerprint `3c09818d4896a47b4ded828f15c3735ac2e5c46e525a8cedd3882a99c159d5c8`,
19 frontend scripts and12 ancillary checks passed. The reviewer inspected the
receipt and backend traceback. Ancillary checks include Django checks, migration
drift, dependency consistency, JavaScript/Python/shell syntax and isolated static
collection. Local backend wrapper duration is680.078seconds; the actual test
runner duration is671.209seconds. These are deliberately distinguished.

The reviewer independently fetched hosted application job logs for exact
`e5490a6` from
[run41476832696](https://github.com/assimbaig/iSurvix-Field/actions/runs/41476832696):
Windows ran1,672 tests in654.184seconds, **OK with no skips**; Ubuntu ran1,672
tests in504.225seconds, **OK with two skips**. Both dependency checks were clean,
both migration checks reported no changes, and the Chromium frontend job passed.
The hosted Windows environment exercised the symlink test successfully; this
does not remove or approve local L1. The test totals overlap by platform and
must not be summed as3,344 unique product tests.

### Independent shared candidate check and source freeze

All five exact-source feature gates were independently rechecked successful:
application41476832696, staging41476832605, customer41476832604,
isolated repair41476832662 and shared41476832664. The reviewer downloaded the
shared candidate **once** for reuse at
`qa/final-ci/shared-candidate-e549.zip`. Its476,047,095bytes match GitHub SHA256
`2b7dcad41a65d667d24b8fe8f961be1846eab20b81ba8d4b07012f24a2698140`.
The full ZIP CRC and paths were checked. Only the package manifest, shared
release record, consumer receipt and three approved metadata files were
extracted into `shared-candidate-proof`. No image or candidate source was
extracted or executed by the reviewer.

Nineteen independent consistency assertions passed: the shared record and
consumer receipt bind exact `e5490a6`; both editions use the same app/Nginx
images; manifest and three metadata files are byte-identical to the separately
verified customer artifact; the manifest SHA and supported upgrade source
agree; the three required application/staging/customer gate references identify
the actual green runs for that exact commit; and all eight holds remain listed.
The consumer receipt accurately says **static** customer verification, with no
Docker execution in that particular assembly step. Actual Docker installation
and upgrade evidence comes from the separately verified customer workflow.
The record remains `candidate_only: true`, `owner_release_approved: false`.

Shared/customer manifest SHA256 is
`1893c6c9dc99971ea15214f616b9efb8829b6581d752415f565a973297c6b70b`.
Receipts: `independent-shared-download.json`, `independent-shared-checks.json`
and `independent-hosted-application.json`. The SHA covers this exact candidate;
it must not be presented as a candidate for a later documentation commit.
This report is now frozen for the lead's documentation-only delivery commit.
The lead must inspect the resulting new head's gates before the final report;
no later merge, deployment or acceptance is implied.

Private final evidence is under `qa/final-ci`: independently downloaded CI ZIP,
safe extracted receipts,35-assertion chain receipt,28-assertion browser receipt,
13-test final log and six screenshots. The lead stopped its verified8980 lab
after this review, preserving the same database and six events; the independent
reviewer did not stop it. No model, paid API, operational record,
engineering decision or production service was changed.
