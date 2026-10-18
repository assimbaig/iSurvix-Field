# iSurvix Field: local Codex development brief

## Workspace and current state

Keep the existing Windows checkout and all project runtime data under
`F:\iSurvix\iSurvix-Field`. Do not relocate it to the earlier C: checkout path.
The working local launcher/text-AI integration is on branch `feat/local-ollama` (PR #2).
Inspect `git status`, branches, README, docs/LOCAL_SETUP.md and applicable AGENTS.md before changes.
Do not overwrite uncommitted work or change branches until its state is understood.

Existing code: Django backend, versioned custom checklists and client logos, section approvals,
Excel export, separately hosted sample-data redesign, and local Ollama text chat.
The redesigned frontend is NOT connected to real Django records yet.
The existing 36-test baseline was checked in Linux; Windows first launch remains to verify.
The user saw `No suitable Python runtime found`: install/verify Python 3.12 before launching.
Ollama was installed earlier; `qwen3.5:4b` was the selected model. Verify installed models and
actual vision capability rather than assuming its download or image support succeeded.

Some preliminary photo-queue code was drafted in the remote chat workspace but is NOT part
of this branch. Do not assume it exists locally or is finished. Implement/test against the
actual checkout, using this brief as requirements.

## User's requested working model

Use Codex in PowerShell to design, develop, test and maintain the app.
Use Ollama on the PC for operational AI inference on project photos and checklist evidence.
Use existing agent instructions if they can be found and verified. Codex subagents and
Ollama application agents are separate mechanisms; do not claim a connection without wiring it.
No paid/cloud AI API is requested for the application's photo processing.

Start with design/navigation refinement, then implement one end-to-end photo pilot before
scaling it to large batches. Preserve the admin builder and existing survey review workflow.

## Approved layout

- Logo/name top left; centered full-width module navigation below with room for more modules.
- Compact left catalog: Project > Subproject (when modeled) > Site ID; grouped/ungrouped sections.
- Large photo viewer, thumbnails, fullscreen, and source-evidence links.
- Two compact review rows; Full Approve, multi-section Partial Approve, Full Reject.
- Approved sections remain locked; unapproved sections can be corrected.
- Do not replace or discard the full 172-row FDED checklist, inventories or client branding.

## First release: bulk photos to reviewed draft checklist

1. Make a development branch and checkpoint existing work.
2. Start the current app, fix local setup issues, check Ollama connectivity and vision support.
3. Integrate the new UI with authenticated Django data; sample records must remain labeled.
4. Add site-scoped uploads: initially 200 photos/site; browser submits batches of <=20 files,
   <=5 MB each. Preserve original bytes and filename metadata; validate real JPEG/PNG/WebP.
5. Extract available EXIF GPS/time (do not infer missing metadata). Detect exact-byte duplicates,
   flag possible blur/low detail as advisory, and keep a normalized preview for inference.
6. Use a durable database-backed queue and an independent local worker. Show progress, failures,
   retry and recovery after interruption. Avoid unlimited GPU workers and request timeouts.
7. Check the selected local model reports vision capability. Send base64 image data through
   Ollama's native local API; do not enable cloud fallback or expose Ollama to the LAN.
8. Classify visible evidence and map it to the selected published checklist's field IDs.
   Use bounded prompts/structured output with validation and no silent catalog truncation.
9. Return draft values, reasons, uncertainty and photo references. Allow insufficient evidence.
   Never invent dimensions, electrical readings, ratings, standards clauses or N/A decisions.
10. Flag suspected visible anomalies with source photos and optional normalized bounding boxes.
    No detections does not mean the asset passes inspection. No engineering certification.
11. Show drafts in a review queue. Apply a proposed answer ONLY on explicit engineer acceptance.
    Recheck project access, field types, approval locks and stale values at acceptance time.
12. Export a report with drafts, source evidence, suspected defects and missing-information requests.
    Preserve an audit trail; model output must not approve, reject or silently overwrite records.

## Sketch phase

After the photo pilot works, add annotated evidence and measured plan/elevation sketches.
For dimensioned output, require user-confirmed measurements and units. Mark unknowns instead
of guessing scale from ordinary photos. Produce editable SVG/DXF where appropriate.
Do not present an illustrative layout as an engineered/as-built drawing.

## Agents and coordination

Where available, use specialized Codex subagents for UI, local vision/backend, and independent QA.
Keep file ownership clear; do not run several agents editing the same files without coordination.
If existing Agency Agents are present, read their actual instructions and integrate only relevant
roles. Runtime photo agents should share a durable job/evidence schema and one controlled local
inference queue. Roles/prompts are not automatically connected software.

## Acceptance checks

- Real local first launch; chosen admin account; saved surveys survive restart.
- Real Ollama image test on a few user-selected site photos before bulk scaling.
- Auth/CSRF/project access on all photo operations and downloads.
- Corrupt image, duplicate, missing EXIF, missing model, offline model, malformed JSON and restart.
- Approved-section locks, stale answer conflict, missing fields and no automatic approvals.
- UI tested at desktop and phone widths; photo/source links and review decisions work.
- Existing checklist/versioning/export tests continue to pass.
- Clearly report what is implemented, what was tested with a real model, and what remains.

Keep work local by default. Preserve `.local/` (database, media, secret) and do not commit it,
credentials, logs, installed dependencies or real project photos. Do not deploy to Hostinger
or force-push/merge branches without the user's instruction.

## First action

Inspect the checkout, local agent configuration, Python 3.12 and Ollama. Then provide a short
status and begin making the app run locally. Continue through implementation and tests; ask
only when a missing input blocks actual work. Do not require a cloud API key for Ollama.

## Local continuation completed 2026-10-17

- Development branch: `feat/local-photo-pilot`, based on the clean `feat/local-ollama`
  checkout. Changes are local and uncommitted; do not overwrite them.
- Installed and verified Python 3.12.10. The environment and installed app dependencies
  are in `.local/venv`. Django starts successfully on `127.0.0.1:8000`.
- Local database initialized through additive migration `0016_photo_pilot`. No production
  database or real project photos were imported. Existing `.local` files must be preserved.
- The launcher starts a separate durable photo worker. Web chat and photo inference
  share a heartbeat-backed database lease. Upload spill files also stay under `.local`.
- First-run account creation is at `/local/setup/`, loopback-only and CSRF-protected,
  and closes after the first superuser exists. No default credentials were created.
- Existing UX Architect, Application Security Engineer and API Tester agent roles were
  used after inspecting their actual `.codex/agents` instruction files.
- Real authenticated surveys link to a responsive photo workspace with project/site
  catalog, large viewer, thumbnails, fullscreen, source downloads, batched upload,
  job progress/retry, explicit draft acceptance and JSON evidence export. The existing
  custom checklist retains its full/partial/reject controls and section locks.
- Originals are preserved, byte duplicates detected per survey, available EXIF extracted,
  previews normalized and low-detail advisory flags shown. The published field catalog
  is processed in bounded batches without silent truncation. Runtime model verification,
  schema validation, project access, stale answers and approval locks are enforced.
- The installed `qwen3.5:4b` reports vision capability. A real native image-input probe
  and a full synthetic upload-to-draft-to-explicit-acceptance/report pilot passed.
  Both tests use synthetic shapes; no real site photos have been analyzed.
- The 59 baseline/photo tests passed, as did three first-run-account tests and focused
  regressions after schema/lease refinements. Django check and migration consistency pass.
- Edge browser checks passed at 1440, 390 and 320 pixels using rendered synthetic
  survey data and stubbed API responses without database writes. Viewer, thumbnails,
  draft rendering and a single 21-photo enqueue request were checked. Shared blur/header
  CSS conflicts found during these checks were fixed. Screenshots remain in `.local`.
- Reusable verification scripts: `scripts/check_local_vision.py` and
  `scripts/check_photo_pilot.py`. The latter isolates database/media under `.local`.

Remaining acceptance work: user-selected site-photo quality/throughput pilot before bulk
scaling, saved real-survey restart verification once a project/account exists, and the
later measured sketch phase. The separate `/app/` frontend remains visibly labeled
sample data; the photo workspace uses real Django records.

## Invitation-based role workspace continuation

The user's next instruction replaces the sample website with an invitation-based
operational application. `/app/` now returns 410; static source files are preserved.
`/local/` opens `/governance/`; local text AI remains at `/local/assistant/`.

Exactly four roles are defined: Engineer, Team Lead, Project Admin (legacy stored
`ADMIN`) and Super Admin. Only actual active/unlocked Django superusers have global
authority; a role label or legacy session flag cannot grant it. The initial local
bootstrap creates the first Super Admin. All later accounts require an expiring,
single-use invitation. Invitations are shown as private local links; no email is sent.
Super Admin invites Project Admins, who invite their own project's Engineers/Team Leads.

Added migration `0017_invite_governance`, scoped task assignment, member activation/
deactivation/role/unlock controls, governance audit, and separate external client
decision recording after internal Final approval. Client decisions recheck a signed
snapshot and are audited. Existing survey/photo locks remain enforced. Login no longer
offers a role selector or promotes Admin users to Super Admin. Older global account
provisioning and unsafe deletion routes are retired.

Super Admin access maintenance requires current password and typed `RESET ACCESS`.
It clears sessions/lockouts and revokes outstanding invitations while retaining all
users, projects, survey answers, media, templates and audit records. A destructive
factory reset was not inferred from the phrase "master reset".

The database was backed up under `.local/backups` before the additive migration.
Browser checks passed 24 synthetic role/form cases at 1440, 390 and 320 pixels.
The final combined regression suite passed all 79 tests, including 16 governance
checks; Django system check and migration consistency checks passed.
See `docs/ROLES_AND_INVITATIONS.md` for the current routes and role matrix. No remote
hosted preview has been deleted or deployed as part of this local change.

## Requested demo users and Client role

The user subsequently requested 10 Engineer, 3 Client and 2 Team Lead dummy accounts
with temporary credentials. This explicitly adds a fifth **Client** role to the earlier
four-role request. Clients can view only their project's internally Final deliverables,
inspect evidence/export and approve/reject using their authenticated identity. They
cannot alter engineering answers, upload/infer photos, accept AI drafts or manage users.
Super Admin can now invite all non-Super roles; Project Admin can invite Client as well
as Engineer/Team Lead. Additive migration `0018_client_role` is applied.

Fifteen requested accounts were provisioned and login-verified through CSRF-protected
invitation acceptance in **iSurvix Demo Training**. Existing `super_assim` credentials
were not changed. No real site records or fake measurements/approvals were created.
Temporary credentials are kept only under ignored `.local/demo-account-credentials.*`;
never copy them into repository files. A pre-provisioning database backup is under
`.local/backups`. Demo provisioning script is `.local/provision_demo_accounts.py`.
All 89 regression tests passed, including 10 new Client checks. Three focused worker
retry tests also passed after fixing an observed SQLite contention crash during batch
provisioning. Live HTTP sign-in was verified for one account of each requested role;
all 15 passwords were verified through normal invitation/sign-in views. The app and
worker were restarted with the Client and retry changes loaded.

## Section/item selection for custom checklists

The user requested building custom checklists by selecting from the full checklist.
`/devadmin/checklist-templates/select/` now provides whole-section and individual-item
checkboxes, search, select-all/clear, accurate counts and a live selected-items preview.
The authoritative catalog contains 16 sections and 181 field nodes, including the 172
original source rows; no catalog items are truncated. Administrators can use the built-in
master or an accessible existing revision as the source. The existing editor's entry
link carries the current source revision, preserving its branding and custom edits.

POST validates selected IDs against the scoped server-side source and creates a new,
unpublished checklist family/version 1. Selected IDs, groups, field settings, inventory
columns and branding are retained. Publish and assign through the existing editor.
The source, user draft #2, project assignments, existing survey snapshots and approval
locks are unchanged. No schema migration was needed. Locked Project Admins are denied.

All 103 regression tests passed, including 11 selection tests. Edge functional checks
passed at 1440, 390 and 320 pixels, including partial section states and preserving
filtered selections during submission. Authenticated live GET confirmed the complete
181-item catalog in order without creating or modifying real drafts. The app/worker
were restarted with these changes; root coordinated backend, UX and QA agents.

## Primary Project Admin and activity closure workflow

The user next requested explicit Super Admin assignment of Project Admin, followed by
Project Admin creation/invitation of Team Leads, Clients and Engineers, and activity
closure at Client approval, or Team Lead approval when no Client is configured.

Added nullable `Project.administrator`, three nullable checklist client-routing markers,
and `WorkAssignment.CLIENT_REVIEW` in additive migration `0019_client_review_routing`.
At first complete internal approval, routing snapshots all assigned Client profiles
(including disabled/locked accounts) or a valid pending Client invitation. With a
Client configured the activity awaits authenticated Client approval; without one it
closes immediately. Client rejection keeps it open; Admin-recorded external approval
does not bypass the Client gate. Closed activity decisions cannot be rewritten.
Checklist FINAL remains the internally approved state and all section locks persist.
Historical completed records/routing markers are preserved without retrospective edits.

Super Admin has an audited primary-admin assignment action. It does not silently move
an Admin out of another project or delete previous memberships. Acceptance of a new
Project Admin invitation assigns an empty primary slot. Pending/closed workflow stages
are visible in the workspace and checklist. A database backup was taken under
`.local/backups` before applying the migration. Fourteen focused workflow tests and
synthetic role/browser viewport checks passed; the full regression run follows.

## Final workflow runtime verification

The prior combined regression suite passed all 117 tests. The final targeted suite
passed all 43 tests: 17 workflow tests (including strict Engineer/Team Lead stage
signatures) and 26 checklist-builder tests. These suites overlap; do not add their
counts as unique tests. Assigned Engineer submission and actual project Team Lead
internal review are enforced server-side, including legacy delegates. Project Admin
and Super Admin may support unlocked draft corrections but cannot sign these stages.

The verified local launcher PID 9904 and only its child process tree were stopped.
The replacement hidden launcher PID is 15760, started with `-NoBrowser`; logs remain
under `.local`. The launcher applied additive migration `0019_client_review_routing`.
`showmigrations core` confirmed it applied; Django system check reported no issues.
The server listens only on `127.0.0.1:8000` (runtime PID 13212, wrapper PID 31452).
The independent photo worker is running (runtime PID 4616, wrapper PID 30092).
Process IDs are an observation for this session and may change at the next restart.

Authenticated live read-only verification via
`.local/verify_live_checklist_selector.py` passed: all 181 source items appear in
source order. The check signed in and out normally without creating or modifying
checklist drafts or project records. Current launcher/worker error logs showed no
startup or worker errors. Existing users, credentials, surveys, media and approval
history were preserved. No real site-photo accuracy or hosted deployment was claimed.

## Company access and conditional critical AI review

The 17 October 2026 extension adds Company, Profile.company and explicit active
ProjectMembership records in migration 0020_company_memberships. Admin can manage
multiple explicitly granted projects in one company. Team Lead, Engineer and Client
start with one primary project and may receive additional same-company grants.
Non-Admin workspaces default to the primary accessible project; the scoped selector
can switch projects or explicitly show an overview. Engineer ownership and Client
Final-only gates remain. Revocation overrides legacy primary fallback and preserves
history. Global account actions require Admin control of all target active grants.
Cross-company grants/reclassification cannot silently transfer active affiliations.

Migration 0021_checklist_ai_review stores private-by-default critical reviews in a
separate model. Actual project Team Leads request the local structured critique and
explicitly share/unshare each report. Clients see only completed, current, shared
reviews with project authorization and Final status. Changed answers/schema/evidence
make old sharing stale. Private review data does not enter generic Excel/photo
exports or text context. AI never changes answers or signs approval. Review inputs
include recorded evidence summaries, not a new inspection of original images.

Review persistence/sharing rechecks fresh authority under the governance lock and
uses the shared local inference lease. Critical review is synchronous, unlike the
durable photo queue; a later request marks interrupted running records failed after
obtaining the lease. No automatic rerun or sharing occurs. A real native Ollama
qwen3.5:4b synthetic critique returned one validated finding without project records.
Python 3.12.10 and model completion/vision capabilities were reverified.

Final combined core suite: all 145 tests passed in 131.857 seconds, including ten
new company/migration and fifteen critical-review checks. The obsolete single-project
Admin test fixture was updated to use a genuinely foreign company. A final focused
Client visibility test passed after adding no-store protection to review HTML.
Twenty-four synthetic responsive cases passed. Django, migration drift and JS syntax
checks passed; counts overlap and must not be summed as unique acceptance cases.

The verified old launcher 15760 and its own children were stopped. A consistent
checkpoint was taken at .local/backups/before-company-review-20261017-212054.sqlite3.
Migrations 0020/0021 were applied. Every old column in users/profiles/projects/surveys/
assignments/templates/photos/drafts/audit and all media matched pre-upgrade hashes.
Existing counts were 16 users, 2 projects, 3 template revisions and 57 audit events;
no activities or photos were fabricated. These counts precede normal verification
sign-ins, which legitimately update login/audit metadata.

New hidden NoBrowser launcher PID 25132 is running; web observed on loopback port
8000 with PID 20920. PIDs are observations, not stable configuration. Authenticated
Super Admin full-selector GET (181 fields) and Engineer/Client/Team Lead sign-in
checks passed after upgrade. Existing credentials remain unchanged.

Documentation is split into docs/manual/iSurvix_Field_Software_Manual (user operations)
and docs/development/iSurvix_Field_Development_Guide (internal implementation), each
DOCX/PDF in the app palette. Superseded combined guide is internally archived; an
opened legacy PDF may remain at its original path for compatibility. The explicit
allowlist in scripts/package_user_manual.py distributes only the Software Manual
PDF and DOCX for the final release. See docs/README.md and the approved implementation
plan. Real-site AI accuracy, sustained throughput, GPU performance, SMTP, external
deployment and independent restore acceptance remain open.

## Paused at the owner's request

The owner is stopping work for now and will return later to investigate unspecified
issues. Do not assume those issues are resolved; no description was supplied.
All implementation and manuals are saved in this checkout. Two requested Admins,
demo_admin01 and demo_admin02, were created through CSRF-protected invitation
acceptance and login-verified. Both have explicit grants to iSurvix Demo Training
and Test Project 1 within the existing company. Existing credentials were not reset.
Their temporary credentials are only in ignored .local/admin-account-credentials.json.

A dated local checkpoint under .local/backups/project-checkpoint-* preserves source,
documentation, a consistent SQLite backup, media and local recovery configuration.
It is a private local backup, not a Git commit, push or deployment. Keep the entire
project under F:\iSurvix\iSurvix-Field. Resume by reading this handoff, checking current
runtime and Git state, and addressing the owner's reported issues without overwriting
existing data. The local app is left running; no further feature changes are pending
in this pause turn.

## Resumed workflow crash recovery

The owner resumed with a workflow crash. Logs identified invalid review POSTs to
`[object RadioNodeList]` and SQLite lock errors during saves/session loading.
Fixed survey_workspace.js to read the form action attribute rather than the named
property shadowed by action controls. Actual Edge checks passed Engineer save/submit
and all four Team Lead review decisions against synthetic fixtures and real JS.

Idle photo polling now performs only a read when no queued/running job exists.
Local startup enables persistent WAL once; local short atomic blocks use IMMEDIATE
transactions with timeout30 and no request-wide transaction. Inference remains
outside transactions. Six focused backend contention/recovery checks passed.

Final full core suite passed all 147 tests in 134.939 seconds. Django checks,
migration consistency and JS checks passed. Before recovery a consistent checkpoint
was saved at .local/backups/project-checkpoint-20261017-213352. Live survey/task rows
matched that backup after restart: actual activity1 remained Submitted, with answers
and approvals intact. No real activity decision was made during testing.

Replacement launcher24016 and web runtime22432 were observed running; PIDs may change.
WAL was verified active. Authenticated live Engineer and Team Lead checklist GETs
and the corrected served JavaScript passed. The app was reopened for the owner.
See docs/WORKFLOW_CRASH_RECOVERY.md. Earlier pause notes are superseded by this repair.

The subsequent rejection complaint showed the old RadioNodeList POST again from a
previously loaded page. Added explicit workflow-recovery-3 versions to checklist JS
URLs so a refreshed page fetches the repaired scripts. Re-ran real Edge save/submit
and all four review decisions successfully, plus all17 workflow tests. Restarted
launcher27784 and live-verified versioned HTML and repaired JS for Engineer/Team Lead;
actual answers/approvals remained unchanged. Reopened the local workspace. A page
left open before the update must be refreshed to replace its already-loaded handler.

## Engineer photo upload access

The next reported issue was Engineer upload access. Actual activity1 was Rejected
with no section locks. There were no upload POSTs in live logs: the old Photos tab
opened only a section viewer with no visible upload entry. Both backend upload
routes passed four new isolated real-PNG/CSRF tests as the assigned Engineer, without
changing answers, status or approvals. No backend permission relaxation was needed.

Photos & uploads now opens the actual site photo library. The checklist's section
viewer has a visible Upload site photos link and a section-upload shortcut when an
editable photo field exists. Copy distinguishes section attachments from site-library
photos. Submitted/Final/Client read-only notices explain the actual stage. Script
and stylesheet versions avoid stale assets. Phone layout has explicit box sizing.

Actual Edge tests passed PNG multipart images/files uploads, thumbnail rendering,
corrupt-image errors, oversize client validation without POST, preserved existing
images and 1440/390/320 layouts. Synthetic records/media only. Isolated API tests
are backend/core/test_engineer_upload.py. The focused 54-test run passed 53 cases;
its only failure was an obsolete assertion for the renamed Photo workspace label,
updated to Checklist section photos, followed by a final builder regression run.

Launcher13608 is observed running after restart (PID can change). Live normal sign-in
as demo_eng01 verified Upload site photos, editable /local/photos/1/ controls and
authenticated photo state. Existing actual site-photo count was0; none was fabricated
or deleted. Evidence/review locks remain. Browser reproduction is in ignored .local
render_photo_upload_fixture.py and engineer-upload-browser-regression.cjs.

The final builder rerun passed all26 tests in64.702seconds after updating the obsolete
label assertion. All focused upload/photo/builder cases now pass. The earlier full147
suite remains the prior baseline; do not sum overlapping runs as unique tests.

## Field intake grouped photography and AI locations

The approved field workflow is delivered locally. Team Leads/Admins/Super can preview
UTF-8 CSV (1MiB/200rows), validate project/Engineer/checklist general-info IDs, then
commit all assignments atomically. Single assignment also accepts validated preloads.
AssignmentIntakeBatch retains source/template fingerprints and creator-bound previews;
Checklist.intake_metadata retains provenance. Engineer edits unlocked site information
through a stale-checked endpoint; linked Site ID cannot be overwritten.

Engineers open a photo-first field workspace. Civil/Electrical/Tower group uploads
are split into bounded requests; Upload & analyze group explicitly queues durable
work behind earlier jobs (opt-in queue_when_busy, max10 pending, no overlapping IDs).
Local vision creates proposed PhotoPlacement links, not automatic answers. Reviewed
proposals can be confirmed in batches100; manual corrections reject/replace links
atomically. Existing human confirmation/rejection wins over model reruns. Confirmed
links appear beside fields and in Excel, with separate evidence-location provenance.
Legacy image_data and original bytes remain unchanged. Required photo validation
counts confirmed evidence, including selected-section approval using full source schema.

Coverage distinguishes explicit required photos from recommended inspection evidence.
Canonical master has150 inspection fields and0 dedicated photo fields, so a required-
photo-only counter would be misleading. Human N/A with reason can exclude recommended
slots; AI cannot invent N/A. Processing readiness tracks durable processed photo IDs,
including zero-draft results. Pending photo work blocks final critical review. Engineer
can request/read own private reviews; Team Lead can inspect and alone controls Client
sharing. Mapping/coverage/source changes invalidate older review snapshots.

An actual native synthetic vision probe initially over-tagged a blue rectangle as both
blue and absent red subjects. Fixed prompt/schema to require explicit evidence_match
and concrete visual_evidence. Absent/insufficient/generic/legacy null-only drafts cannot
create locations. The corrected probe returned only the blue subject with a meaningful
observation. No site/photo records or approvals were created by probes. Real-site
accuracy and bulk throughput still need field acceptance; confidence is not certification.

Final core suite passed186 tests in163.371seconds after the tagging fix. Prior184 run,
focused8 intake/5export/40photo cases and responsive/browser checks overlap. Actual
Edge tests covered camera/gallery PNG, group queueing,105 mappings in100+5 batches,
late-batch retry, manual correction, CSV preview/commit and Engineer/TL sharing controls.
Independent security audit found no new scope/atomicity defect; corrected a minor actor
provenance label. Physical phone/LAN/offline operation is not claimed.

Stopped only verified launcher13608 and children. Consistent private checkpoint:
.local/backups/project-checkpoint-20261017-220905. Applied additive migrations
0022_assignment_intake and0023_photo_placements. Before restarting, compared every old
column in29 existing tables and hashes of all4 media files: unchanged. New model
permissions/content types/migration bookkeeping are expected additions. No real task,
answer, evidence, credential or approval was fabricated or reset.

Replacement hidden launcher4076 is running; observed web32684/worker wrapper31804.
PIDs can change. Live normal Engineer/Team Lead GET checks passed: field workspace,
181-field state with existing1site photo, general-info endpoint, own critical review,
TL bulk preview/sample and Engineer403 for bulk. No uploads/decisions were made by
live verification. Django/migration-drift/JS checks passed; worker stderr clean.

Software Manual v1.2 now11pages; internal Development Guide v1.2 now8pages, each
Word/PDF, rendered and inspected. Final user documentation ZIP still contains only
the Software Manual. Updated plan: docs/FIELD_PHOTO_WORKFLOW_PLAN.md. Existing photos
can be selected and analyzed for new locations; older drafts/history stay preserved.
All project/runtime data remains F:\iSurvix\iSurvix-Field. Do not run old recovery
verifiers that compare a historical Submitted snapshot after legitimate user edits.

## Real 78-photo queue failure recovery (2026-10-17)

Actual jobs1 (77 photos) and2 (78 photos) failed before their first checkpoint.
Verified installed qwen3.5:4b vision support before native reproduction. Exact causes:
non-null generated values for protected human-only fields, malformed inspection
answer structures, and then truncated JSON from the old 53/64-field batches.
Inference now withholds unsafe/invalid answer values as null with an explicit human
verification warning. Strict draft acceptance and visual-evidence validation remain
unchanged. Unknown IDs, generic matches, invalid metadata and invalid boxes still fail.
Catalog batching now retains all181 fields in16 batches, at most12 fields per batch,
and still respects the UTF-8 byte bound. Truncation and validation failures expose only
controlled photo/batch/error diagnostics, never raw model content or image bytes.

Checkpoint before recovery: .local/backups/project-checkpoint-20261017-221724.
Private answer/approval/photo-digest baseline: .local/photo-recovery-before.json.
Existing43 photo/placement/worker tests passed; independent recovery10 tests passed,
53 distinct tests. Recovery tests cover strict injected-answer rejection, unsafe-value
withholding, all181 catalog fields, truncation privacy and failed-photo checkpoints.
The larger full186 run above predates this repair; it was not rerun for this patch.

Restarted verified launcher4076 tree only; replacement launcher29976 observed running.
Normal Engineer/Team Lead live GET checks passed with78 photos and181 fields. Retried
existing job2 through the owning Engineer's normal authenticated HTTP endpoint; job1
is preserved as failure history and was not retried to avoid duplicate processing.
No photo uploads, answer changes, confirmations or approvals were performed by recovery.

Native acceptance probe completed one actual uploaded photo across all181 fields in
275.02seconds with12 validated draft suggestions and no truncation or validation
failure. The probe wrote no photo results; released its shared inference lease cleanly.
Fresh database inspection then confirmed job2 running, attempt2,0/78, empty error.
Observed throughput is about4-5minutes/photo, so78 photos may require several hours;
do not report all photos as analyzed until durable per-photo checkpoints confirm it.

## Metadata-first optimization supersedes repeated vision calls

User then approved metadata-first processing and increased the target to400 photos
within30minutes. The 16-image-call approach above is replaced: active analyze_photo
now calls photo_metadata.extract_metadata once per uncached image, then conservatively
compares every frozen checklist field using image-free lexical retrieval. Cached visual
observations are separate from original EXIF metadata. SHA256/model/prompt-version
signatures and shape validation invalidate stale or malformed caches; schema revisions
rematch without another vision call. Explicit negative observations defeat contradictory
object-list claims. Proposed locations remain high-uncertainty, values null, and require
human review. Synonyms/subtle requested details can be missed; manual assignment remains.

Applied additive migration0024_photo_metadata_cache: PhotoEvidence.analysis_metadata,
analysis_signature and PhotoJob.progress. API/UI accept400/site and enqueue400, still
20 files/request,5MiB/file,24MP. UI distinguishes metadata extraction, checklist matching,
cache reuse and durable completion. Worker records timings/stages and per-photo progress.
Obsolete AI-only proposals become superseded; human confirmations/corrections/rejections
remain. Critical-review snapshots include cached observations/signatures; a field with
400 photos is split into bounded evidence chunks with all source references retained.

Real benchmark on RTX3060Ti8GiB/Ryzen7: first uncached photo12.890s including9.176s
model load, then3.016/3.344/3.015/3.219s. Warm mean3.149s, cached rematch0-16ms.
Private evidence .local/compact-metadata-benchmark.json. All181 fields compared with
one image call per uncached photo and zero image/text calls for valid cached rematches.
This projects~21.2minutes/400 similar photos, not a measured400-photo maximum and not
a guarantee for final critical review or hardware contention. Full30-minute end-to-end
acceptance remains open until a representative400-photo run including review is timed.

Stopped only verified old worker4660 tree and expired its dead lease before migration
and benchmark. Replaced verified launcher29976 tree with34320; live Engineer/Team Lead
checks passed. Existing job2 resumed automatically (attempt3), all78 sources retained;
observed15/78 durably completed at22:37 with no error. Original answer/approval baseline
is still .local/photo-recovery-before.json. No automatic answers or approvals are allowed.

Final metadata deployment verification: job2 completed78/78 at22:40:43, average3.165s
per photo including five initial cached observations (about247s processing attempt).
All78 valid metadata caches and all181-field matching passes are present. Final
launcher19332 replaced34320 only after the job completed; no work was interrupted.
Normal Engineer/Team Lead HTTP verification confirms max_photos400, metadata_ready78,
analyzed78, review_readytrue, per-photo unverified visual observations and job source IDs.
Exact baseline comparison confirms answer_data, section_approvals, review_history,
status and all78 stored source hashes unchanged. Evidence: .local/metadata-recovery-verified.json.

Full core suite205 tests passed in160.451s. Later focused metadata9 and review-scaling2
tests passed (overlap; do not sum these counts). Added tests also cover obsolete-AI-only
proposal supersession and visual-cache changes invalidating critical-review snapshots.
Browser tests covered400 files in20 multipart batches plus one durable enqueue,401
rejection, stage/cache displays, safe untrusted observation text,320/390/1440 widths,
and old failed jobs whose photos were analyzed by a later job. Those retain original
error details but no longer offer redundant retry. Current incomplete failures retain it.
Asset version metadata-first-3. Django checks and migration-drift checks passed.

400-photo30-minute acceptance remains a projection, not a completed400-photo timed
run. Final critical AI review was not automatically requested, approved or shared.

## Product roadmap pilot application on18October2026

User asked to apply E:\Online Storage\OneDrive\Documents\Personal Projects\iSurvix\
Engineering_Intelligence_Product_Roadmap.pdf. Read all36 pages and inspected role/
review diagrams. Retained unchanged source under docs/roadmap; SHA256 verified against
the external original. Full mapping and remaining Stage0-9 backlog:
docs/roadmap/APPLICATION_PLAN.md. Receipt: docs/development/ROADMAP_RELEASE_RECEIPT.json.

Important scope truth: roadmap references a different React/Workers/D1/R2 repository,
main114ccf3/PR129 and later-domain source. This checkout is Django, branch
feat/local-photo-pilot, base596c7c2385013d8712c46171b491edf1edb08568 with substantial
existing local work. No reset/pull/merge/push/hosted publication was performed. Applied
the roadmap's bounded pilot foundation; engineering/commercial/construction execution,
assets, services, finance, professional acceptance and ISO certification remain planned.
400-photo current capacity supersedes the roadmap's historical200-photo reference.

Before changes checkpoint .local/backups/project-checkpoint-20261018-183910. Independent
QA restored the prior224458 checkpoint into .local/qa-roadmap-restore-gfjb0grb only:
SQLite integrityOK, zero FK violations,158 media files and78 original hashes verified.
Receipt .local/qa-roadmap-restore-receipt.json; no live overwrite. Python3.12.10 and native
qwen3.5:4b completion/vision verified; no new image inference was required for this work.

Applied additive migrations0025_roadmap_context,0026_governed_revisions,
0027_inspection_qualification,0028_membership_expiry. New Project.industry,
Checklist.workflow_type/governance_mode/asset_reference/coordinate_reference, PM role
project_manager, explicit review policies, immutable SubmissionRevision/RevisionDecision,
technical template qualifications, findings/events and optional expiring project grants.
Existing records default to legacy flow/Telecom survey and have not been converted.

Five destinations: My work, Projects and sites, Review queue, Reports, Administration.
Scoped industry/project filters and persistent Site context. PM project membership alone
does not grant independent Site reads; assigned L2/L3/Client scope is enforced in pages,
source URLs, exports, AI selectors and signatures. Expired/revoked memberships defeat
legacy primary-project fallback. Admin can invite/grant/manage non-admin PM accounts,
but no actual accounts were created or role-changed by this implementation.

New inspections require independent governance. Explicit Engineer owner, different TL L2,
different PM L3 and named Client if applicable. Creating TL may configure only the initial
draft they actually created; other policy configuration requires scoped Admin/Super.
Policy freezes after first submission. Actual PM must technically qualify the exact
published template/workflow digest; criteria/method/applicability and coordinate provenance
must exist before L1 submit. No actual qualification or signature was fabricated.

Sources freeze project/company/industry, template/criteria, answers/remarks/images,
original manifests, confirmed photo locations, findings/events, coordinate provenance
and review identities. L1/L2/L3 are ordered and bound to the exact revision/digest.
Stale validation/approval blocked; reasoned returns remain possible and create linked
correction revisions. Generic legacy review endpoint cannot sign independent activities.
Open critical/blocking findings prevent release; frozen sources require return before
remedy/retest changes. Findings/events and qualifications retain immutable history.

Client release is separate C1. New independent rejection preserves L3+C1 history and
reopens Engineer correction repeating L1/L2/L3. Legacy rejection behavior stays unchanged.
Client approval checks the frozen digest even with a fresh current token; refusal rolls
back the surrounding transaction. Frozen historic JSON/HTML and manifest-bound originals
remain available to the named scoped Client while current draft library stays private.
Original downloads rehash bytes; corruption409 and missing storage503 are controlled.
Expired/revoked grants remove historic reads too. Routes in governance_urls/roadmap_views.

First full230 tests passed; final full236 tests passed in154.088seconds. Later15-case HTTP
suite passed after frozen-source addition, plus focused missing-file test. Counts overlap.
Tests cover foreign/peer/unassigned/expired/revoked scope, source/hash boundaries, role
substitution/order, CSRF, immutable JSON/HTML, C1 reject/correct/approve and stale rollback,
qualification authority, blocking finding/remedy/retest, CSV review-policy roundtrip,
legacy compatibility and400-photo existing pipeline. Django checks and migration drift clean.
Browser evidence:39 navigation role/view/width cases and15 roadmap detailed views at
1440/390/320, including encoding/null-admin/phone overflow fixes. Synthetic evidence is
not a physical-phone or qualified engineering/customer acceptance claim.

Initial port8000 was down. Started launcher3672, then replaced only its verified tree
after final source changes with hidden launcher19056. Normal authenticated Engineer,
TL, Client, Admin, Super checks passed all five destinations, with403 Administration for
non-admins. Live legacy activity and field workspace still work. Exact comparison with
restored baseline: every old column in7 business tables, all account identities/password
hashes/roles and all78 original byte hashes unchanged; only own sign-in sessions/last-login
bookkeeping expected. Live receipt .local/roadmap-live-verified.json. Jobs2 and3 remain
completed78/78; no native re-analysis, automatic approvals or real task mutations.

Manuals v1.3 dated18October: SoftwareManual14 pages, DevelopmentGuide10 pages, separate
DOCX/PDF with existing green brand. Native Word export used after packaged renderer
reported missingsoffice; all24 pages visually inspected, changed pages full-size checked.
End-user ZIP rebuilt/verified to contain only current SoftwareManualDOCX/PDF, byte-equal
to the final artifacts. Source roadmap/internal guide/credentials/logs excluded. Original
roadmap source is unchanged. No production, full-lifecycle or400/30min SLA acceptance implied.


## 18 October 2026 Super Admin console industry Admins and Quality Control

This update supersedes the earlier broader Super Admin support permissions and the TL/PM sequence for new submissions. Everything remains under F:\iSurvix\iSurvix-Field. Before-upgrade recovery checkpoint: .local/backups/project-checkpoint-20261018-192729. A later verified checkpoint was saved at .local/backups/project-checkpoint-20261018-193411 with 251 source files, consistent database, media and private recovery configuration.

### Administration and industry scope

Migration 0029 introduced IndustryCatalog and the five Super Admin destinations: Dashboard, Industries, Clients, Projects and Sites. The Super Admin role is administration only. Engineering pages, APIs, old aliases and nine operational Django ModelAdmins deny access. Both actual URL configurations retire raw Django admin. The previous console regression run passed 245 tests; three further tests exercise the raw admin restrictions independently.

Migrations 0030_admin_industry and 0031_quality_control_workflow are applied locally. New Admin invitations require an active industry matching the initial project. Acceptance preserves that binding. Only Super Admin can change it through governance_admin_industry, with transaction, CSRF and audit controls. Existing unambiguous Admins were bound during migration: demo_admin01 and demo_admin02 both manage Telecom. Ambiguous existing Admins are marked admin_industry_pending and denied project access until Super Admin assigns an industry. Effective membership and company affiliation remain required. Existing grants are preserved; cross-industry grants cannot become effective for a bound Admin.

Admins can invite Client reviewers and create or assign Engineer, Quality Engineer and Team Lead roles within managed projects. Client organizations in the Super Admin console remain Company records; Client reviewer accounts are separate invited identities. Admins cannot adopt another company's records. Only Super Admin creates company organizations.

### Quality Control and historical review preservation

All new workflow submissions use Engineer -> assigned Quality Engineer -> Team Lead -> Client when required -> Closed. Without a configured Client, Team Lead approval closes the activity. The new role is QUALITY_ENGINEER. Checklist.quality_reviewer and quality_approval are additive fields; no actual reviewer, QC approval or technical signature was fabricated.

The existing rejected activity 1 retains its answers, photos, status and empty QC fields. Admin or Team Lead must explicitly assign a real Quality Engineer through its checklist before resubmission. Assignment records a reason and checks the current timestamp. A Quality Engineer reads assigned evidence and can request internal AI critique, but cannot edit answers, upload photos, share with Client or sign Team Lead approval. Only Team Lead controls optional AI sharing.

QC approval binds the submitted evidence digest. Changed answers, remarks, schema, photos, confirmed locations or relevant site context require fresh QC. Rejection needs a reason and returns work to Engineer. Resubmission clears the current QC gate and retains review history. Existing Final activities and historical approvals are preserved.

New independent policies and submissions use workflow_version 2: L1 Engineer, L2 Quality Engineer, L3 Team Lead and optional named Client C1. Frozen version 1 TL/PM reviews retain their original identities, snapshot digests and decision sequence. Returned historical activities must explicitly adopt version 2 before a new correction submission. Draft/returned reviewer configuration is available through the activity page, with role, scope and stale-version guards. Frozen policies cannot be reassigned. Historical reviewers retain authorized access to their own frozen reports and originals after an upgrade, without current draft access; revocation removes historical access too.

Team Leads can technically qualify templates; historical PM qualifications remain valid records. Finding, remedy, independent retest and optional Client controls are retained. The older /work/assign route now delegates to the authoritative assignment form, including the required reviewer. Bulk CSV templates include quality_reviewer; independent rows use l2_reviewer for QE and l3_approver for Team Lead.

### Verification and documentation

The final full core suite passed 269 tests in 19.302 seconds. MD5 was overridden only inside the synthetic test process to accelerate fixtures; production password hashers are unchanged. Earlier runs loaded fixtures before their QC adaptations and are superseded by this final passing run. Counts overlap and must not be added. Coverage includes industry binding, invitation acceptance, forged fields, audit, CSRF, project boundaries, QC roles and evidence access, AI privacy, stale digests, rejection/resubmission, optional Client closure, historical policy upgrades and frozen-source revocation. Django checks and migration drift checks pass.

Browser evidence covers 18 role/state/width cases plus three existing-policy form widths and synthetic form submission payloads, at 1440/390/320. This is not physical-phone acceptance. Manuals v1.5 retain the green brand: 16-page Software Manual and 12-page Development Guide, each DOCX/PDF. All 28 rendered pages were visually checked. The user documentation ZIP was rebuilt and byte-verified to contain only the current Software Manual DOCX/PDF, excluding internal guides, credentials and the roadmap source.

### Running app and preserved data

Current hidden launcher PID is 9204, started through Start-iSurvix.ps1 -NoBrowser after stopping only the verified previous launcher tree. The app listens on 127.0.0.1:8000 and the independent photo worker runs locally. Internet access remains disabled. Python 3.12.10 and native Ollama qwen3.5:4b completion/vision capabilities were reverified; no new real photo inference was needed.

Normal Super Admin, Admin, Engineer, Team Lead and Client sign-ins passed. All five Super Admin destinations work and engineering URLs return 403. Every old column in seven business tables, existing account identities/password hashes/roles and all 78 original photo hashes matched the prior baseline. Only expected sign-in session/last-login bookkeeping changed. Receipt: .local/super-console-live-verified.json. Jobs 2 and 3 remain completed 78/78; old failed job 1 remains preserved. Release evidence: docs/development/INDUSTRY_QC_RELEASE_RECEIPT.json. The full 400-photo/30-minute target remains unqualified. No production deployment, hosting, commit or push was performed.


## 18 October 2026 Client creation belongs to Admin only and final save

This correction supersedes previous Super Admin Client creation permissions. Only a scoped, industry-bound Project Admin creates Client organizations, links them to managed projects, invites Client reviewers and grants Client project access. Super Admin Clients is read-only. Super Admin may retain administrative maintenance and revocation powers, but cannot create Client accounts, convert roles to Client, issue Client invitations, assign Client organizations or add Client project grants. Old Super-issued Client invitations fail current issuer validation. Actual server routes and retired Django admin forms enforce the boundary, including Profile role/primary-project/company changes and a read-only Project client field.

Applied 0032_client_organizations and 0033_preserve_legacy_clients. ClientOrganization is separate from employer Company tenancy, belongs to a company and industry, records its creator, and can be linked to Project.client_organization. Creation derives tenant/industry from the bound Admin; forged ownership fields do not control access. Project assignments validate tenant, industry and current Admin scope. Optional Client context enters evidence digests when present without rewriting old snapshots.

The user created Company records 2 and 3, Client 1 and client 2, between earlier work and this task. They already existed in the before-change checkpoint .local/backups/project-checkpoint-20261018-193722. Migration 0033 imported their proven historical client meaning into scoped ClientOrganization records with legacy_company provenance, retaining original Company rows, IDs, descriptions, creation dates and actual historical creator. Import required an audited orphan record and a single unambiguous bound Admin company/industry pair. Ambiguous/unproven records remain preserved read-only; no arbitrary owner is inferred. The actual two Clients are now visible to Admin and read-only to Super Admin.

Final full core suite: 281 tests passed in 19.987 seconds, with fixture-only in-process MD5 override; real password hashers are unchanged. Prior 279 passing run preceded legacy preservation migration. Counts overlap. Coverage includes permission/CSRF/forged fields, old invitation rejection, cross-company/industry assignment, raw admin form restrictions, source digest changes, legacy import provenance/preservation/idempotency and existing workflow/photo tests. Django checks and migration drift checks pass. UI evidence: 12 responsive role/page cases and two synthetic POST payloads. Manuals v1.6 are separate green-branded 17-page user and 13-page internal DOCX/PDF; all 30 pages were rendered and checked. User documentation ZIP contains only the Software Manual DOCX/PDF.

Current hidden launcher PID18452; local app and independent photo worker are running at 127.0.0.1:8000. No internet exposure, commit, push or hosted deployment. Live normal sign-ins passed for Super/Admin/Engineer/TL/Client. Super Client-create endpoints are blocked, Clients page has no creation/invitation forms, and Admin administration shows both preserved Clients and its creation form. Read-only exact comparison against this task's 193722 checkpoint verified all old columns in seven business tables, existing account identities/passwords/roles and all 78 original photo hashes. Expected own sign-in sessions/last-login bookkeeping is excluded. Evidence: .local/super-console-live-verified.json and docs/development/ADMIN_CLIENT_OWNERSHIP_RECEIPT.json. User asked to save everything after completion; source, persistent data, manuals, credentials and recovery backup are preserved locally.
