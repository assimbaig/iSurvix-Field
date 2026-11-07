# Account recovery and email implementation

## Scope and release state

The candidate adds migration `0065_account_recovery`, two private recovery tables, public CSRF-protected recovery forms and a reset queue in the existing email worker. No operational migration or live recovery release was performed by this implementation agent.

The separate independent review identified **AR-Q1 Medium**: repeated requests from one IP can consume the global hourly recovery budget before the per-IP limit rejects them. The finding is reproduced in isolated data and remains held pending explicit owner approval. Do not treat this candidate as cleared for release while that finding is unresolved.

## Storage and controls

- `AccountRecoveryRequest` stores an opaque UUID, keyed email/authentication fingerprints, a bearer-token fingerprint, expiry, use/invalidation timestamps and bounded delivery state. It stores neither the password nor the raw bearer token.
- Link tokens use a dedicated HMAC purpose and the server secret. The registered email, password, last-login state, active flag and deliberate profile lock are rechecked. Ambiguous duplicate email addresses fail closed.
- A new reset invalidates older outstanding requests. Successful consumption is transactional and writes only the password field, preserving concurrent account edits. Existing sessions fail Django's password-derived authentication hash; recovery does not authenticate the caller.
- Recovery link lifetime is 30 minutes. Throttles use shared database state, a one-hour window, account limit3, IP limit10 and global limit100. Current-window throttle cardinality is bounded; expired throttle rows are reclaimed. See the held AR-Q1 ordering finding above.
- Forwarded-IP headers are ignored locally. The explicit `ACCOUNT_RECOVERY_TRUST_PROXY_IP` switch is enabled only behind the reviewed private-backend proxy, which overwrites `X-Real-IP`; invalid/multi-value input falls back to `REMOTE_ADDR`. Arbitrary `X-Forwarded-For` chains are never trusted.
- No request-derived host or `next` redirect enters an email. The existing HTTPS/allowed-host public-origin validator controls links and logo URLs.
- Production Nginx access formats exclude URI/query/bearers, and the supervised Gunicorn access log is disabled. Recovery responses use no-store and same-origin referrer policy.

## Delivery

The existing management command processes invitation, recovery and workflow queues with rotating priority:

```powershell
.local\venv\Scripts\python.exe backend\manage.py run_invitation_email_worker --settings=checklist.settings_local
```

Use the established production environment/settings on a hosted installation. Microsoft credentials remain in the existing protected credential file; do not put them in commands or repository files.

Provider calls stay outside short database transactions. A lease lasts120seconds; requests use the existing bounded OAuth/send transport. Definite retryable failures receive at most3 automatic attempts. An expired sending lease becomes uncertain and is not automatically resent. Explicit `--retry-failed` retries only definite, currently valid failures; expired/changed account links cannot be revived.

`GraphMailClient.send(..., branded=True)` renders escaped HTML only after its fresh-scope callback. Default callers still use the existing Text payload. The shared presentation helper also supplies a plain-text signature representation, but Graph sends one body content type; this is not a multipart delivery claim. The fixed same-origin logo is `/static/core/img/ifield-logo.webp`. Only same-origin HTTPS application URLs are made clickable by the renderer. Subject/body limits, canonical sender, credential privacy and ambiguous-POST handling are preserved.

Company onboarding and normal project invitations continue through the same original outbox. Specific default copy distinguishes company-admin activation from project-role invitations, while respecting saved custom company templates. Account creation through invitation acceptance does not send a password or create a duplicate invitation email.

## Verification evidence

- Initial TDD execution:10 tests failed because recovery and presentation did not exist. Independent QA separately reproduced missing-route failures before implementation.
- Final broad email execution:193 tests,191passed and2platform-specific skips;36 connections to in-process HTTP fixtures and zero external-network attempts. Command: `scripts/run_backend_tests.py core.test_account_recovery core.test_account_email_presentation core.test_invitation_email core.test_invitation_email_independent core.test_invitation_email_security core.test_workflow_email core.test_workflow_email_security core.test_workflow_email_independent core.test_notification_email_transport core.test_custom_notifications core.test_notification_customization_security core.test_custom_notification_upgrade --verbosity 1` using the established project Python.
- Expanded account recovery module:18 tests passed, including real local OAuth/send HTTP fixture delivery, single-use consumption, expiry, changed account data, CSRF, unavailable accounts, generic responses, limits, interrupted sends, bounded retries and password validation.
- TDD reproduced and corrected starvation of the new queue when both older queues were busy, and a broad user save overwriting a concurrent account-field edit. Password writes are now narrow and queue priority rotates.
- Existing workflow security assertions still verify recipient scope, absence of private remarks/AI findings/credentials/attachments and unchanged engineering decisions. Their expected body type intentionally changes to HTML for approved branding; no privacy assertion was removed.
- Registered project-role invite tests use an authorised company Admin. Existing policy correctly rejects a platform-owner-issued Client invitation; it was not weakened to make the test pass.
- Two older digest tests incorrectly activated their historical November6 schedules using the real current date. Their complete activation/event/cutoff lifecycle now uses a controlled clock; no product scheduling or no-backfill rule changed. A saved-scope callback fixture now explicitly accepts/asserts branded presentation rather than throwing an unrelated argument error; all cancellation checks remain.

Tests use isolated databases/media and controlled HTTP fixtures. They do not establish delivery to a real recipient. The lead's live non-sending OAuth check passed, and the inspected live invitation/workflow outboxes were empty; no current provider failure was reproduced from those facts.
