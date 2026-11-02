# System Health & Support: independent functional QA

2 November 2026. Independent Agency Reality Checker, worktree `.local/b7`,
branch `feat/gpt-support-workflow-20261102`, base `a811130`. The reviewer read
the repository instructions, installed Agency profile, original task22–25
acceptance and `SUPPORT_REQUIREMENTS_20261102.md`. This is functional QA,
separate from the later Application Security Engineer review.

**Current result:** 13 independent unit/real-Django-HTTP tests and42 independent
saved-data browser assertions passed. Task23's real container execution and
tested draft PR are still pending the lead's hosted rehearsal. Task25 complete
release acceptance remains Blocked. No production-readiness or native-AI claim
is made.

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

## Acceptance disposition and remaining evidence

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

## Final reviewer handoff

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
