# Independent QA: gallery headings, availability and shared header

26 October 2026. Final branch `feat/qa-view-panel-header-20261026`; baseline
`19c011a65f158d276bb410ac45a7989d5d41dfe8`. Used the installed Agency Evidence
Collector and Reality Checker definitions, actual handoff and owner development
rules. No product file was edited by this reviewer. This is scoped functional
evidence, not production approval; a separate subsequent AppSec report is
`SECURITY_REVIEW_QA_VIEW_PANEL_HEADER_20261026.md`.

## Baseline reproduced before verification

Archived the exact baseline templates/static files and served them against a
consistent private copy of the existing synthetic166-point/460-photo fixture.
Actual Edge/Playwright captures at1920x1080,1366x768,1024x768 and390x844 showed:

- No group heading elements or checkpoint h4 headings; group context was repeated
  as small text below checkpoint titles.
- Empty groups said `No linked photos.` rather than the requested `Not available`.
- The initial36 cards went to linked groups; the bottom unlinked pool had zero
  card/image nodes until scrolling caused24 to load.
- `Review point` was still an option in the viewing toolbar.

Baseline receipts/screenshots remain private under
`.local/qa-gallery-groups-20261026`: `baseline-ui.zip`, archive hash, `baseline.json`
and `before-*.png`. The baseline was pinned even while workers edited source.

## Final actual-browser verification

After both implementation workers froze source, restarted only the owned8925
fixture against current files. **46/46 gallery assertions passed across all four
viewports**, with no console errors or mutation POSTs (`final-gallery.json`):

- Exact approved group/section heading plus all40 Civil checkpoint h4 headings,
  with actual stable field IDs and distinct saved-photo counts.
- Every zero-photo checkpoint says `Not available`; unloaded or filtered linked
  groups are not falsely called unavailable.
- Initial DOM remains36 cards globally, including12 real protected-preview image
  nodes reserved immediately for the170-photo unlinked pool, before any scroll.
  Pool IDs match globally unlinked photos in the chosen upload category; the pool
  remains last. Visible thumbnail bytes decode successfully.
- No Review-point option in the viewing toolbar or gallery Next pager. The same
  review controls remain accessible through More tools and open the existing
  drawer. General Info remains a read-only submitted/human-value table.
- Duplicate checkboxes for one physical photo synchronize; selection survives a
  real reload. Browsing/selection/reload does not create a matching/review POST.

**5/5 additional controlled-browser starvation checks passed** (`hidden-pool.json`):
the gallery was initially CSS-hidden and IntersectionObserver callbacks disabled.
The true unlinked pool still had12 real image nodes, without exceeding36 initial
cards. Showing the gallery needed no callback to populate it, and its thumbnail
decoded once visible. This is explicitly a controlled visibility test.

**287/287 authenticated header assertions passed over56 page visits**, zero console
errors (`final-headers.json`): all six roles' Home/Profile pages at all four widths,
plus QA My reviews and saved-site pages at each width. Exact permitted link sets,
single/current markers, Profile with no false active section, visible contained
navigation and pairwise selector/Reviews/Help/user collision checks passed.
Desktop headers are44px across all six roles at1920/1366; QA header height matches
Home/Profile/My reviews/saved-site at each viewport. Fonts and touch targets remain
consistent, with no page-level horizontal overflow.

Final targeted visual captures selected a real zero-link checkpoint (`civil_013`)
and waited for all visible unlinked images to decode at1366/390
(`final-visual.json`). An earlier screenshot script hardcoded `civil_033`, which
already had a link in the inherited fixture; that test assumption was corrected
to use actual saved link membership, without changing product or task data.

## Screenshots manually inspected

All public screenshots contain synthetic names/evidence only, without session
tokens or operational survey data. In addition to assertions, manually inspected
the four gallery viewports, visible unlinked pool, Admin desktop and Super Admin
mobile headers. The headings have a distinct group band/checkpoint level; actual
photo pixels and the zero-photo message are present, with no observed control
overlap. These captures support appearance, while JSON receipts establish behavior.

- [Desktop gallery](screenshots/qa-view-panel-header-20261026/after-gallery-1366.png)
- [Mobile gallery](screenshots/qa-view-panel-header-20261026/after-gallery-390.png)
- [Actual mobile unlinked thumbnails](screenshots/qa-view-panel-header-20261026/after-visible-unlinked-390.png)
- [Selected empty checkpoint](screenshots/qa-view-panel-header-20261026/after-selected-empty-1366.png)
- [Admin header](screenshots/qa-view-panel-header-20261026/header-admin-home-1366.png)

1920/1024 gallery and QA mobile-header screenshots are in the same directory.

## Preservation and limits

The consistent SQLite/media copies and synthetic role sessions were under this
F: worktree, served on loopback8925. Only GET/HEAD requests were allowed during
functional browser verification; native-AI calls were explicitly blocked. No
operational task, approval, original, app8000/8001 or model worker was changed.
The owned fixture server was stopped; `cleanup.json` records its PIDs and zero
model-call attempts. Reviewed source hashes are in `final-qa-source-hashes.json`.

Scoped result: requested gallery/header behaviors verified in the tested fixture.
No new functional defect remains from this review. Dark mode, physical devices,
native model accuracy, arbitrary-load performance and production deployment are
not certified. Existing held security findings remain separate. Parent-agent
full-suite/deployment/push results are not claimed as this reviewer's execution.
