# Task06: company access delivery checklist

Owner: Dot. Phase1 Company access. Acceptance: **Two companies onboard separately.
Replayed requests create no duplicates.** Active scope is Company access only;
staging, AI settings and pilot/release tasks are deferred by owner instruction.

The existing application is reused. Apply means the platform owner records a
received application in a controlled administration screen. This does not launch
anonymous public registration, email delivery or automatic customer provisioning.
The owner reviews, provisions a distinct company and issues its existing type of
company/industry-bound Admin invitation. The invited Admin accepts through the
existing account-creation route and manages its own projects under existing rules.

| ID | Expected behavior | Location / owner | Verification | Status |
| --- | --- | --- | --- | --- |
| 06.1 | Current platform owner can record and inspect applications; other roles cannot. | Onboarding views/service; backend owner | Authorized HTTP/browser and role/session negatives | Verified |
| 06.2 | Apply, review, provision and invite are deliberate, persisted transitions; rejected applications do not provision. | Onboarding service/model | Unit and saved-record integration, invalid-order attempts | Verified |
| 06.3 | Two companies obtain distinct companies and correctly bound Admin accounts; no foreign record is claimed by matching name/email. | Existing Company/invitation acceptance reused | Actual two-Admin acceptance and saved company/industry IDs; existing Task04 isolation regressions | Verified |
| 06.4 | Request and transition replays preserve IDs and create no duplicate company, invitation or audit change. | Unique request key, normalized name and transaction serialization | Repeated same/changed requests, retries and DB assertions | Verified |
| 06.5 | Permissions, issuer/industry validity and posted authority are checked server-side. | Existing authority guards, new controlled forms | CSRF, stale/inactive owner, industry and forged-input tests | Verified |
| 06.6 | Durable audit is atomic; raw invitation bearer is shown once and never stored in DB/session/audit. | Existing hashed invitation and audit reused | Rollback, token replay/redaction tests and response headers | Verified |
| 06.7 | Existing records and historical approvals survive additive migration. | Migration0055; backend owner | Isolated forward/backward migration and actual-copy table comparison | Verified |
| 06.8 | Compact existing-brand UI is usable on desktop/mobile, has truthful error states and works after refresh. | New onboarding templates; backend owner | Independent real browser interactions, persistence and screenshots | Verified |
| 06.9 | Functional completion receives a separate adversarial security review; findings are reported, not silently fixed. | Independent Agency QA/AppSec | Attack tests and severity/evidence report | Verified |
| 06.10 | Existing regressions are checked on final source; operational data unchanged and review-only delivery recorded. | Lead | Full suite/frontend/system gates, preservation hashes and draft PR | Verified |

## Source and recovery

Worktree `.local/b3`, branch `feat/company-onboarding-20261031`, application
parent81982db (Task05, draft PR26). Source and operational state are deliberately
separate: the main working application remains fd365f1/schema0053. Neither0054 nor
0055 is applied to operational data in this task. Existing approval-held findings
remain outside scope; staging/native-model/production acceptance is not implied.

Checkpoint `.local/backups/project-checkpoint-20261031-165639-platform-customer-admin`
contains a fresh consistent SQLite backup, verified Git bundle and CRC-checked
source archive;3,595 protected files matched the trusted full recovery archive.
The suffix identifies the reused established checkpoint helper, not a deployment.

Agency ownership: backend implements model/migration/service/views/templates and
own tests; independent Reality Checker owns its own regression tests and isolated
browser fixtures; a separate AppSec agent owns the adversarial review; lead owns this ledger,
integration, final checks and delivery. No shared-file edit conflicts are intended.

Final evidence: COMPANY_ONBOARDING_ACCEPTANCE_20261031.json;1350run/1349passed/oneexisting Windows fixture error. DraftPR27, no merge/deployment. Acceptance coverage10/10 within this scope; not a full-green/production claim.
