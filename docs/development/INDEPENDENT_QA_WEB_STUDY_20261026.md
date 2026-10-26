# Independent QA: public references, findings, phases and completed study

26 October2026. Reviewed with the installed Agency Test Automation Engineer and Reality Checker instructions. This report covers the new features and the explicitly owner-approved WS1 repair. Earlier52-browser/1085-suite results are not evidence for these additions. No product files were edited by this reviewer.

## Results and evidence

**155 distinct browser assertions,9 actual HTTP guard assertions and29 focused backend tests pass.** The155 browser assertions comprise118 initial feature checks,33 WS1 checks and4 final actual-schema defect checks. Repeated native/capture checks are counted once. This is functional evidence, not a production-security certification.

All private scripts, actual JSON receipts and screenshots are under `.local/qa-web-references-20261026/` in the candidate checkout. The controlled database/media were copied from the established disposable166-point/460-photo fixture. Additional source observations and other-project/unassigned QA actors are explicitly synthetic. The separate `active.sqlite3` copy has no final processing result and permits deterministic phase-transition tests without running a worker.

`preservation-proof.json` independently rehashes all460 originals: each matches its recorded SHA256 and the source disposable fixture bytes. Original photo rows and the immutable revision snapshot/digest remain unchanged. Browser read/navigation and web lookup checks compare saved review/source digests, links, acceptance and workflow before/after; no automatic answer acceptance or approval occurred. No customer database/source was modified and no Ollama request was made.

| Check | Passing assertions | Actual receipt |
| --- | ---: | --- |
| Native Wikipedia through authorized Django endpoint and actual browser |10|`native-endpoint-browser.json`|
| Controlled web form/error/loading/empty/retry/stale-photo/draft behavior |29|`controlled-browser.json`|
| Saved context/finding tables and ready-state phases, three sizes |24|`table-phases-browser.json`|
| Four-role completed study, three sizes, paging/original hash/authorization |45|`completed-study-browser.json`|
| Active source-analysis/matching phases and honest incomplete study |10|`active-phases-browser.json`|
| Approved WS1 service/DOM/actual-click regression cases |33|`ws1-browser-retest.json`|
| Actual-schema defect versus non-defect display in QA and study |4|`actual-schema-defect-browser.json`|
| Additional actual endpoint guards |9|`access-endpoint.json`|

The browser scripts run with installed Playwright/Edge at1920x1080,1366x768 and390x844. Third-party page assets are blocked; the product's own local assets remain active. Explicitly synthetic browser/provider responses are identified below and in their receipts.

## Native public reference proof

After restarting the owned isolated server with current WS1 code, the assigned QA user explicitly typed **microwave antenna** into the initially blank Wikipedia form. Actual POST `/local/photos/5/capture/review/web-references/` returned200,1776 response bytes in1014ms. The receipt preserves its SHA256, returned article citations and provider retrieval timestamp. Requests used native TLS; this proof did not mock provider data. The final screenshot visibly shows the public citations and unverified/retrieved notice.

The request contained only query/provider and the current revision/source guards. Site IDs, coordinates, source filenames, photos, extracted findings and private draft remarks were not automatically transmitted to the provider. Wikipedia is correctly described as an encyclopedia reference source; results remain separate from saved site evidence and engineering decisions.

The actual unconfigured Brave request returns503/not_configured with the exact blocker: an **owner-provided Brave Search API key is required**. The UI clears old citations, retains the query and offers Retry lookup. No account, paid signup or real Brave credential was created. Native full-web Brave operation is therefore not verified.

`browser.cjs` explicitly intercepts only the lookup response to test loading, duplicate-click suppression, success,503,429, empty results, malformed success, retry and delayed old-photo responses. It verifies no automatic lookup/autofill, only explicit public-query fields, preserved unsaved private QA correction, reset/abort on photo navigation, safe citation attributes, Team Lead hiding and no JavaScript exception. These controlled results are not native provider proof.

`access.cjs` uses actual HTTP requests with real copied-fixture sessions: missing CSRF403, GET405, stale revision/digest409, extra private-context/control-character/oversize requests400, foreign-project QA404 and same-project unassigned QA404. These denied requests do not require provider access. Backend tests additionally cover revoked project membership and current source guards before cached responses.

## Findings, phases and completed study

Actual saved source tables show Site ID, photo identity and upload category; absent capture time/GPS explicitly say Not recorded. A declared synthetic equipment record exercises manufacturer, model, defect,48VDC, description, source quote, uncertainty and confidence. The public lookup query stays blank despite those values. Both retained observations remain available in the one-at-a-time picker.

The final actual Observation-schema regression uses `category=defect`, `component`, `value`, `notes` and `evidence_quote`, rather than assuming a nonexistent `defects` key. Its defect note is shown in the Defect/issue row in both QA and completed-study tables. An equipment-category descriptive note remains Not recorded in that row, preventing an invented defect.

Active tests show that460/460 source counters alone still say Processing before the observed analysis boundary. Preparing checklist makes Analysis/Findings complete while Checklist tagging continues with the actual0, then1 durable saved mapping batch and an explicitly unknown total. Findings share source analysis and have no invented independent fraction/job. Lightweight and full-state phase projections agree. A completed stage with unknown denominator has no indefinite processing bar. The study route honestly says not complete before the ready boundary.

Engineer, assigned QA, Team Lead and scoped Admin receive the same read-only completed-study main content at all three sizes: one protected original photo and one paged finding. Finding/photo navigation works; the HTTP original's hash matches the recorded immutable original. No study mutation form or browser POST appears. Foreign users and anonymous sessions remain denied/redirected.

**Client scope is narrower:** the actual browser receives404 for unreleased private observations. The positive released Client path is verified by isolated backend integration tests and shows only accepted, linked, current QA-reviewed information under the matching released review signature. This report does not claim that Client receives all internal raw AI observations.

At1366, a richly populated observation and expanded reference results can require vertical support-panel scrolling while the source photo stays visible. Mobile stacks image and details with vertical modal/page scrolling. No horizontal overflow was found; this report does not claim that every field/result fits simultaneously within a mobile viewport.

## Owner-approved WS1 retest

After explicit owner approval, implementation agents repaired the canonical-link issue. This reviewer made no product repair. The following five inputs were independently retested:

```text
http://127.1/private
http://2130706433/private
http://0x7f000001/private
http://%31%32%37.0.0.1/private
http://localhost./private
```

`ws1_fixture.py` replaces only the provider HTTP response inside the owned isolated process, using a declared synthetic Brave token and fixture records; no real provider request/key is used. The actual authorized Django endpoint still executes its service, validation and result filtering. For every input it removes the unsafe result while retaining a legitimate Wikipedia URL.

`ws1.cjs` separately injects raw legacy/untrusted successful lookup responses containing each unsafe URL, bypassing the repaired backend to exercise the final browser filter. In all five cases the actual DOM retains only the public Wikipedia anchor. It performs ten real browser clicks across service and legacy cases; each opens the retained public URL in a new page, with that external navigation intercepted as declared synthetic content. No loopback/private or local-AI request occurs. Provider-call records and actual response/DOM/click receipts are saved privately. This establishes the reported WS1 cases are repaired; it is not a DNS-rebinding or multi-process deployment guarantee. No other held finding was repaired or implicitly approved by this review.

## Independently executed focused checks

```powershell
F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe scripts/run_backend_tests.py core.test_web_references core.test_qa_review_progress core.test_completed_ai_study --verbosity 1
node frontend/check-web-references.cjs
node frontend/check-qa-finding-table.cjs
```

Final backend run: **29 passed in4.638s**, zero external attempts and zero in-process HTTP-fixture connections. This includes13 reference tests,9 phase tests and7 completed-study tests. Independently reran frontend behavior checks:29 web-reference assertions and12 finding/phase assertions passed. These overlap feature behavior and are not added to the browser total. The root agent owns the final full-suite/build and separate AppSec report; this reviewer did not claim another agent's full-suite result as independently run.

No remaining functional blocker was found in this scope. All receipts use explicitly synthetic site evidence. Native provider proof concerns public reference lookup only, not model extraction, installation verification or engineering approval.

## Reviewed screenshots and cleanup

Five sanitized screenshots were each visually inspected and copied to `docs/development/screenshots/qa-web-study-20261026/`:

- `native-wikipedia-1366.png`: actual public Wikipedia citations/retrieved notice beside synthetic source image.
- `finding-context-1920.png`, `finding-context-1366.png`, `finding-context-390.png`: recorded context, equipment fields and responsive layout.
- `completed-study-qa-1366.png`: paged read-only source study.

No real customer screenshot or original evidence was copied into documentation. Private raw receipts and test databases remain under the project F: checkout. Owned8921 shutdown verification and before/after protected-service PIDs are saved in `.local/qa-web-references-20261026/cleanup-receipt.json`; main8000, review8001 and model11435 are excluded from cleanup.
