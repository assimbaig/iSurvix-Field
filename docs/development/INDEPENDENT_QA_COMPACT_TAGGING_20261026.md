# Independent QA: compact support and retained tagging

Reviewed with the installed Agency Test Automation Engineer and Reality Checker instructions. Initial scope is the compact photo support viewer, existing completed-result matching projection and active mapping visibility. The appendix separately records the subsequent hand-sketch follow-up. This review does not establish native inference accuracy or production readiness.

## Isolation and reproducible evidence

Private evidence: `.local/qa-compact-tagging-20261026/` in this candidate checkout. The controlled166-point/460-photo database/media were copied from the established disposable `.local/qa-site-compact-20261024` fixture; no operational survey database was opened for writes. This reviewer owns only scripts/evidence and this report, with no product changes. Loopback8921 serves the isolated fixture. Main8000 and model11435 are untouched. No inference or model-download request was made.

`seed_legacy.py` retains34 existing controlled findings and their exact approved schema, removes candidate metadata from only the copied result, persists retained source observations and sets its copied job ready_for_review. Existing synthetic human decisions are preserved. `active_fixture.py` additionally makes an `active.sqlite3` copy, removes only its copied final result and sets preparing_checklist/460 analysed sources; its publish action writes a declared controlled durable mapping with no model request. Original media are shared read-only by these two isolated databases.

`preservation-proof.json` verifies460 original files against both their recorded hashes and the original disposable fixture bytes. All original photo rows and the immutable revision snapshot/digest match the source fixture. No workflow approval was issued. Candidate metadata injected later by `seed_compact_candidates.py` is explicitly separated from the legacy regression and has an archived pre-injection payload; its two candidates support picker/panel UI testing.

## Meaningful before/after regressions

`true-before-support-{1920,1366,390}.png` use a private UI snapshot from commit9e849e6 and unchanged normal shared styles. At1366x768 the original support panel had scrollHeight615 versus clientHeight599. The final compact viewer has599/599 at the same size, and842/842 at1920x1080; its Matching content, candidate choice and action are directly visible. See `true-before-browser.json`, `final-browser.json` and `final-support-{1920,1366,390}.png`. Mobile remains vertically stacked with modal scrolling, while each selected support panel is compact and no horizontal overflow occurs.

The initial photo2 candidate expectation was excluded from the tagging diagnosis because its two links were already QA-confirmed. The independent regression instead uses photo10's substantive retained finding and still-unconfirmed civil_009 link. `legacy_red_green.py` executes the real isolated GET review endpoint with the exact prior9e849e6 state function, then current state code. Prior code returns unmatched/zero candidates despite that supported link; current code returns the exact approved civil_009 location and retained reason, without inventing a similarity score. `legacy-red-green.json` and `red-prior-saved-state.json` / `green-current-saved-state.json` contain the actual responses. The test requires the old assertion to fail and the current assertion to pass. This substantive finding is separate from the held M1 empty-observation security finding.

`legacy_regression.cjs` passes6 projection assertions: reproduced old omission, current valid location, absent invented score, preserved QA reassignment, unchanged acceptance/links from GET and stable original names/source digest. Existing QA reassignment of photo4 to electrical_001 does not resurrect its older civil_003 association.

## Independently executed checks

45 browser assertions pass, with JSON receipts written by the exact commands:

```powershell
node .local/qa-compact-tagging-20261026/capture.cjs final
node .local/qa-compact-tagging-20261026/tabs.cjs
node .local/qa-compact-tagging-20261026/guards.cjs
node .local/qa-compact-tagging-20261026/active.cjs
```

- Final capture10/10:166 points/460 originals,1920x1080,1366x768,390x844, contained compact support with no desktop panel scroll or page horizontal overflow, saved matching data and no JavaScript/model requests.
- Tabs20/20: one selected panel/candidate/finding at a time; both ranked alternatives and both retained findings reachable; Arrow/Home/End move tabs without navigating photos; actual delayed progress response preserves the AI tab and selected finding; all prior source links retained; zoom/Fit/Escape/trigger focus; candidate-save503 visible and retry persists only the link, without changing any answer acceptance; mobile AI/Links accessible; Team Lead sees only Links and no confirm control. Receipts: `tabs-browser.json`, `mobile-links.png`.
- Guards6/6: answer-save503 retains the draft, a real concurrent change produces stale-save protection with original saved answer retained, approved section disables matching mutations, Engineer QA-state GET403 and no JavaScript error. Receipts: `guards-browser.json`, `failure503-1366.png`, `approved-lock-1366.png`. Isolated lock removed in cleanup.
- Active9/9: preparing_checklist explicitly says Matching photos to checklist and460/460 evidence sources analysed without a100% final-completion claim; initially pending photo becomes civil_009 after controlled durable mapping is saved and source is reopened, before any final result exists; the reopened source triggers current full-state retrieval, retains extraction, and dirty-preview opening preserves the unsaved draft while skipping full reload; Escape restores focus. Receipt: `active-browser.json`, `active-durable-mapping-1366.png`.

The active command must run against `active_fixture.py serve`; all other browser commands use `fixture.py --serve --port 8921`. Exploratory harness waits were corrected to allow intentionally disappearing legacy candidate buttons after confirmation, and to compare stale-save state with the fixture's existing human decision rather than assuming a blank fixture. Those were harness/data assumptions; the final receipts above pass.

Focused deterministic backend verification independently executed:

```powershell
F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe scripts/run_backend_tests.py core.test_qa_matching_backend core.test_qa_matching_workspace --verbosity 1
```

43 tests passed in16.722s; zero external attempts and zero in-process HTTP-fixture connections. These include retained preview matching, active durable candidate projection before final result, uncertain/conflicting/unmatched suppression and existing QA mapping boundaries. Full-suite verification and separate adversarial AppSec are owned by the root agent. M1 and prior approval-held findings were not repaired by this review.

No remaining functional blocker was found within this scope. Desktop final1366 screenshot was visually inspected; results do not establish accuracy on operational evidence or sustained460-photo inference throughput.

## Appendix: independent hand-sketch follow-up

This additional review is separate from the45 support/tagging browser assertions. Read-only PDF inspection followed the installed PDF skill: the sample PDF was rendered with bundled Poppler and both pages were visually inspected, together with the original `sk-002.png`. Poppler emitted missing Symbol/ArialUnicode display-font notices but completed both page renders; the inspected sample labels and missing-dimension notes remain readable.

Independently ran:

```powershell
F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe scripts/run_backend_tests.py core.test_survey_sketch_integration --verbosity 2
```

Both integration tests pass in2.143s, zero external attempts or fixture connections. These tests exercise actual upload/submission/render/download endpoints, QA200 versus Client404, unchanged original sketch bytes, unreleased output and idempotent rendering. Ordinary reports are not treated as hand sketches.

`sketch_link.cjs` passes7 additional browser checks after refreshing the isolated server templates: actual More tools entry, correct `/local/survey-processing/<id>/#drawings` destination, actual200 navigation with Drawings tab visible, unchanged review/source digest and workflow state, no POST, no model request and no JavaScript exception. The protected processing page is existing functionality. Receipt: `sketch-link-browser.json`; screenshot: `sketches-drawings-link-1366.png`.

`inspect_sketch_pdf.py` passes5 output checks, corroborated visually: readable3500mm transcription with unverified/source reference and SHA256; red missing/unreadable measurement ledger; Draft For Review/Not to Scale/no measured engineering reconstruction; complete cleaned and colour-reference sides; unreleased manifest. Receipt: `sketch-pdf-inspection.json`. Original sample is `.local/sketch-drawing-review-20261026/revision-001/survey-drawings.pdf`; independent renders are `sketch-pdf-page-1.png` and `sketch-pdf-page-2.png` in the private QA evidence directory. No scale, missing measurement or approval was inferred from the traced pixels.

Independent functional consistency finding was reported to root: the earlier sampled register omitted SK-002 and said0 warnings, while the manifest contained the sketch and one warning. The implementation owner repaired the register with TDD. This reviewer independently verified the final artifact at `.local/sketch-register-review-20261026/revision-001/`: both the source `sv-001.png` and separately Poppler-rendered final PDF page1 visibly list SK-002, its source reference, one linked evidence reference and the current1-warning summary. The PDF/DXF manifest counts agree. Draft/Not to Scale/unreleased status remains explicit.

`inspect_final_register.py` passes4 final artifact assertions, saved as `final-sketch-register-inspection.json`; visual evidence is `final-sketch-register-pdf.png`. Independently ran the two register tests `core.test_survey_sketches.SurveySketchTests.test_register_lists_appended_sketch_and_current_warning_counts_in_both_exports` and `core.test_survey_sketches.SurveySketchTests.test_register_continues_all_rows_and_respects_total_sheet_bound` using the ordinary backend runner:2 passed in1.809s, zero external attempts/connections. This covers both exported register formats and continuation without omitted sheet rows. The reported functional finding is verified repaired; no remaining sketch-review blocker was found. This repair is separate from the approval-held security findings.

Final independent totals within this report are52 browser checks (45 support/tagging plus7 drawing-link checks),47 focused backend tests (43 matching plus2 sketch integration plus2 register),6 saved-projection assertions, and9 artifact assertions (5 initial sketch PDF plus4 final register). The exact prior/current retained-tag endpoint regression is recorded separately. The root agent owns full-suite and native evidence; these independent totals are not a substitute for that verification.
