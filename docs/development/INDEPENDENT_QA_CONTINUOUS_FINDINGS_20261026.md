# Independent QA: continuous AI findings

26 October 2026. Reviewed with the installed Agency Test Automation Engineer and Reality Checker instructions. This covers the new continuous-findings presentation; the earlier 67 spacing passes and older one-finding tests are not substituted for this review. This reviewer made no product edits.

**48 live-browser assertions and4 quantitative table assertions pass.** The48 comprise42 source/role/content checks plus6 actual progress/reading-position checks. Existing29 web-reference/WS1 frontend assertions were also independently rerun and passed; they are not added to the new browser total. No native provider, Ollama or customer-database write occurred.

## Before/after and provenance

Pre-change QA JavaScript/CSS, all templates and the completed-study helper were copied before implementation. Exact hashes are retained in `.local/qa-continuous-findings-20261026/baseline-source-hashes.json`. The baseline was actually served, including its old helper/template, against the same disposable166-point/460-photo database/media copy. It displayed only one of two saved findings with a finding dropdown. Both1366x768 and390x844 before assertions correctly failed the new all-findings/no-selector requirement.

Current source renders one semantic table with site/photo context first and all saved findings in individually headed row groups. The original two-finding source shows both groups without a selector. A separate declared three-observation fixture tests zero, false, missing numerical value with recorded unit, complete long notes, literal HTML-like quote text and unchanged Matching alternatives. No actual source image or immutable source revision was modified to create those observations.

| Actual simple value row | Before | After | Reduction |
|---|---:|---:|---:|
|1366x768|34.546875px|19px|45.00%|
|390x844|34.546875px|20px|42.11%|

Before cells computed13px font with17.55px line height and8px10px padding. Final desktop cells compute11.5px/14px with2px5px padding; mobile computes12px/15px with the same padding. Final captures include the current ASCII caption separator ` - ` and group separator ` / `. Long or wrapped content naturally occupies more than one line; this is not a claim that every observation fits simultaneously inside a phone viewport.

## Executed checks

Private scripts and actual JSON receipts are under `.local/qa-continuous-findings-20261026/`:

```powershell
node .local/qa-continuous-findings-20261026/checks.cjs
node .local/qa-continuous-findings-20261026/scroll.cjs
node .local/qa-continuous-findings-20261026/capture.cjs after
node .local/qa-continuous-findings-20261026/accept.cjs after
node frontend/check-web-references.cjs
```

`continuous-checks.json`:42/42. At1920,1366 and390px there is one table, context is first, all three observation groups remain rendered, heading cells use row-group semantics and no observation dropdown exists. Actual0A and false values survive; a unit-only mm record retains its unit without inventing0mm. Full notes, quotes, basis, checklist hints and uncertainty remain available. Test note comparison ignores only its fixture's trailing whitespace, not words or quote content. HTML/script-like saved text stays text, creates no executable node and does not run. No horizontal overflow or automatic public-query fill occurs.

The independent Matching candidate dropdown still contains its two declared saved alternatives and selection works. This is separate from removal of the findings dropdown. Engineer, assigned QA, Team Lead and scoped Admin completed studies use the same continuous three-finding read-only format; none has a finding pager or mutation form. Old `finding=2` links do not hide the other observations. Client unreleased access remains404, foreign-project access remains denied and the Team Lead QA viewer still hides its private AI panel. Source/review digests and workflow state remain unchanged after views.

`scroll-progress.json`:6/6. A controlled copied job uses analysing_evidence with scalar counters; no worker/model runs. The application itself makes its real scheduled progress GET for the selected source. After advancing37→38, desktop right-pane reading position stays **600→600px**, the exact source-content hash and photo stay unchanged. For a second real in-flight request, the viewer is closed, a QA draft is typed, the same source is reopened and scrolled, then the actual39-counter response is released. Reading position stays **769→769px**; the unsaved result and remarks, selected source and all three finding groups survive. Three actual progress responses return200 and no JavaScript error occurs. The copied job is restored to ready_for_review in cleanup.

`after-table-assertions.json`:4/4. Both saved observations are present without a picker and every measured simple value row is thinner than the archived baseline, at both tested table widths. `before-table-geometry.json` contains the meaningful two-case red evidence. Final screenshots were refreshed after the caption correction.

The root agent owns the final backend suite, implementation unit tests and separate security review. Those results are not claimed as independently executed by this reviewer. The positive released-Client policy remains narrower than internal raw observations; this browser fixture verifies unreleased denial and does not simulate operational approvals. No earlier held finding was remediated or implicitly approved by this work.

## Preservation, screenshots and cleanup

`preservation-proof.json` rehashes all460 original files and confirms their recorded SHA256, bytes and original photo rows still match the source disposable fixture. The immutable source snapshot/digest is also unchanged. Synthetic analyses and a documented two-candidate setup exist only in this isolated copy; no actual source bytes or human decision were overwritten.

Six sanitized screenshots were visually inspected and copied to `docs/development/screenshots/qa-continuous-findings-20261026/`: before/after table captures at1366 and390px, and before/after1366px source-viewer captures. Component captures show the complete continuous table; the viewport capture demonstrates the source image remains beside it. Mobile uses normal vertical scrolling for long content. No customer source was copied into documentation.

Only the verified owned8921 fixture is stopped. Its command/PID, zero remaining listener and protected8000/8001/11435 before/after PIDs are recorded in `.local/qa-continuous-findings-20261026/cleanup-receipt.json`. No remaining functional blocker was found within this presentation scope; these results do not certify model accuracy, engineering approval or production readiness.
