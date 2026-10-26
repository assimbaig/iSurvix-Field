# Separate AppSec review: gallery headings, availability and header

26 October 2026. Branch `feat/qa-view-panel-header-20261026`. This AppSec phase
began **after** functional source freeze and the independent responsive gallery,
hidden-pool and authenticated header checks. Used the installed Agency AppSec
profile and owner rules. Implementation remained read-only; only private probes,
screenshots and new review reports were written.

**No new exploitable vulnerability or security finding was established. No
security fix was performed.** C1/M1/W1/S1/S2/S3/R1/R2 remain held pending their
own owner approval. Earlier explicitly approved G1 and WS1 closures are retained;
this task does not authorize broader remediation or deployment.

## Independently executed attacks

Private command: `node .local/qa-gallery-groups-20261026/security_probes.cjs`.
**11/11 assertions passed**, native exit0 (`security-probes-final.json`):

- New group/checkpoint headings render hostile HTML-like metadata as literal
  text, without injected child elements. A controlled HTTP-response injection
  was then tested in the actual browser: `<img src=x onerror=...>` remained text
  in both h3/h4, created zero image elements and executed no event handler.
- Foreign photo references produce no gallery cards or inflated unique counts;
  displaying links/headings never changes an unaccepted answer into approval.
- Immediate unlinked image nodes retain same-origin URL filtering; injected
  external preview URLs do not become image requests. Rendering sends no native
  model or matching mutation request.
- Actual authorized preview GET returned200. A foreign photo ID and wrong task
  ID returned404. An actual matching request without CSRF returned403, without
  changing a source/link. Engineer and Client requests for private QA state were
  denied403/404.

The first unit probe mistakenly matched every node with the hostile label,
including an existing link row with legitimate action-button children. It did
not establish XSS. The selector was narrowed to the new h3/h4 nodes and the
actual-browser injection above independently confirmed literal rendering. No
product change was made to resolve that test-harness assumption.

Ten existing independent G1/general-gallery probes also passed
(`security-existing-probes.json`), covering mapping-only suppression versus real
human blanks, source zero/false, dirty/read-only guards, scoped photo IDs and lazy
loading. The expanded WS1 reattack passed31 unsafe URL forms, retained five public
URLs and passed both unsafe-anchor cases (`security-ws1-expanded.json`). These are
existing probes, not new unique acceptance tests.

## Boundary assessment

The changed production files are QA JS/templates/CSS and shared header CSS/cache
tokens. No backend role, project, revision, original-download, mutation-CSRF or
engineering-approval predicate changed. The removed viewing-panel button was
relocated to More tools with the same action/permissions; displaying a gallery
badge, heading or `Not available` does not accept an answer. New headings use
text-node construction and dataset properties, without HTML parsing/evaluation.

The separate functional evidence is in
`INDEPENDENT_QA_VIEW_PANEL_HEADER_20261026.md`:46 responsive gallery checks,
5 hidden-pool checks and287 authenticated header checks/56 visits. That phase
was completed first and is not relabelled as a separate penetration-test campaign.

All HTTP tests used private consistent synthetic SQLite/media copies on
loopback8925. The missing-CSRF POST was an intentional negative test against that
copy only. No operational records, model services or native inference were used.
The owned server is stopped; source hashes, model-block receipt and cleanup are
under `.local/qa-gallery-groups-20261026`. Public screenshots are sanitized
synthetic data under `docs/development/screenshots/qa-view-panel-header-20261026`.

No fresh dependency audit, DNS-rebinding campaign, large-file stress test or
production assessment was performed. No guarantee beyond the measured scope is
implied, and all earlier approval holds remain unchanged.
