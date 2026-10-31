# Independent customer-server review — 31 October 2026

Worktree `.local/b6`, branch `feat/customer-server-readiness-20261031`, based on
`e832def` plus the customer package/offline/local-PDF changes under review.
The reviewer read `AGENTS.md`, the handoff, development rules, customer-server
requirements and installed Agency Reality Checker/API Tester profiles. The
reviewer did not implement the package, offline assets or PDF/OCR product code.
Ownership was restricted to `core/test_customer_independent.py`, private QA
fixtures and this report. No operational database, evidence, credentials,
approval, existing service, customer machine or native Ollama model was changed.

## Result

The exercised candidate-preservation, offline HTTP and local PDF/OCR boundaries
passed the tests below. One separately reported **provisional Medium context
validation gap** remains unfixed. This is **not customer-release approval**.
Actual Docker installation and a second physical LAN device remain separate
gates; mocked Docker commands cannot establish those results.

## Independent commands and receipts

From `.local/b6`, using the existing shared interpreter:

```text
F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe scripts\run_backend_tests.py core.test_customer_independent --verbosity 2
F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe scripts\run_backend_tests.py core.test_customer_package core.test_customer_offline core.test_pdf_tools core.test_local_ocr_offline core.test_customer_independent --verbosity 1
F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe scripts\run_backend_tests.py core.test_qa_document_preview core.test_engineer_documents core.test_document_repair_regressions --verbosity 1
```

| Execution | Actual result |
| --- | --- |
| New independent package/HTTP/PDF checks | 10 passed in 3.543 seconds; zero failures/errors/skips; zero external attempts; 26 in-process HTTP fixture connections |
| Combined package/offline/PDF/OCR/independent checks | 63 passed in 8.586 seconds; zero failures/errors/skips; zero external attempts; 38 fixture connections |
| Protected document upload/preview/history regressions | 29 passed in 13.032 seconds; zero failures/errors/skips; zero external attempts; zero fixture connections |

The ten new checks overlap the 63-test execution. The combined selected modules
and 29 document regressions are independent executions of tests also eligible
for the full suite; do not add them to a full-suite count as extra unique tests.

The first combined run found an isolation problem in the reviewer's new HTTP
fixture: a preceding `StaticLiveServerTestCase` flush removed seeded industries.
The fixture now explicitly creates its synthetic industry when absent. The failed
receipt is retained. No product code or assertion was changed to conceal it.

Private receipts are under `.local/customer-server-20261031/qa`:
`independent-final.log`, `affected-final.log` (the fixture failure),
`affected-green.log`, and `document-affected-green.log`.

## Behaviors checked independently

- Runtime preparation leaves the immutable bundle byte inventory unchanged and
  copies neither the Django secret value nor external TLS keys into the package
  or runtime. References remain distinct from secret contents.
- An existing runtime and its database sentinel are refused and preserved.
  Missing image archives, absent draft acknowledgement and missing initialized
  storage fail before any Docker call or blind initialization.
- Replacing both an image archive and its local manifest still fails when checked
  against the separately trusted original manifest digest. This proves corruption/
  digest checking, not package authorship or resistance to replacement of the
  independent trust channel.
- Real SQLite/media backup restored into a new candidate preserves the human
  review value and original evidence bytes, leaving the verified backup inventory
  unchanged. No operational recovery or old-target overwrite was performed.
- A real authenticated HTTP request to saved company settings delivered the page
  and all critical linked assets from the same server, including a local stylesheet
  and JavaScript/font infrastructure. No automatic third-party resource URLs were
  present. This is a local HTTP fixture, not customer-LAN TLS acceptance.
- Actual local PDF conversion preserves source IDs/hashes and sends a real bounded
  page image to the controlled HTTP vision fixture. Image-only PDF OCR unavailability
  remains explicit in source findings/missing-information, with status `needs_review`.
  A digital-text PDF sends its extracted text and image without starting optional OCR.
- Authenticated document regressions exercised preserved originals, bounded PNG
  preview/cache, stale/corrupt previews, cross-project/revoked access, exact retained
  historical revisions, duplicate upload retry, save failure and human-review locks.

The reviewed package uses local image archives, `pull_policy: never`, explicit
no-pull/no-build operations and RFC1918 IPv4 listener validation. Actual native
Docker/Compose behavior is assigned to the separate Linux rehearsal; it was not
simulated into a success claim here. Draft markers and recorded approval holds
do not confer owner deployment approval.

## Independent native PDF/OCR smoke

Executed separately from ordinary tests:

```text
F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe .local\customer-server-20261031\qa\native_pdf_ocr.py
```

A newly generated raster-only PDF containing the single printed line
`HEIGHT 30 m` was actually converted by PDFium, then read by the already installed
RapidOCR/ONNX model bundle. Exact line matched. Conversion took **0.2605 seconds**,
OCR **1.9402 seconds**. PDF source bytes and all three installed model SHA256 values
were unchanged. Python network isolation recorded zero connection attempts;
ONNX telemetry opt-out was enabled before import. No model was downloaded, no
Ollama call occurred, and no paid service/API was called.

Receipt: `qa/native-pdf-ocr-receipt.json`; source/converted image:
`qa/independent-synthetic-scan.pdf` and `.png`. These are synthetic private samples.

This narrow passing smoke does **not** erase the previously recorded stricter
three-line benchmark: exact spacing matched only one of three lines, although
alphanumeric content matched three of three. Neither test validates handwriting,
Arabic, real-site labels, engineering measurements or compliance. OCR completion
means transcription finished, not that the reading is a verified answer.

## Offline/browser evidence cross-check

The reviewer read the offline agent's actual detailed receipts and restart proof,
verified all 34 vendored asset SHA256 values and matching recorded source hashes,
and visually inspected desktop/mobile QA screenshots. Reported browser counts are
68 operational assertions, with zero third-party requests; the separate retained
map component has six checks and initiates its deliberately failed online tile
requests only after the explicit action. These are the offline agent's browser
executions, **not a second independent execution of all 68 browser checks**.
The independent real HTTP asset exercise above is additional verification.

Useful screenshots:

- [Desktop QA](screenshots/customer-offline-20261031/offline-qa-linked-1366.png)
- [Mobile QA](screenshots/customer-offline-20261031/offline-qa-linked-390.png)
- [Enlarged viewer](screenshots/customer-offline-20261031/offline-qa-viewer.png)

## Reported context boundary gap — provisional Medium, unfixed

Most package Docker actions call `_docker`, which rejects inherited remote Docker
contexts. `run_action(..., 'create-owner')` launches its interactive Docker command
directly using `subprocess.run`, omitting that preflight. A bounded private probe
supplied a forbidden remote `DOCKER_HOST` and captured the subprocess call: the
interactive owner command was invoked without context inspection. **Docker was
not executed and no account was created.**

Evidence: `qa/context-boundary.log` and `qa/context-boundary-observation.json`.
Risk: an operator with an inherited remote context could target an unintended
daemon during owner provisioning, contrary to the documented local Unix-socket
boundary. Recommendation: share the local-context preflight with the interactive
operation while keeping the human password prompt uncaptured. This was reported
to the lead for separate AppSec disposition; the reviewer made no fix. Owner
approval is required before repairing review findings under repository rules.

## Service-offer and release limits

The service offer is explicitly a draft: it assigns supplier/customer/operator
responsibilities without granting a licence, setting a price/SLA or claiming a
customer deployment. The retained local PyMuPDF drawing dependency and broader
licence/redistribution decisions remain owner gates. Free local PDF/OCR components
do not resolve those obligations or imply universal handwriting accuracy.

Physical customer server/second-device access, trusted target DNS/TLS, target
backup/off-device restore, native vision accuracy, accepted capacity/cost and exact
owner release approval remain unverified. Actual Linux package rehearsal, final
full regression and separate security review must be reported independently.
All earlier A12/BR1/D1/D2/L1/CS1/CS2/AI1 holds remain. No merge or deployment was
performed, and this evidence does not approve one.
