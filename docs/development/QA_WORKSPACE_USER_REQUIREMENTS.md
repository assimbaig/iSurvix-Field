# QA Engineer review workspace — owner requirements, 23 October 2026

This records the owner's next-phase instruction. Finish Engineer category intake first.
Run the full audit before uploading the combined work to GitHub. The owner later
provided `F:/iSurvix/references`. Its `Notes for Layout.txt` and twelve screenshots
were inspected for Engineer, QA and Team Lead layouts: compact header, narrow
navigation, checkpoint list and evidence space. Those assets are layout references
only; their customer branding, site data and checklist text are not imported.

## Objective and agents

QA receives the Engineer's category-based submission and AI-generated checklist
matching. QA reviews and corrects the matching in one workspace. Reuse the
application's existing branding and components.

Read repository instructions and installed Agency definitions. Use UI/UX for
panel layout, frontend for navigation/thumbnails/drag-and-drop, backend for saved
matching and AI handling, and independent QA/testing for end-to-end verification.
Coordinate ownership and report unavailable agents accurately.

## Three visible areas

1. Left navigation: categories.
2. Main workspace left: checklist points.
3. Main workspace right: photo thumbnails.

Keep task/site information in a compact header.

### Category navigation

- General Info, Civil, Electrical, Tower.
- Provide plus/minus expand/collapse controls for category groups.
- Group/ungroup means navigation expansion/collapse, not category editing.
- Selecting a category filters its checklist and photos.
- Clearly distinguish checklist-item counts from photo counts.

### Checklist points

- Show points from the selected category, with title, linked-photo count and
  existing review status where supported.
- Clicking a point displays its linked photos on the right.
- At the end show `Not Assigned (count)`, including when count is zero.
- Not Assigned means photos with no checklist links.
- Required points without photos remain visible with a zero evidence count.

### Photo workspace

- At the top show selected point title, approved requirement/instruction,
  assigned-photo count, and Pending/Processing/Complete/Failed AI state.
- Use a compact thumbnail grid with identifier/filename, current assignment,
  AI-suggested versus QA-confirmed assignment and an AI-analysis action.
- Clicking opens the existing enlarged viewer where practical.
- In the viewer/compact details show full image, AI observation, suggested point,
  brief supplied matching explanation and current saved assignments.
- Keep AI details with QA; do not expose them as Engineer action items.
- Avoid a permanent extra panel that reduces photo space.

## Matching and display order

QA must confirm suggestions, change incorrect matches, assign unassigned photos,
remove incorrect links and use existing engineering review controls.

- Drag a photo onto a point to assign/reassign; provide an equivalent
  Assign to checklist point click/touch alternative.
- Clearly show valid targets. Save to the backend before reconciling counts and
  Not Assigned. On failure retain/restore prior state and display an error.
- Reorder points only within their existing category/group for review display.
- Persist display order only. Do not change requirement IDs, template content,
  evidence links or engineering decisions; no template editor through dragging.
- Reuse existing evidence relationships where appropriate. Never silently remove
  another valid link. A photo is unassigned only when it has zero links.

## AI and review authority

- QA can open before AI finishes; progress must not block manual review.
- Populate proposals only against approved IDs; preserve unsupported or uncertain
  photos as unassigned.
- Late/retried results cannot overwrite QA correction/confirmation, duplicate
  evidence links, invent readings or accept inspected work merely from matching.
- Keep assignment, confirmation of the assignment, and acceptance/rejection of
  inspected work distinct.
- Reuse the current engineering decisions; do not create another approval system.

## Persistence and permissions

Store each assignment against the correct project/task, submitted revision,
photo ID and checklist point ID. Audit who changed it and when.

Enforce QA permissions on endpoints, cross-project restrictions and approved
record locks. Approved-evidence reassignment requires the existing authorized
reopening procedure.

## Visual requirements

- Compact header, readable navigation, expandable groups, clear point titles and
  thumbnails large enough for inspection.
- Do not crop or distort technical photos.
- Resizable panes where supported; clearly highlight category and point selection.
- Preserve selection when viewing/closing a photo.
- Useful loading, empty and failed-save states.
- On small screens put category navigation in a drawer while retaining an
  accessible checklist-to-photo workflow.
- No oversized dashboard cards or unrelated statistics.

## Limit scope

Only category navigation, point list, grouped thumbnails, QA AI analysis,
confirmation/correction, drag-and-drop and touch alternative, Not Assigned,
required persistence, permissions and tests. No chat, industries, roles,
analytics, reports, custom template builders or unrelated redesign.

## Original acceptance list

1. Engineer uploads photos by category without selecting checklist points.
2. Engineer submits; the task appears for QA before AI completes.
3. AI matches actual photos against the correct approved template.
4. QA sees General Info / Civil / Electrical / Tower on the left.
5. Category groups expand and collapse.
6. Selecting a checklist point shows its linked photos.
7. Not Assigned appears last and shows genuinely unassigned photos.
8. QA can inspect AI analysis for each photo.
9. Dragging a photo onto a checklist point saves the correct link.
10. The click/touch assignment alternative performs the same action.
11. Checklist reordering changes display order only.
12. Counts and assignments remain correct after refresh.
13. Failed saves do not display false success.
14. Late AI results do not overwrite QA corrections.
15. AI failure still allows manual QA matching.
16. Matching never automatically accepts engineering work.
17. Existing permissions and approved-record locks still apply.

Use Agency Agents to implement, test, find defects, fix and retest every item.
Do not claim completion until the actual saved-data Engineer-to-QA scenario has
been tested. Deliver changes, working screenshots, results, limitations and a
short manual verification procedure.
