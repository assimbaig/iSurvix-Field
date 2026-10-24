# Owner requirements: Site Review / QA workspace

24 October 2026. This records the expanded owner instruction. It supersedes the
two-pane review layout while retaining the compact Site Information work already
in progress. No new screenshots were attached to this message; inspect the
previously supplied local layout references in `F:\iSurvix\references`.

TASK: Redesign the iField Site Review / QA Review workspace using the attached reference.

SCREENSHOTS
1. First screenshot: current iField interface.
2. Second screenshot: reference interface whose layout and evidence-review interaction I want to follow.

Implement the redesign in the actual application. Do not stop at a proposal, mockup, or partial implementation.

Use the reference for layout hierarchy, compact checklist navigation, evidence grouping, and efficient review. Retain iField branding and existing application navigation. Do not copy Huawei/ISDP branding, logos, proprietary text, or unrelated menus.

PRIMARY OUTCOME
An engineer or QA reviewer must be able to:
- Find a checklist point quickly.
- Immediately see its linked photos and documents.
- Inspect evidence at a useful size.
- Enter a result and remarks without losing sight of the evidence.
- Identify missing, unassigned, suggested, and confirmed evidence.
- Save and move to the next point reliably.
- Continue reviewing while AI is processing.

SCOPE
Apply this redesign to the Site Review / QA evidence-review workspace and its directly related components.
Preserve existing workflows, approved checklist templates, role permissions, submission revisions, saved answers, evidence associations, and audit history.
Do not redesign unrelated modules.
Do not change authorization rules or approval policy as part of this visual redesign.

## 1. Inspect the application first

Before editing:
- Read AGENTS.md and relevant repository instructions.
- Identify the route, page components, styling system, API endpoints, state management, and tests used by this workspace.
- Trace checklist loading, evidence loading, photo assignment, review saving, AI status, and final decisions.
- Identify existing reusable tree, gallery, drawer, dialog, and toolbar components.
- Inspect existing Agency Agents definitions if available.

Use relevant Agency Agents for frontend implementation, UX/accessibility review, and QA/testing if supported in this environment. Give each agent a concrete scope and avoid conflicting edits. If the agent framework is unavailable, state that clearly and perform the work directly.

Do not invent backend capabilities, API responses, counts, or successful test results.

## 2. Required desktop layout

Use the available viewport efficiently:
A. Existing application header/navigation
B. Compact site identity and workflow strip
C. Compact review summary and AI status
D. Main workspace:
- Left: checklist tree
- Centre: evidence gallery and document sections
- Right: review panel
E. Compact save/navigation controls

Suggested desktop proportions:
- Left tree: approximately 250–280 px.
- Centre: flexible, largest area.
- Right review panel: approximately 300–340 px.

These are starting values, not rigid dimensions. Adapt them to the real application shell and viewport.
At smaller desktop widths, allow the review panel to become a drawer or collapsible panel so the evidence remains usable.
Do not squeeze all three columns into unreadable widths.

Avoid excessive blank space, large purple blocks, oversized fields, and stacked banners.
Use restrained colours, thin borders, clear labels, and consistent compact spacing.
Retain readable text; do not copy the reference’s tiny text or excessive truncation.

## 3. Compact site header

Show real data where available:
- Site ID and site name.
- Project.
- Submission revision.
- Workflow status.
- Assigned reviewer or task owner, if supported.

Keep “Back to my reviews” accessible.
Move secondary actions into “More tools.”
Do not fabricate missing metadata.
Retain access to Site information, Review evidence, Decision.
Replace the large coloured step bars with compact tabs or a small step indicator.
Preserve workflow restrictions on the Decision step.

## 4. Review summary and AI status

Replace the current large AI analysis block with a compact status row containing:
- Actual AI state.
- Processed / total eligible evidence.
- Progress percentage, when the denominator is valid.
- Appropriate Pause / Resume control.
- Refresh only if still needed.
- Expandable details.

Expanded details can show submitted photos; unique assigned photos; unique unassigned photos; suggested links; confirmed links; failures and retries, if available.

Define counters precisely:
- Photo counts and link counts are different.
- A photo linked to multiple points must not inflate unique-photo totals.
- Distinguish current-point counts from submission-wide counts.
- Never show zero for an unknown or still-loading value.

The current screenshot appears to show conflicting assignment information. Investigate the scope and source of each counter and correct misleading labels or calculations with focused tests.

AI must not block manual review. Preserve checklist visibility during analysis wherever supported.
If the current backend delays generated content until analysis finishes, communicate that limitation accurately while keeping existing template points and manual evidence review usable.
Do not allow polling or refreshes to reset the selected point, scroll position, or unsaved review input.

## 5. Left checklist tree

Build a compact, searchable, expandable tree:
Project/template -> Category -> Section, where applicable -> Checklist point.
Use the actual approved template hierarchy and ordering.
Do not infer hierarchy from titles when structured data exists.
Do not silently rename, remove, or reorder approved checklist points.

Each point: title; review status using icon and text/tooltip; linked evidence count where useful.
Category completion: “Reviewed X / Y”. Do not confuse reviewed-point counts with evidence counts.

Provide filters: All points; Pending review; Pass; Fail; Not applicable if supported; Missing evidence.
Use existing result values and permissions. Do not introduce new backend enums just to match these labels.

Separate evidence collections: Unassigned photos; AI suggestions needing confirmation.
These are collections, not fake checklist points.

Interaction:
- Clicking a point opens its evidence and review values.
- Keep selected point highlighted and expanded categories preserved on save/refresh.
- Scroll active point into view on Next/Previous.
- Search includes section names and point titles.
- Full text on hover/focus when truncated.
- Keyboard navigation and accessible expand/collapse controls.

## 6. Centre evidence workspace

Centre is the dominant area. Selected point shows full title; category/section breadcrumb; current review status; linked evidence count; approved guidance in expandable area.
Group evidence into Photos / Documents / Other supported evidence.
Clearly label AI suggestions versus confirmed evidence.

Photo toolbar: selected count; Select all visible results; Clear selection; evidence-scope filter; thumbnail-size control; available assignment/link actions.
“Select all visible” must not select hidden/unloaded items.

Cards: real thumbnail; checkbox; filename/readable label; confirmed/suggested/unassigned indicator; available capture date/GPS; relevant review status if supported.
Responsive grid roughly3–5columns according to width/size. Useful defaults; lazy loading/pagination; stable ordering; loading/empty/failed-image/retry states.
Hundreds of photos: no full-resolution originals in gallery, reuse thumbnail URLs, no per-render regeneration, responsive scroll/selection.
Only uploaded evidence, no stock/decorative images.

## 7. Photo viewer

Large viewer: zoom; pan when zoomed; next/previous in current filtered collection; filename; available capture time/GPS; current links; clear AI status; permitted original download; close/Escape.
Rotation only view-only unless an actual existing editing workflow exists.
Preserve point/gallery position after close and restore keyboard focus to triggering thumbnail.
No storage credentials or unauthorized download bypass.

## 8. Document sections

Collapsible section title/count, filename, preview, permitted download.
Use actual file types; supported existing types safely; no arbitrary HTML trusted rendering.
Clear missing-document / unavailable-preview / loading-failure / access-denied states.
Failed preview cannot look like empty successful preview.

## 9. Right review panel

Compact beside evidence: existing-supported result selector; reviewer remarks; required correction reason; labelled expandable AI observation; save state.
Do not prefill the human correction-reason field with “No supported answer was extracted” or other AI placeholder text.
AI observations cannot overwrite reviewer input.
Distinguish absent AI, suggested result, human-confirmed result.
No auto-approval from AI or linked evidence; preserve review/final approvals.
Compact initially sized textareas, expandable as needed.

## 10. Assignment/linking

Preserve: link selected to current point; link to another permitted point; confirm AI; remove link; move where supported.
Link versus move explicit. Unlink/move cannot delete originals; explain removed associations before action.
No invented batch endpoints. Existing per-item API batch must handle/report partial success/failure.
Refresh affected counts after success, keep retry selection on failure.

## 11. Save/navigation

Consistently visible Previous / Next / Save / Save & next.
Next cannot silently discard dirty input. Save & next waits for confirmed success.
Failed save stays on same point with input intact; prevent duplicates; existing stale/concurrency checks.
No premature Saved; useful error/retry. Preserve existing explicit save model; no invented autosave.

## 12. Scrolling/responsiveness

Deliberate bounded panes, no excessive nested scrolling or independent scroll area for every evidence section.
At1920×1080/1366×768: usable tree, centre largest, accessible save controls, no page-wide horizontal overflow, overlapping/clipped panels/menus.
Tablet/phone: checklistdrawer, evidenceprimary, reviewtab/drawer/bottomsheet, controlsnotcovercontent, touchusable.

## 13. Accessibility

Label icon buttons; visible focus; non-colour status; logical tab order; correct dialog focus; readable contrast; browserzoom usability; reducedmotion ifanimated.

## 14. Data/workflow safety

Preserve reviewrecords, originals, checklistIDs, submissionrevisions, confirmedlinks, roles, audits, finalrules.
StableIDs, never arrayindexes for identity. No crosssite/project/revision mixing.
No weakening auth for previews/downloads. Any necessary backendsecurity/policy change separately identified under approval rule.

## 15. Realistic fixtures

Controlled isolated environment, no destructive productionoperations.
Cover166points/460photos; emptysubmission; zerolinkpoint; multiphoto point; sharedphoto; documentonly; longtitles/names; AIprocessing/paused/completed/failed; absentcapturemetadata; brokenthumb; savefailure; partialassignment; dirtyAIrefresh; supportedread-only/reviewerroles.
Meaningful behaviour/data-integrity/regression tests, not implementation mirrors.

## 16. Required verification

Applicable lint, typechecking, tests, productionbuild, browserinteractions.
Browser: open; expand/search; selectpoint; inspectphotos; vieweropen/close; documentpreview; testlink/unlink; save result; Save&next; reloadpersistence; dirtyAIrefresh; responsive.
Inspectconsole/failedrequests, fixintroducedreproduciblebugs, rerunaffectedchecks.
Do not claim100% or allpassed without specific evidence; list blockedchecks/remainingissues.

## 17. Acceptance

Compactchecklist/evidencehierarchy; photos/docsimmediateonselection; reviewformsecondary; compactnonblockingAI; consistent scopedcounts; search/filters/selection/viewer/linking/save/navigationwork; dirtyrefreshsafe; existingpermissions/approvals; specifieddesktop/mobile; checkswithgapdisclosure.

## 18. Delivery

Dedicatedbranch; concisechangedfiles/behaviour; before/after1920×1080/1366×768; mobile; exactchecks/results; limitations; draftPRifaccesspermits.
No merge or deploy.
