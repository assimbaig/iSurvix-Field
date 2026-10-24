# Site Review / QA workspace

Delivery record for the 24 October 2026 reference-layout redesign.
Branch: `feat/qa-review-workspace-20261024`. The owner merged PR17 during this
task; the base was fast-forwarded to `948bfc9` after verifying its committed tree
was identical to `03b5eed`. No working changes were overwritten. No PR merge or
production deployment was performed. Before editing, checkpoint
`.local/backups/project-checkpoint-20261024-154811` passed database integrity,
ZIP CRC and Git-bundle checks. Existing operational workers remain independent.

The owner requirements and live evidence checklist are
`QA_REVIEW_REDESIGN_REQUIREMENTS_20261024.md` and
`QA_REVIEW_REDESIGN_ACCEPTANCE_20261024.json`. Requirements are marked verified
only after their actual checks. Functional verification is complete. Git delivery
is recorded in the final acceptance row and local recovery receipt.

## Integration map

| Area | Existing implementation |
| --- | --- |
| Workspace | `/local/photos/<task-id>/`, `photo_views.workspace`, `qa_evidence_review.html` |
| Full saved review | `/local/photos/<task-id>/capture/review/`, `category_intake.review_state` |
| Lightweight progress | `/local/photos/<task-id>/capture/review/progress/`, `qa_review_progress` |
| Save/link/confirm/move | `/local/photos/<task-id>/capture/review/action/`, `category_intake.review_action`, `qa_matching.action` |
| Protected photos | `/local/photos/<task-id>/evidence/<photo-id>/<variant>/` |
| Protected documents | `/local/photos/<task-id>/capture/documents/<document-id>/` with revision parameter |
| Browser state | Existing controller and session view state, stable checklist/photo IDs |
| Styling | Existing application shell/theme tokens, `qa_evidence_review.css`, `qa_quick_review.css` |

The existing tree, protected viewer, matching dialogs, upload documents and
explicit answer API are reused. The old full-width inline photo viewer gives
way to a dominant thumbnail gallery and large modal viewing. The adjacent review
form uses the existing supported field types and server-side concurrency guards.
The Site Information step keeps all fields and offers original-source comparison.

## Counter definitions

| Display | Meaning |
| --- | --- |
| Submitted photos | Distinct photo IDs in the frozen current submission |
| Assigned photos | Distinct submitted photo IDs with at least one visible link |
| Unassigned photos | Submitted photo IDs with no visible checklist links |
| Suggested links | Individual proposed photo-to-point relations |
| Confirmed links | Individual QA-confirmed photo-to-point relations |
| Current-point photos | Distinct photo IDs linked to the selected point |
| Reviewed X / Y | Human-reviewed checklist points in the labelled scope, not photo count or a claim of compliance |

A photo linked to two points counts once as an assigned photo and twice as a
link. AI suggestion collections count distinct photos; their underlying link
count can differ. Unknown/loading values remain distinct from a known empty
submission. Team Lead sees its existing confirmed-evidence projection rather
than private AI matching data.

Existing inspection results are `Checked`, `Defect found`, and `Not applicable`.
Pass/Fail filters map to those reviewed inspection values. Accepting a text
answer or linking a photo does not turn it into an inspection Pass.

## Narrow data projection changes

The authenticated review DTO now includes the actual used template identity,
raw approved section group, the existing section-lock result, and whitelisted
capture time/GPS from the frozen photo snapshot. It does not expose arbitrary
EXIF dictionaries or storage paths. Missing or invalid capture facts stay absent;
valid zero coordinates remain valid. No authorization rule, status enum, schema
migration or matching mutation API was introduced.

Existing `document:<id>:...` source references identify point-linked documents.
The application has no manual document-to-point linking API; the redesign must
not present one as working. Supporting documents without a point association can
be shown separately as submission documents. Preview availability follows the
actual MIME type and protected routes. Existing PDF-original policy is retained.
A protected `preview=1&raster=1&page=1` option uses the installed PyMuPDF renderer
to serve a bounded PNG without browser PDF plugins or policy relaxation. Original
PDF bytes are checked before cached preview delivery. In-app preview shows the
first page with its actual page count; the full original remains downloadable.
XLSX remains download-only. The derivative-cache integrity limitation is below.

## Verification evidence

Before-layout screenshots were captured at1920x1080,1366x768 and390x844 using
real isolated Django submissions. The large fixture has166 approved points and
460 uploaded synthetic photos, including a shared photo and a document-only
point. Separate fixtures cover72 Site Information rows, genuine embedded EXIF,
unclassified approved groups, missing evidence and empty submissions. Controlled
AI job/results fixtures are not native inference or throughput benchmarks.

Executed red checks reproduced four-column Site Information, the old workspace
layout, AI text in the human reason field, Save advancing the point, and dirty
input being allowed to adopt a different source revision. Backend red checks
identified missing frozen capture/group data and the missing lock projection.
Ten new backend tests cover those projections and actual PDF rendering, cache
reuse, page bounds, original retention and existing access restrictions.

Final checks after the last functional repair:

- Full backend: **1,040 passed in 345.067s**, zero failures/errors/skips, zero
  external connections and 33 in-process HTTP fixtures. Source was stable:
  `5710f85f54288c7c9e88628bac7f3175b1a067700af7338693f4e168745e5689`.
- Eight frontend scripts passed: four behavior suites with **108 assertions**
  and four retained prototype checks. These are separate from browser integration.
- Independent QA: **175 assertions across 15 real saved-data browser runs**,
  including true save/409 reconciliation, partial failure/retry, cross-submission
  dirty protection, PDF raster visibility, thumbnail failure/retry, viewer pan,
  keyboard focus and approved-source Move protection.
- Django system check, migration drift/pending checks, dependency check and
  JavaScript syntax check passed. No migration or new package was required.
- Django static collection built **214 files** into the private review directory;
  the generated controller/CSS hashes match the final source. This is an asset
  build, not deployment. There is no configured lint, TypeScript or bundler
  pipeline; none is claimed as executed.
- **2,091 preexisting operational media/private files** matched the pre-edit
  checkpoint. The isolated large fixture retained all 460 photo hashes,
  categories, filenames, 166-field schema and frozen source snapshot. Only
  expected append-only synthetic QA events were added by its review tests.

Exact backend/check commands, run from the project root:

```powershell
.local\venv\Scripts\python.exe scripts\run_backend_tests.py
.local\venv\Scripts\python.exe backend\manage.py check --settings=checklist.settings_local
.local\venv\Scripts\python.exe backend\manage.py makemigrations --check --dry-run --settings=checklist.settings_local
.local\venv\Scripts\python.exe backend\manage.py migrate --check --settings=checklist.settings_local
.local\venv\Scripts\python.exe -m pip check
node --check backend/static/core/js/qa_evidence_review.js
```

From `frontend`, run `node` with each of: `check-engineer.cjs`,
`check-preview.cjs`, `check-site-routing.cjs`, `check-workspace.cjs`,
`check-engineer-documents.cjs`, `check-qa-guided-state.cjs`,
`check-survey-pause.cjs`, and `check-qa-workspace.cjs`.
The actual isolated asset-build command was
`.local\venv\Scripts\python.exe .local\qa-site-compact-20261024\build_static.py`;
its helper and receipts are retained in the recovery archive. It calls Django
`collectstatic` with `STATIC_ROOT` overridden to that private review directory.

Before screenshots use committed `03b5eed` UI assets served separately against
the same saved synthetic submission. This preserves a reproducible comparison.

| Viewport | Before | After |
| --- | --- | --- |
| 1920x1080 | [Before](../../output/screenshots/qa-site-compact/workspace-before-1920x1080.png) | [After](../../output/screenshots/qa-site-compact/workspace-after-1920x1080.png) |
| 1366x768 | [Before](../../output/screenshots/qa-site-compact/workspace-before-1366x768.png) | [After](../../output/screenshots/qa-site-compact/workspace-after-1366x768.png) |
| 390x844 | [Before](../../output/screenshots/qa-site-compact/workspace-before-390x844.png) | [After](../../output/screenshots/qa-site-compact/workspace-after-390x844.png) |

## Manual verification and startup

Double-click `Start-iSurvix.cmd` and open `http://127.0.0.1:8000/login/`.
Existing app/worker commands remain in `QA_TWO_PANE_AND_AI_REUSE_20261024.md`;
this UI change needs no new service. The local app has been reloaded with matching
HTML/assets; existing AI workers were not stopped or reset.

1. Open My reviews, choose an assigned site and Review evidence.
2. Search/expand a category and select a point. Inspect its linked photos/docs;
   choose Available or a separate evidence collection to find other photos.
3. Open a photo, zoom/pan, navigate and close. Check point/gallery position and
   keyboard focus. Open a linked report preview or download its protected original.
4. Enter the supported result/remarks and your own source-backed reason. Save
   remains on the point; Save & next moves only after confirmed persistence.
5. Refresh and check saved values. Confirm links separately from accepting a
   checklist answer. Final approval/rejection stays in Decision.

Browser zoom was verified through a 200%-equivalent CSS viewport, not physical
phone or assistive-device certification. No native Ollama call or sustained
throughput/engineering-accuracy benchmark was performed for this UI task.

## Safety and scope

Engineer category upload remains separate from QA matching. The existing named
QA, read-only reviewer, approved-section, project-grant, revision and final
approval boundaries remain enforced. Save records an explicit human answer;
final QA/Team Lead/Client decisions remain in their existing workflow.

The earlier security findings S1/S2/S3/R1/R2 and hardening observations remain
approval-pending. This visual redesign does not authorize their remediation.
A separate Agency AppSec review completed five isolated probes and a closing
read-only check of the final JavaScript repairs. **W1 Low** records cached PDF
preview bytes being served without a derivative digest check after private
storage mutation. Original PDF hashes and access checks remain effective; no
remote cache-poisoning route was established. Recommendation: verify a derivative
digest bound to source, page and renderer version, rejecting/regenerating a
mismatch after approval. **W1 is unfixed**, as are earlier findings. Full report:
`SECURITY_REVIEW_QA_WORKSPACE_20261024.md`. Successful adversarial reproduction
does not constitute security approval or universal correctness.
