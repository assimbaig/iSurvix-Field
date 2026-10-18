# Workflow crash recovery

## Observed failure

On 17 October 2026, review actions posted to `/custom-checklist/1/[object RadioNodeList]` and returned 404. Separately, checklist saves and session loads logged SQLite `database is locked` errors. The user's activity remained Submitted; it was not approved or reset during recovery.

## Corrections

The review form has multiple controls named `action`. Browser named-property lookup therefore makes `form.action` a `RadioNodeList`, rather than the form destination. `survey_workspace.js` now obtains the destination with `getAttribute('action')`. CSRF, save-before-review ordering and approval role checks remain.

The idle photo worker previously acquired and released the shared inference lease every poll, generating writes even without jobs. It now performs one read-only existence check and returns without lease acquisition when no queued/running jobs exist. Local startup enables SQLite WAL once with a bounded timeout. Local short atomic transactions use IMMEDIATE mode and a 30-second busy timeout. Model inference remains outside database transactions; request-wide transactions remain disabled.

## Preservation and verification

A consistent source/database/media checkpoint was taken before recovery in `.local/backups/project-checkpoint-20261017-213352`. Live checklist and assignment rows matched that checkpoint after restart, including answers, approvals and Submitted status. No restore, deletion or automatic approval was performed.

Real Edge checks exercised Engineer save → submit and Team Lead save → partial approval, full approval, rejection and request changes using actual templates/JavaScript with synthetic records and a loopback stub. All destinations and payloads were correct; no invalid object URLs were sent. Six focused backend checks covered WAL concurrency, idle polling and worker retry/recovery. Authenticated read-only checks passed for the actual Engineer and Team Lead record. WAL was verified active; Django configuration and migration drift checks passed.

Final combined regression results are recorded in `LOCAL_CODEX_HANDOFF.md`. Browser reproduction files remain under ignored `.local/render_submit_regression_fixture.py` and `.local/review-submit-browser-regression.cjs`; no real workflow decisions were changed by those checks.
