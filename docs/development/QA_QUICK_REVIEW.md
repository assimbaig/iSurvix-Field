# QA quick-review redesign

23 October 2026. Improve the existing QA Engineer interface across its entry list,
site information, checklist/evidence categories and decision step. Keep the
application's existing roles, data, AI integration and engineering workflow.

Baseline: `e1792065f27b0f4755285a55a5f45343ef2ff2d0` on
`fix/engineer-general-information-20261023`. The working tree was clean before
editing. Its preceding source-stable full run passed948 tests; this is baseline
evidence, not the result for the redesign. Recovery archive
`.local/backups/project-checkpoint-20261023-233824` contains2,635 files and a
consistent SQLite backup; database integrity and ZIP CRC passed. One temporary
Office lock was excluded while the real workbook was preserved.

## Existing implementation and pain points

The real task explorer opens the category QA evidence workspace for applicable
saved records. It already supports confirmed/proposed links, photos, an enlarged
viewer, source information, answers, progress/retry and completion. The decision
link then opens a broad custom-checklist interface, and a workflow decision
redirects again to the activity page. Repeated navigation and simultaneous tools
make one review feel like several disconnected screens. The task explorer also
uses the general operational table rather than a focused QA entry list.

The approved references under `F:/iSurvix/references` control structure only:
compact header, category navigation, checklist list and an evidence area. Their
customer images, branding, site data and checklist text are not imported.

## Intended journey

My reviews opens the assigned site. The same workbench provides:

1. Site information: frozen Engineer-submitted information alongside the existing
   required General Info checklist review. Reading a source does not accept it.
2. Evidence review: category navigation, searchable checklist and photographic
   evidence, with one clear save/next action and contextual secondary tools.
3. Decision: existing QA completion and review-route controls, with current stage,
   missing requirements, rejection reasons and history. Rejection remains
   available when the existing workflow permits it, even before review is complete.

Matching, AI link confirmation, item review and engineering approval stay separate.
The decision uses existing server rules and POST endpoints. AI does not approve.
Reports, original downloads, history, reordering, AI details and recovery remain
available through secondary controls. Legacy workflows retain honest existing
fallbacks; no category pipeline is enabled by a layout change.

## Agency ownership

Installed UX Architect/Frontend Developer profiles own QA-specific markup,
styling, interactions, task-list presentation and navigation. Backend Architect
owns context, safe navigation after existing decisions and server regressions.
Independent Reality Checker/API Tester owns isolated saved-data browser journeys,
negative cases and desktop/mobile screenshots. The lead owns recovery,
requirements, integration checks, operational preservation and Git delivery.

## Requirements and evidence ledger

| Expected behavior | Implementation | Verification | Status |
| --- | --- | --- | --- |
| QA starts from a focused My reviews list; secondary features remain accessible | QA task-list/nav and existing scoped task route | Actual login/list/navigation, other-role regression | In progress |
| Search, project/status filters, sorting, paging and filtered-list return survive | Existing task explorer/return context | Persisted browser and HTTP/filter checks | In progress |
| Site information, evidence and decision share a clear guided workbench | Existing QA template/CSS/JS and view context | Desktop/mobile end-to-end navigation | In progress |
| General Info shows source data plus existing QA checklist answers without a new photo-upload bucket | Existing frozen data and answer controls | Reported versus accepted values, save/refresh/export boundaries | In progress |
| Civil/Electrical/Tower retain all required sections and stable IDs | Existing category/checklist state | Category/tree/search and zero-evidence point checks | In progress |
| Photos receive usable space, correct proportions and reliable enlarged browsing | Existing gallery/viewer | Real thumbnails, zoom/next/previous and selection restoration | In progress |
| Links can be assigned, confirmed, moved or removed by drag/drop and click/touch | Existing matching actions | Saved-data positive/negative API/browser cases | In progress |
| Not Assigned stays available and includes genuinely zero-link photos only | Existing evidence relationships | Multi-link counts, refresh, failed-save rollback | In progress |
| One clear save/next action preserves entered answers and requires explicit acceptance | Existing answer API and navigation | Dirty state, validation, cancellation, failed save and retry | In progress |
| Advanced AI details, retry/recovery, reordering, history and exports remain usable | Contextual tools/expanders | Action inventory and actual route checks | In progress |
| AI progress stays beside the real numerical count; pending/failed AI permits manual QA | Existing processing state/bar | Persisted pending/failed/active and mobile states | In progress |
| QA completes evidence review before permitted approval; incomplete work can still be rejected where allowed | Existing completion/review-route rules | Full/partial completion, approve and early-return scenarios | In progress |
| QA decision returns to an understandable site/queue outcome without another checklist editor | Existing workflow POST plus guarded return target | Success/rejection messages, stale and open-redirect negative tests | In progress |
| Rejection returns one step, preserves original photos and allows Engineer correction/resubmission | Existing workflow | Isolated QA-to-Engineer-to-QA scenario and source hashes | In progress |
| Client/Team Lead/Engineer/Admin behavior, historical records and approval locks remain intact | Existing server access/workflow | Role/project/record-lock and regression suites | In progress |
| Responsive layout, focus, keyboard navigation and error states remain usable | QA-specific UI | Actual desktop/mobile screenshots, DOM/console and keyboard checks | In progress |
| No operational inputs, originals, model settings or running AI jobs are reset by this UI change | Local checkpoint and existing workers | File hashes, database preservation and runtime inspection | In progress |
| Final current-source tests/checks and independent review pass | Existing test runner/check scripts | Native exits, source fingerprint and QA evidence | In progress |

Private test records, authentication and browser profiles live under
`.local/qa-quick-review-20261023`. Public screenshots must use clearly synthetic
data. Test success establishes the checked behavior, not universal software or
engineering accuracy.
