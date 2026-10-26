# Compact QA navigation, progress and evidence workspace

26 October2026. Extends `ee082a2` on the existing feature branch
`feat/qa-photo-candidate-ranking-20261024`; no production merge or deployment.

## Implemented

- Existing My reviews, Projects & sites, Overview, Review activity and Reports
  links appear directly in the compact desktop header for the QA workspace.
  The same URLs, project context and server role checks remain in use. Other
  pages retain their existing navigation; shared base layout is unchanged.
- Three phase indicators share one14px line inside a28px status strip. States
  and recorded counts remain visible. Long explanations and manual-review
  guidance move to the existing Analysis details disclosure. Unknown totals
  remain unknown; no new background phase or approval state is invented.
- Checklist and evidence panes move upward. Desktop primary point labels go
  from12px to9px; photo captions from11px to8.25px: the requested25% reduction.
  Mobile retains13px/12px labels and larger touch controls. Evidence toolbar
  and review-filter labels reduce from16px to12px with aligned controls.
- Existing checklist navigation, hierarchy, filtering, source selection,
  evidence viewer, review controls and footer remain connected to saved data.
  No backend service, database schema, approval policy or inference code changes.

## Measured baseline versus candidate

Independent QA serves the exact `ee082a2` assets/templates as the baseline and
uses the same isolated166-point/460-photo records for both captures.

| Measurement |1920x1080 before → after|1366x768 before → after|
|---|---|---|
| Three-phase group height |59.94 →14px|65.44 →14px|
| Whole status panel height |115.44 →28px|148.33 →28px|
| Workspace top |354.67 →163.94px|387.56 →163.94px|
| Checklist/evidence height |659 →862px (+30.8%)|360 →550px (+52.8%)|
| Checklist primary label |12 →9px|12 →9px|
| Photo caption |11 →8.25px|11 →8.25px|

Thus the phase group occupies23.36%/21.40% of its previous height; the complete
status panel occupies24.26%/18.88%. Checklist width remains unchanged. Evidence
area gains are31.2%/53.6% including its small width gain. The later toolbar
refinement reduces its1366 height to81px from157px. Mobile adapts rather than
shrinking labels to desktop density: its workspace starts at555.48px versus
611.33px previously, retains its360px
pane/drawer arrangement and has no page-wide horizontal overflow.

## Verification

Executed meaningful failing controller and measured geometry tests before
implementation, including a separate toolbar regression after visual inspection
found nested16px labels missed by the initial CSS. The final controller compact
suite passes5/5; geometry passes15/15; toolbar assertions pass3/3.

Related backend integration/permission checks:

```powershell
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' scripts/run_backend_tests.py core.test_qa_matching_workspace core.test_qa_review_progress_routes core.test_qa_review_progress core.test_pause_functional_review core.test_completed_ai_study --verbosity 1
```

47 tests passed in15.018s after the mobile touch fix, isolated database/media/cache and zero network
attempts. All11 frontend `check-*.cjs` scripts pass when run from `frontend/`.
Django check, migration-drift check, dependency check, JS syntax and the215-file
static asset build passed. Source remained unchanged throughout this final
targeted run; fingerprint:
`7afb262feb39757347fcf5c5eda7089338b676c1b476d4d8f654bf773e90e890`.
Exact commands and logs: `.local/qa-space-compact-20261026/root-checks/receipt.json`.
The earlier1,110-test backend suite is a baseline; it was not rerun or relabelled
as current verification for this frontend-only change.

Independent browser QA passed67 checks:15 geometry,3 toolbar,47 saved-data
flows and2 tablet checks. A mobile navigation control was reproduced at32px,
then repaired to36px; all affected checks passed afterward. The progress-refresh
race preserved unsaved input and viewer focus. Browser interactions and screenshots
are documented separately in `INDEPENDENT_QA_SPACE_20261026.md`.
The subsequent continuous-findings request has its own tests/report and is not
claimed by this earlier spacing fingerprint. Separate AppSec found no new issue in this
narrow change; it checked phase-text escaping, readonly controls, preserved
CSRF/WS1 protections and promoted navigation URLs/role scope. Its final addendum
includes three actual Django template checks for hostile parameter values and
unchanged non-QA navigation. See `SECURITY_REVIEW_QA_SPACE_20261026.md`. Older
recorded findings remain subject to their existing approval holds.

## Local review and recovery

Test at **http://127.0.0.1:8001/login/**, then reload the QA review page. Both CSS
and JS cache tokens changed. Original8000 and model11435 are preserved; only the
feature web preview restarted. No Ollama inference, operational approval or
customer-evidence mutation was performed by this change.

Recovery archive/consistent SQLite snapshot:
`F:\iSurvix\iSurvix-Field\.local\backups\project-checkpoint-20261026-153841`.
The final Git bundle supplements the archive for the exact committed UI source.
The final branch/remote SHA and recovery receipt are kept privately at
`.local/qa-space-compact-20261026/delivery.json`.
