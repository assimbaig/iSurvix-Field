# Company Admin overview and per-release notices

This change improves the existing `/governance/` workspace. It does not replace the application or introduce operational roles, AI services or engineering approval rules.

## Implementation

- `core/admin_dashboard.py` prepares bounded, read-only totals and project summaries using existing access functions. Counts distinguish sites, activities, unique photos and links. Review-stage summaries use current records; expensive or unsupported historical classification stays explicitly unresolved.
- `core/governance_views.py` selects the new company Admin landing view and returns existing Project, Client and Invitation forms to it. Existing `?view=my_work` behavior remains available. Return hints never confer project authority.
- Dashboard templates and scoped assets implement Option A, with four creation actions, compact tables, accessible dialogs and responsive internal scrolling. Other-role template paths remain in place.
- The approved AD-S1 repair bounds project identifiers before integer conversion and retains the same accessible-project lookup. The independent malformed-ID regression remains in the suite.
- `core/release_notice.py`, `release_notice_models.py` and `release_note_content.py` provide all-role update notices. Hosted acknowledgement keys use the existing verified immutable release ID. Local development uses an explicit stable content identifier; request handling never invokes Git or an external service.
- Migration `0062_release_notice_acknowledgement` adds only account/release acknowledgement storage with a unique user/release constraint. Existing operational rows and evidence are retained. The customer upgrade verifier admits only the exact reviewed empty table and default Django metadata for this migration; it does not waive old-row or permission-grant checks.

The notice uses authenticated, CSRF-protected, bounded JSON requests. User identity comes from the authenticated request. A separate opaque login nonce rejects stale tabs/account changes. Checked dismissal persists for the current account/release; unchecked dismissal is limited to the current login. New release identities prompt again. Storage failures are explicit and session-only continuation remains available.

Update the truthful, user-facing highlights in `core/release_note_content.py` with each release. A build identity automatically controls the next notification; highlights are curated source content, not AI-inferred changes. Do not claim a service is enabled or verified merely because its code shipped.

## Preservation and verification

Use isolated databases and media for tests. Ordinary backend tests run through the repository's network-isolating runner:

```powershell
.local\venv\Scripts\python.exe scripts\run_backend_tests.py --verbosity 1
npm.cmd test --prefix frontend
.local\venv\Scripts\python.exe backend/manage.py check --settings=checklist.settings_local
.local\venv\Scripts\python.exe backend/manage.py makemigrations --check --dry-run --settings=checklist.settings_local
.local\venv\Scripts\python.exe -m pip check
```

Focused regressions include Admin totals, company/project boundaries, safe returns, preserved MyWork behavior, independent adversarial input checks, release identity, acknowledgement persistence, nonce/CSRF checks and migration/retention negative cases. Browser checks supplement component fixtures with real Django authentication, saved records, all supported role workspaces and desktop/mobile interactions. Report final commands, pass/fail/skip counts and CI against the exact delivery commit in the PR; component fixtures alone are not end-to-end acceptance.

The controlled dashboard benchmark uses two authorized projects, 40 checklists, one unlinked assignment and 463 photos. The original page measured 72.79 ms median, 55 queries and 43,262 response bytes. With release notices, the unseen-notice page measured 82.03 ms, 59 queries and 23,544 bytes; the acknowledged page measured 81.52 ms, 58 queries and 21,133 bytes. Payload was smaller; latency was not improved. Direct helper query count stayed at 20 for both 2 and 30 projects, with 25 visible project rows. These measurements are not a 100,000-user throughput benchmark.

Deployment/recovery continues to stop the existing web/proxy writer boundary. Notices introduce no independent process or background writer. Before local or hosted migration, prove retention on a coherent disposable copy. Hosted delivery requires the reviewed retention-helper prerequisite, exact-source checks and owner approval; never rewind records after public writes may have begun.

Local startup after the migration is verified:

```powershell
.local\venv\Scripts\python.exe backend/manage.py runserver 127.0.0.1:8000 --noreload --settings=checklist.settings_local
```

See the separate email handoff for the unresolved Microsoft sending-permission grant. These notices are application UI and do not require a Microsoft administrator sign-in.
