# Compact evidence filter toolbar - 26 October 2026

The evidence filter toolbar is now the first row of the QA/Team Lead viewing
panel, above the category/checkpoint heading. It uses the existing navy header
palette, light labels and white inputs. Evidence state, photo search, thumbnail
size and the supported photo scope remain connected to their original controls.
Link/move/selection actions remain separate. General Info retains its own table
and heading and hides photo-only controls through the existing controller.

QA and Team Lead share this component. Admin and Client retain their already
top-aligned gallery filters and existing permissions; Engineer retains category
upload without QA matching controls. No backend service, controller, model,
permission or approval-policy change was made.

Agency Frontend Developer/UX Architect profiles guided implementation. An
independent Reality Checker/UX reviewer exercised actual Django fixtures, then
performed a separate AppSec review. Unit and real HTTP tests were executed RED
before implementation, then GREEN. The owner later requested moving the bar
above the heading and applying the header palette; the additional order test
was executed RED before that refinement.

## Verification

- 35 affected backend unit/integration tests passed, no failures/errors/skips.
- All18 frontend check scripts passed using installed Edge via
 `PLAYWRIGHT_BROWSER_CHANNEL=msedge`; default Playwright Chromium is not installed.
- Django check and migration-drift check passed; isolated static collection copied215files.
- 92 actual browser assertions passed across15 role/viewport visits, including
 search/state/thumbnail controls, General Info hiding and dirty-input/selection
 preservation during refresh. No JavaScript errors or failed local requests.
 External CDN requests were intentionally blocked and recorded separately.
- Five focused geometry/color cases passed; desktop toolbar40px and collapsed
 phone toolbar47px in the controlled layout fixture. The independent actual
 application screenshots show final placement/palette.
- Separate security review:9 focused assertions passed, no new exploitable
 finding established. Tested hostile search text, control/role boundaries,
 forged unauthorized matching and unchanged saved data. Not exhaustive DAST.
 Prior unrelated security findings remain unapproved and untouched.

The final palette/geometry capture gate passed65 additional checks on unchanged source; these overlap the earlier browser coverage.

The final receipt records exact commands and frozen source hashes. Intermediate
runs are preserved privately, including a gate that passed its checks but caught
late CSS/test edits; the complete affected gate was rerun on unchanged source.
The previous full backend run's Windows symlink privilege error remains disclosed
in the earlier batch-decision acceptance report; this focused follow-up does not
claim a newly green full backend suite.

## Files and testing

Product: `backend/templates/dashboards/qa_evidence_review.html` and
`backend/static/core/css/qa_quick_review.css`. Tests:
`backend/core/test_qa_filter_toolbar.py`, `frontend/check-qa-filter-toolbar.cjs`.
CSS cache token `qa-filter-toolbar-20261026-2`.

Open http://127.0.0.1:8002/login/ with your existing account, press Ctrl+F5,
open a review and select Civil/Electrical/Tower. Filters should appear above the
category heading. Search a filename, filter unassigned evidence and change
thumbnail size. On phone expand Filters. General Info should show its data table
without photo filters. Existing operational app/model/worker services remain
running; only the web candidate8002 was restarted. No native AI request was made.

Recovery: `.local/backups/project-checkpoint-20261026-233722`, complete archive
CRC checked plus consistent SQLite backup and pre-change source ZIP. The update
stays on `feat/qa-batch-decisions-20261026` in draft PR23; no merge/deployment.
