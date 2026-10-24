# Separate AppSec review: QA workspace redesign

24 October 2026. Branch `feat/qa-review-workspace-20261024`, changes after
`03b5eed`. The installed Agency Application Security Engineer profile,
`AGENTS.md`, current handoff and `QA_REVIEW_REDESIGN_REQUIREMENTS_20261024.md`
were read. Production implementation and ordinary tests remained read-only.
Only this report and private disposable probes were written. Operational data,
existing QA fixtures/services, approvals and native AI were not touched.

No new Critical/High/Medium exploitable issue was established by this focused
review. One Low private-storage integrity observation is recorded. **No finding
was fixed; owner approval is required before remediation.** This is not a
production security certificate.

## Executed evidence

```powershell
.local\venv\Scripts\python.exe .local\security-qa-workspace-20261024\run_audit.py
```

**5 adversarial probe tests completed in3.915s, zero failures/errors/skips,
zero external connections and zero model calls**, using the ordinary runner's
temporary database/media/cache isolation. One test deliberately asserts the
finding below to retain an executable reproduction; a green probe suite does
not mean every security expectation passed.

Artifacts: `.local/security-qa-workspace-20261024/audit_workspace.py`,
`adversarial-tests.log` and `observations.json`. These contain synthetic evidence
only. No competing browser debugger was opened.

## W1 — Low: existing PDF raster cache bytes are not integrity-checked

Location: `backend/core/engineer_documents.py`, `_pdf_raster()`, lines186–211.

The endpoint correctly authorizes the task/document/revision and rechecks the
original PDF SHA before serving even a cached preview. However, when its expected
PNG cache path already exists, the derivative bytes are opened without a hash or
image-content check.

Reproduction in isolated media: render the authorized PDF once; replace that
private cached PNG with a different valid PNG; request the same preview again.
Actual result:200 with the replacement image, while the original PDF remains
byte-identical. The server retains `image/png`, `nosniff` and private/no-store
headers. Corrupting the original PDF instead correctly returns409, even when
the cached PNG exists.

This **requires private-storage write access or an out-of-band storage fault**.
No upload path to write the derivative filename, cross-project route or remote
cache-poisoning exploit was found. It can nevertheless display altered technical
evidence to an authorized reviewer without detecting derivative corruption.

Recommendation: store a trusted derivative hash/manifest bound to document hash,
page and renderer version; validate it before serving, and regenerate or reject
a mismatch while retaining the original. Keep writes atomic if implementing
concurrent generation. Add a cached-derivative corruption regression. **Fix is
approval-pending.**

## Boundaries independently checked

- Unassigned QA and Client preview requests are404, anonymous requests redirect
  to login, and the rasterizer is not called for those requests.
- Nine malformed/out-of-range page variants are404. A revision not containing
  the document and a nonexistent revision cannot expose the source.
- Original PDF bytes remain unchanged across normal, invalid-page and corrupted
  derivative requests; altered original bytes fail their existing SHA check.
- Metadata projection excludes private keys and invalid Boolean GPS values,
  preserves the immutable input, and leaves textual metadata as untrusted text.
- Static review found checklist groups projected from saved structured fields,
  existing server lock state exposed to the UI, and existing action authorization
  and stale-digest checks retained. Template identity is resolved from the saved
  revision rather than an arbitrary request parameter.
- Changed UI labels, remarks and metadata use text nodes; source URLs have
  same-origin checks. Document preview accepts JPEG/PNG/WebP responses into an
  image element and rejects non-image responses. This does not claim a separate
  browser-based XSS campaign or active-PDF execution test.
- Save sequencing clears dirty state only after a confirmed saved-state response;
  new-source/revision drafts remain blocked, and stale review reconciliation
  requires explicit acknowledgment. This was a source review; independent QA's
  actual dirty/save browser tests remain separate evidence.

## Earlier findings and limits

S1 Medium, S2/S3 Low and R1/R2 Low remain **unfixed and approval-pending** in
`SECURITY_REVIEW_QA_DOCUMENTS_PAUSE_20261024.md` and
`SECURITY_REVIEW_QA_REFINEMENT_20261024.md`. Their existing hardening observations
also remain open. Image-only in-app preview does not remove active content from
downloaded PDF originals and is not approval to remediate that older policy item.

No production Nginx/VPS, dependency-advisory, native-model, physical-device or
parallel-render stress audit was performed here. The root/QA owners' full suite
and browser evidence must be reported separately. No claim of universal security
or bug freedom is made.

## Closing JavaScript-only review

The final functional corrections were inspected read-only: the bulk-Move button
and handler now share the same edit/dirty/source-lock guard; a failed attempt to
open a Move dialog stops before using its state. Viewer focus restoration retains
the original numeric photo trigger instead of the subsequently viewed photo.
These paths add no endpoint, URL source or authorization rule. Existing same-origin
URL checks, CSRF mutation headers and server revision/lock enforcement remain.
No additional security regression was identified in these narrow changes. This
closing check was source inspection only, with no new broad tests or model calls;
functional browser/unit retests are recorded by QA. W1 and all earlier findings
remain unchanged and approval-pending.
