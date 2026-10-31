# Customer server delivery: tasks 16-18

Worktree `.local/b6`, branch `feat/customer-server-readiness-20261031`, based on reviewed shared candidate `e832def` (draft PR29). Main operational source remains
`fd365f1`; no live database migration or customer deployment is authorised by a
test. Recovery checkpoint193523 preserves source, consistent SQLite and3595
protected files. Existing approvals, uploads and records remain authoritative.

| ID | Expected behavior | Implementation/owner | Verification | Actual result | Status |
| --- | --- | --- | --- | --- | --- |
| 16.1 | Exact-source installable candidate with local image archives and hashes; no secrets/data bundled | Customer package agent: deploy/customer and builder | Unit/integration and disposable Linux build/install | Pending | In progress |
| 16.2 | Clean persistent initialization; existing targets refused; restart preserves files/records | Customer package CLI | Disposable Docker install/restart/negative cases | Pending | In progress |
| 16.3 | Private LAN HTTPS and authenticated scoped evidence; raw media denied | Customer package/unchanged Django policy | Actual proxy and separate client network namespace | Pending | In progress |
| 16.4 | Second authorised physical LAN browser works on customer target | Customer operator/owner | Real server and second device | No approved target or second device access recorded | Blocked |
| 16.5 | Already-started legacy/native jobs keep first durable model pin after AI settings activation | Backend agent in B5; root integrates reviewed fix | Executed regression RED, integration GREEN, independent QA |235 affected tests, independent QA and separate security checks passed; parent CI41221090193 Windows1473/Linux1471+2 skips/Chromium passed | Verified |
| 17.1 | Operational pages load critical styles/scripts/fonts locally | Offline agent: templates/static/vendor | Rendered-page and real-browser external-request assertions |34 bundled assets, SHA inventory and5 original SRI values checked;18 affected tests and68 real browser assertions passed, zero automatic third-party requests | Verified |
| 17.2 | Saved login/task/upload/review/report operations work with internet unavailable | Offline agent/independent QA | Isolated real records and blocked third-party networking |68 saved-data browser assertions and14 restart assertions (included) passed under controlled network isolation; no physical disconnected-NIC test | Verified |
| 17.3 | Connected functions and local-AI prerequisites are described accurately; no hidden downloads | Existing pipeline + mode guide | Negative offline/queue/asset/model checks |Modes and prerequisites documented; strict bundled OCR preflight and missing-model cases passed. Native vision accuracy/live provider credentials remain separate gates | Verified |
| 17.4 | Installation uses supplied local archives without registry/pip/model downloads | Package agent/root Linux CI | Missing-image, archive validation and offline install | Pending | In progress |
| 18.1 | Maintenance responsibilities, supported scope and exclusions are concrete | Root: service offer | Agency review against existing capability/requirements | Draft prepared, no binding commitments | In progress |
| 18.2 | License and commercial policy approved by owner | Owner | Explicit approval of completed offer and third-party route | No owner decision or commercial-license evidence recorded | Blocked |
| QA | New behavior has executed RED/GREEN tests, independent user-flow review and full regression | Root/Agency QA | Ordinary isolated runner, CI, browser | Pending | In progress |
| AppSec | Separate post-functional review; report findings without unapproved repairs | Agency AppSec | Bounded isolated adversarial tests |12 separate PDF/OCR security checks passed; CP1/CP2 confirmed, owner explicitly approved repair; independent closure pending | In progress |

First supported package target is Linux/amd64 with Docker/Compose already
available. This reuses the existing Django deployment, not a replacement app or
a claim of a native Windows installer. Offline package operation does not imply
that Docker itself, GPU drivers, model weights or customer certificates are
installed. No model is silently downloaded or exposed on a public listener.

All A12/BR1/D1/D2/L1/CS1/CS2/AI1 holds retain their existing approval status. A
customer-package rehearsal is not permission to ship vulnerable dependencies,
claim license clearance, approve engineering work or deploy to a real customer.
The new legacy-job fix is a functional regression repair, not an AI1 audit fix.

## Approved repair follow-up

The owner explicitly approved CP1 and CP2 on31 October2026. Existing private
RED evidence is retained. The package developer owns tracked regression tests
and implementation; independent Agency QA and a separate AppSec reviewer own
verification. Approval does not waive earlier security holds.

| ID | Expected behavior | Verification | Actual result | Status |
| --- | --- | --- | --- | --- |
| CP1 | Interactive owner creation validates the same local Docker boundary as other operations, preserving terminal input | Executed RED, positive local-TTY control, independent negative tests | Repair in progress | In progress |
| CP2 | Tracked key/credential artifacts cannot enter a distributable package; public certificates and safe references remain usable; no secret logging | Actual synthetic Git exports, filename/content negative cases, public controls | Repair in progress | In progress |
| CI route | Installation rehearsal uses actual application endpoints | Registered Django resolver regression, independent rerun | RED1 error; GREEN1 test; independent1 passed. Actual Docker verification remains separate | Verified |

Free local PDF/OCR evidence is in FREE_PDF_OCR_INTEGRATION_20261031.md and the
independent QA/security reports. No paid PDF/OCR API was found or introduced.
Remaining MuPDF drawing use is local but retains its licence/redistribution gate.
The actual printed three-line OCR benchmark retained1/3 exact-spacing and3/3
alphanumeric results; do not substitute the separate one-line pass for that limit.
