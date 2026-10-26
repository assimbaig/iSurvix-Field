# Continuous, thin AI finding tables

26 October2026. Extends the compact QA workspace spacing work on
`feat/qa-photo-candidate-ranking-20261024`; no merge or production deployment.

## Result

AI details now uses one continuous semantic table for the selected photo.
Site/photo information appears first; every saved finding follows under its own
heading. The finding dropdown and completed-study finding pager are removed.
Photo-level navigation and the separate matching/category controls are preserved.
No original evidence, finding, answer or approval is edited by viewing the table.

Single-line cells measure19px on desktop and20px on mobile, versus34.546875px
before: padding is2px5px, line height14px/15px and text11.5px/12px. Long source
quotes and notes wrap fully rather than being clipped to that height. One shared
scrolling support area replaces switching individual findings; no per-finding
scroll panel was added. The larger source image remains beside the table.

The completed-study view uses the same continuous group format. It retains one
photo per page, original-source links, digest verification and existing project,
revision, QA-completion and client-release rules. Client rows include accepted,
linked information only. Values0/false remain visible. A recorded unit with no
readable value is explicitly retained without inventing a measurement.

## Implementation

- `backend/static/core/js/qa_evidence_review.js`: grouped current-photo findings,
  site context first, plain-text cells, no finding selector; matching unaffected.
- `backend/static/core/css/qa_evidence_review.css`: narrowly scoped thin rows.
- `backend/core/completed_ai_study.py` and its template/CSS: all findings in one
  protected read-only table, source-photo pagination retained.
- QA template and `base.html`: cache tokens only for the shared QA stylesheet
  reference, preventing an older cached duplicate from restoring large padding.
- Finding/controller and Django integration tests cover every group, no selector,
  zero/false/unit-only records, source quotes and client filtering.

The preceding header/progress/toolbar density changes remain in place; see
`QA_COMPACT_SPACE_20261026.md` and its67-check independent review. No additional
AI service, inference call, category-editing system or approval policy was added.

## Executed test and repair loop

Executed meaningful RED tests for the missing second visible finding, continuous
groups, unit/false/basis retention and removal of the selector, then implemented
and reran. The saved-study HTTP test initially showed only the first record;
it now renders both. A separate RED reproduced a missing unit-only record in the
read-only view; that field is now explicit with the value still Not recorded.
Literal question-mark separators in new headings/caption were corrected to
ASCII separators with regression assertions before final UI checks.

Final ordinary backend command:

```powershell
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' scripts/run_backend_tests.py --verbosity 1
```

**1,112 passed in412.492s**, no failures/errors/skips; isolated database/media/
model cache, zero external network attempts and33 in-process fixture connections.
All11 frontend `check-*.cjs` scripts pass from `frontend/`, including16 finding,
47 workspace,29 web-reference,58 guided-state and5 compact-layout assertions.
Django check, migration-drift check, pip check, JS syntax and the215-file static
build passed. Independent current-study9-test coverage also passed after the
unit-only repair.

The broad all-file fingerprint gate recorded a caption and its frontend-test
edit while server tests ran; its original failure/changed-file receipt is retained.
This was resolved by component verification, not suppressed: all server Python,
templates and CSS remained identical, all eleven final frontend scripts and
syntax ran after those two edits, and current source matches the recorded final
fingerprint. Component proof and exact commands/results are published in
`QA_CONTINUOUS_FINDINGS_ACCEPTANCE_20261026.json`.
Final fingerprint:
`b681339088ae1df384e6b568234f1ed37db7405b0997bf4d2b6246387c34267c`.
Private logs: `.local/qa-continuous-findings-20261026/final-delivery/`.

Independent saved-data browser checks:42 table/role/source assertions plus6 real
progress-refresh/scroll assertions. The right support scroll position remained
600px→600px during a clean refresh and769px→769px during the delayed response
after entering a draft; photo ID, source-content hash and reviewer input remained
intact. No model calls or mutation requests occurred. Before/after source captures
and further proof are in `INDEPENDENT_QA_CONTINUOUS_FINDINGS_20261026.md`.

Separate Agency AppSec found no new issue:7 private backend probes and7 frontend
security probes passed, including hostile group/unit/quote text, cross-photo/
revision access, two accepted client records with private proposals excluded,
and the retained WS1 protections. See
`SECURITY_REVIEW_CONTINUOUS_FINDINGS_20261026.md`. Existing separately held
findings were not changed or approved by this UI work.

## Review and limits

Use **http://127.0.0.1:8001/login/** and Ctrl+F5, then open a QA photo and AI
details, or its Completed AI study. Existing local credentials remain valid.
Only the feature web preview restarted; original8000, model11435 and in-flight
operational workers remain untouched. Long entries necessarily make the table
taller; preserving full evidence text is intentional. The view does not establish
native extraction accuracy or engineering compliance.

Recovery uses the archive/consistent SQLite backup at
`F:\iSurvix\iSurvix-Field\.local\backups\project-checkpoint-20261026-153841`,
supplemented by the final verified Git bundle. Final branch/remote SHA and saved
data receipt: `.local/qa-continuous-findings-20261026/delivery.json`.
