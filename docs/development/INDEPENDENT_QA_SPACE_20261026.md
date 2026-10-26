# Independent QA: compact QA workspace spacing

26 October2026. Installed Agency Test Automation Engineer and Reality Checker instructions applied. This report covers the spacing/navigation checkpoint after `ee082a2`; the later continuous-findings request requires separate QA and is not established by these results. This reviewer owns only isolated scripts, evidence, screenshots and this report, with no product changes.

## Result

**67 checks pass:**15 quantitative geometry assertions,3 toolbar assertions,47 actual saved-data browser flow assertions and2 additional1024px tablet assertions. Desktop targets are met; mobile limits are stated below. No native provider/model requests or customer writes were made.

The exact `ee082a2` static files and templates were saved with `git archive` and actually served for the before measurements. Current spacing source was separately served for after measurements. Both use the same disposable166-point/460-photo SQLite/media copy, same local asset policy and default appearance. The private evidence directory is `.local/qa-space-compact-20261026/`.

## Measured before and after

Measurements are CSS pixels from real Edge/Playwright DOM rectangles/computed styles. Font targets allow a0.70–0.80 after/before ratio for “about25%”; the measured primary fonts are exactly0.75. Height assertions allow1px rounding.

| Metric |1920x1080 before → after|1366x768 before → after|
|---|---:|---:|
| Three-stage progress group height|59.94 →14|65.44 →14|
| Residual progress height|23.36%|21.40%|
| Whole analysis/status area height|115.44 →28|148.33 →28|
| Residual whole status height|24.26%|18.88%|
| Workspace/tree/evidence top|354.67 →163.94|387.56 →163.94|
| Tree/evidence pane height|659 →862|360 →550|
| Checklist pane area gain|30.80%|52.78%|
| Evidence pane area gain|31.21%|53.60%|
| Actual checklist scroll viewport height|409 →637|110 →325|
| Actual evidence scroll viewport height|604 →819|305 →507|
| Checklist primary point font|12 →9|12 →9|
| Gallery filename font|11 →8.25|11 →8.25|
| Gallery toolbar height|87 →81|157 →81|

All three stage statuses and real source/saved-batch counts remain visible. The long explanations were preserved under existing Analysis details; they were not discarded to obtain the height reduction. All five existing QA primary links are directly visible: My reviews, Projects & sites, Overview, Review activity and Reports. Their project query is preserved, and an actual Projects & sites click reaches the scoped page.

The1024px tablet check passes without a special repair: document/header width remains1024px and navigation wraps internally into3+2 links; the rightmost tested link ends at930.42px. No clipped or inaccessible promoted link was found at1920,1366,1024 or390px.

## Red/green evidence and real behavior

`before-geometry-assertions.json` records the initial meaningful geometry failures:12 target assertions fail on the original measurements. The first implementation passed the space targets but retained12/11px body labels; four font assertions failed until the requested9/8.25px styles were applied. A separate toolbar regression caught nested16px labels and145.47px intermediate toolbar height; all three toolbar assertions subsequently pass at12px/81px. A mobile touch check measured a32px essential checklist opener; its scoped repair produces36px and the complete flow rerun passes. These were communicated to the frontend owner and repaired there, not by this reviewer.

Commands and actual receipts:

```powershell
node .local/qa-space-compact-20261026/measure.cjs after
node .local/qa-space-compact-20261026/accept_geometry.cjs after
node .local/qa-space-compact-20261026/accept_toolbar.cjs after
node .local/qa-space-compact-20261026/tablet.cjs tablet-final
node .local/qa-space-compact-20261026/flows.cjs
```

The47 flow assertions verify all five scoped links across three sizes; preserved Analysis details; real scoped project navigation; point search/selection; original-name photo search; honest empty results; next/previous gallery pages; checkbox selection; original photo viewer; source AI tables and multiple existing links; zoom; Escape/focus restoration; mobile drawer focus trapping/opener restoration; read-only Team Lead controls; and unchanged source/review/workflow state after all views.

The progress race uses only a controlled copied job's scalar state, never a worker: set analysing_evidence, open the source while clean, hold the actual progress GET, close the viewer, type an unsaved QA correction, advance the fixture counter37→38 and release the real request. The late response preserves both answer fields and editing focus. Routine polling deliberately skips dirty input; the test does not force an unsupported automatic overwrite. The copied job is restored to ready_for_review in cleanup. The first harness attempt lacked a fresh active context; it is retained as an exploratory harness issue rather than reported as an application failure.

The200% check uses equivalent reflow at683x384 CSS pixels with deviceScaleFactor2, corresponding to a1366x768 physical surface. It verifies horizontal fit, reachable checklist navigation and reachable source dialog/close control. This is not automation of the browser's native zoom-settings UI.

## Mobile and verification limits

At390x844, workspace top moves611.33→555.48px. The photo pane remains360px high; the hidden checklist remains an accessible drawer. Primary point/gallery text is13/12px and essential mobile checklist controls are36px. All five promoted links remain visible with wrapping. Horizontal overflow and modal clipping were not found. Mobile does **not** claim the desktop25% pane-area gain or quarter-height target: its stage group is43px versus87.19px and its whole status area132px versus192.08px; vertical scrolling is retained for readable controls and full content.

No browser mutation POST, model request or JavaScript exception occurred. The actual API still returns all166 approved IDs and460 photos, and review/source digests and workflow remain unchanged. `preservation-proof.json` independently verifies all460 original hashes/bytes, original photo rows and immutable revision snapshot/digest against the source disposable fixture. No real customer image/database was used for this review.

This reviewer did not repeat the backend suite for a styling-only change. The root agent owns the related47 backend tests, frontend checks, build and separate security review. Their results are not counted as independently executed here, and this report is not a production acceptance or native inference claim.

## Screenshots and cleanup

Six synthetic before/after screenshots were each visually inspected and copied to `docs/development/screenshots/qa-space-20261026/`: `before-1920.png`, `after-1920.png`, `before-1366.png`, `after-1366.png`, `before-390.png`, `after-390.png`. Before screenshots were recaptured from the exact archived baseline after visible thumbnails finished loading; their geometry matches the original baseline receipts. The private `zoom-200-equivalent.png` and tablet receipts provide supplementary responsive evidence.

Only the verified owned fixture on8921 is stopped for this checkpoint. Its command/PID, zero remaining listener and before/after protected8000/8001/11435 PIDs are saved in `.local/qa-space-compact-20261026/cleanup-receipt.json`. The subsequent continuous-findings work uses its own evidence directory and does not inherit these67 passes automatically.
