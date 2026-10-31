# Independent company onboarding verification

Scope: delivery task06, Apply -> Review -> Provision -> Invite. The current
implementation is being developed separately from this independent test module.
The controlled intake is recorded by the platform owner; this work does not
establish a public applicant registration portal or deployed staging acceptance.

## Evidence and execution status

Independent meaningful RED was executed before production implementation:

```powershell
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' scripts/run_backend_tests.py core.test_company_onboarding_independent --verbosity 1
```

The run failed because `CompanyApplication` did not exist. Twelve tests describe
saved-record behavior: separate company/industry-bound Admin invitations, existing
invitation acceptance, human review prerequisites, replay idempotency, changed
payload rejection, rejected requests, disabled industries, existing-company
conflicts, current platform authority, audit rollback and secret omission, and
authenticated valid-CSRF HTTP operations. The ordinary runner reported zero
external network attempts and isolated database/media/model cache.

Functional GREEN: all 12 independent saved-record tests passed with zero external
connections. This covers actual stored records and authenticated HTTP, not mocked
provisioning. It does not establish actual browser invitation acceptance.

## Browser finding before functional completion

The recovered original browser fixture had one synthetic application in Reviewed
state after interruption. That partial fixture was retained; the independent
reviewer created a new isolated `qa-resume` SQLite/media fixture on loopback8943.
The original owned8942 server was stopped after checking its command identity.

In the fresh real browser, the platform owner successfully recorded, reviewed,
provisioned and invited Company A. Refresh retained those transitions and the
one-time bearer was not shown on the saved GET. Actual invited Admin acceptance
then failed with HTTP403. The browser emitted `Origin: null`; Django's CSRF log
records `Origin checking failed - null does not match any trusted origins.`
The existing acceptance response uses `Referrer-Policy: no-referrer`. No new Admin
was created. The functional integration is therefore **not yet verified**.

This was reported to the implementation lead before the separate AppSec phase;
the independent reviewer made no product changes. Private receipt paths:
`qa-resume/browser-error.json`, `qa-resume/browser-app.log` and the original
preserved `qa/browser.sqlite3`. Final browser and separate security results must
be recorded after the functional repair and rerun. No full-success claim is made.

## Final functional rerun

The implementation lead executed a failing origin-policy regression and repaired
the existing invitation response to `Referrer-Policy: strict-origin`. CSRF was not
disabled and opaque/foreign origins were not trusted. A fresh isolated fixture
then completed both company onboarding paths in real Microsoft Edge/Playwright.

**39 browser checks passed, zero failed**, covering:

- Existing owner Administration entry, empty intake state and saved applications.
- Both companies' actual Apply, Review, Provision and Invite steps with reloads.
- Actual replayed intake, provisioning and invitation POSTs returning the same
  application, without another bearer response or duplicated records.
- Both new company Admins accepting their real hashed invitations through the
  existing account-creation form and reaching their authenticated workspaces.
- Customer Admin denial from the platform onboarding workspace.
- Desktop1366×768 and phone390×844 geometry, persisted status and safe screenshots.
- `strict-origin` invitation response and no observed outgoing request referrer
  containing the invitation bearer path.
- Zero browser JavaScript errors and zero failed local requests.

The isolated server blocks all outgoing Python connections; browser requests to
external hosts are blocked by the harness. No Ollama request occurred. The old
partial fixture was retained; final verification used `qa-final/browser.sqlite3`.

Independent readonly SQLite verification confirms exactly two applications, two
distinct provisioned companies, two invitations and two accepted Admin accounts.
Each Admin has its own company and requested industry, no primary project and no
global `is_staff`/`is_superuser` flags. No projects were automatically created.
Each company has exactly one applied/reviewed/provisioned/invited audit plus one
invitation-created and one invitation-accepted event despite request replays.

## Visual defects found and repaired before completion

The first mobile screenshot showed an unreadably squeezed six-column table and a
low-contrast Record application link. The independent reviewer added and executed
actual computed-color and layout browser checks: **6 passed,4 failed**. CTA contrast
was1.363:1, and the mobile table was squeezed instead of scrolling within its pane.

The lead repaired only scoped onboarding CSS and the table's accessible focusable
region. The exact checks then passed: **10 passed, zero failed** at desktop/mobile
widths, verifying CTA contrast≥4.5:1, readable status-column width, no page-wide
overflow and horizontal scrolling confined to the table panel. Final phone and
desktop screenshots were visually inspected and copied to
`screenshots/company-onboarding-20261031/`. These are synthetic accounts only.

## Exact focused commands and receipts

```powershell
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' scripts/run_backend_tests.py core.test_company_onboarding_independent --verbosity 1
node .local/company-onboarding-20261031/qa-final/browser.cjs
node .local/company-onboarding-20261031/qa-final/visual.cjs red
node .local/company-onboarding-20261031/qa-final/visual.cjs green
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' .local/company-onboarding-20261031/qa-final/verify_saved.py
```

The final independent12 unit/HTTP tests passed in0.391s, zero external attempts.
The browser command requires a fresh prepared isolated fixture and server; it is
not an idempotent command to run against operational data. Its deliberate replays
occur inside each scenario; repeated whole-suite runs require a new fixture.
An extra logout CSRF input caused one harness locator ambiguity; the selector was
scoped to the actual onboarding form. That was a harness repair, not a product bug.

Private final receipts: `qa-final/browser-results.json`, `browser-persistence.json`,
`independent-functional.log`, `visual-red.json`, `visual-green.json`. Failed and
partial fixture databases remain private for reproducibility. Session fixtures,
CSRF values, invitation bearers and raw error artifacts must not be committed.
The lead owns full-suite/migration/preservation verification. Separate AppSec
results are reported independently; these functional checks do not approve
production deployment or establish universally bug-free behavior.

Private receipts are under `.local/company-onboarding-20261031/qa/`; session-cookie
fixtures and one-time invitation bearer tokens must never be published. No native
AI, operational migration, customer account mutation or deployment is authorized
by this test work.
