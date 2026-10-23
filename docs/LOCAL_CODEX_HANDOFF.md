# iSurvix Field: local Codex development brief

## Engineer workspace simplification - 23 October 2026

Current work is on `fix/engineer-field-workspace-20261023`, from local checkpoint
`e17a6a3`. Recovery snapshot `.local/backups/project-checkpoint-20261023-182116`
was verified before editing. Git fetch now succeeds: PR13's approved merge is
`origin/feat/secure-outbound-survey-workers` at `b0455521`. No production branch,
operational approval or existing template has been overwritten.

The Engineer interface now has My tasks, Checklist & photos, and Submit & AI
Analysis. Pending, submitted, returned and completed filters use scoped Django
records. The left pane is an expandable Group / Section / Checkpoint tree with
retained selection and a mobile drawer. Optional Civil/Electrical/Tower labels
are tucked away; they are not the checklist's controlling hierarchy. Advanced
matching, site/team details and analysis history remain accessible in compact
expanders. Failed answers survive switching checkpoints and block submission
until saved; unfinished uploads also block submission.

Engineer uploads are upload-only. Checklist-required surveys use the existing
immutable submission/job pipeline; historical retry and critique paths cannot
bypass its submission boundary. The three current operational surveys are not
opted in and retain their existing photo pipeline, now with explicit Engineer
AI submission in the interface. Do not enable Checklist required on historical
published templates to force them into a different workflow. Legacy completion
checks are local to the current browser; durable cross-browser sessions remain
an explicitly documented hardening gap for legacy/excluded workflows.

Accepted AI proposals still require Apply reviewed results and the separate
Send to QA review action, which receives focus immediately after successful
Engineer completion. QA, Team Lead and Client retain their stage/signature,
reason, one-step return, frozen revision and release guards. Client evidence
pages identify submitted evidence and hide the private editable matching panel;
authorized source photographs and original downloads remain available.

Draft checklist developers can move a checkpoint between activity sections
without replacing its stable ID or evidence rules. Existing published/used
structures and survey snapshots remain protected. No models, migrations,
dependencies or product modules were added.

Actual installed Agency profiles under
`C:/Users/Muhammad Assim Baig/.agency-agents` were used: root Orchestrator, UX
Architect/Frontend Developer, Backend Architect, and independent Reality
Checker/API Tester. UI, backend and QA agents had distinct file ownership.
The runtime agents do not imply automation of the separate Agency desktop app.

Verification: the final 828 isolated backend tests passed in 276.207 seconds,
native process exit 0; the receipt, focused results, actual Edge
journeys and screenshots are under `.local/engineer-workspace-20261023`.
Desktop 1440px/mobile 390px journeys exercised upload without automatic AI,
failed-save retention, explicit submission, acceptance/correction, QA approval,
Team Lead rejection back to QA, Engineer revision/resubmission, Client
rejection/clarification, and closure of both three/four-layer tasks. Independent QA ran
23 fresh read-only browser checks and inspected persistence. Browser inference
was controlled; real persistent jobs and PDF/DXF renderers ran on synthetic
records/media. This is not a new native model/whole-site throughput benchmark.
Django, migration-drift, pip, four retained frontend scripts and 31 JS syntax
checks passed. Recheck the final receipt rather than adding overlapping runs.

Data-preservation verification compares 59 core tables, 806 media files and 12
private/config files against the recovery checkpoint: no changes; SQLite
integrity OK. Only the application web process was refreshed on loopback port 8000;
existing workers/jobs were preserved. Current local login is
`http://127.0.0.1:8000/login/`.

The single owner-requested guide is
`output/pdf/iSurvix_User_Permissions_and_Known_Issues.pdf`, with an iSurvix
watermark and six roles' allowed/denied actions plus issues under each role.
Editable source: `docs/manual/USER_PERMISSIONS_AND_ISSUES.md`.
Requirements/evidence: `docs/development/ENGINEER_WORKSPACE_SIMPLIFICATION.json`.
A13's reported Client panel is repaired; A12 native crash diagnosis remains
open. Real-site accuracy/throughput, verified CAD/manufacturer references,
physical-device/intermittent-network, staging HTTPS/worker and restore/privacy
operation acceptance remain open. Do not describe these as production accepted.

Windows: use the existing Start-iSurvix.cmd when port8000 is free. Individual
commands, from the project root (do not start duplicate workers):

```text
.local\venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8000 --noreload --settings=checklist.settings_local
.local\venv\Scripts\python.exe backend\manage.py survey_processing_worker --settings=checklist.settings_local
.local\venv\Scripts\python.exe backend\manage.py photo_worker --settings=checklist.settings_local
.local\venv\Scripts\python.exe backend\manage.py photo_search_worker --settings=checklist.settings_local
.local\venv\Scripts\python.exe scripts\run_backend_tests.py
```

## PR13 local update and scope - 23 October 2026

Owner direction: improve and stabilize the existing survey/inspection, checklist,
evidence, review and drawing workflows. Do not add more product modules.

PR13 is merged into `feat/secure-outbound-survey-workers` as `b0455521`.
The local checkout `update/pr13-local-20261023` uses its approved source
`f76e416`; GitHub's commit comparison confirms no file differences between that
source and the merge. Normal Git fetch failed twice because this PC could not
resolve github.com; no remote branch was overwritten or promoted to main.

Before upgrade, checkpoint `.local/backups/project-checkpoint-20261023-175137`
passed archive CRC verification. The actual database upgrade was rehearsed on a
restored copy before applying migrations 0048-0053 locally. Preflight found zero
legacy PM profiles and zero pending PM invitations. All 53 existing core tables
retain their original rows/column values, and 806 media files plus 12 private or
configuration files retain their hashes. SQLite integrity is OK. Do not migrate
back to 0050: migration 0051 is forward-only; use the verified recovery snapshot
and a reviewed recovery procedure instead.

Current Windows verification: 805 isolated backend tests passed in 271.267 seconds
with no failures/errors/skips and no guarded Python external network attempts.
Django, migration-drift, pending-migration and dependency checks passed; all four
retained frontend scripts and both workflow JavaScript syntax checks passed.
Edge checked all six role workspaces and Engineer/Client photo views at 390px,
with zero JavaScript errors or failed local HTTP requests. Browser records/media
were isolated synthetic copies, not operational approval tests. Private receipts
are under `.local/pr13-local-20261023`.

The earlier native exit139 crash remains unresolved; a passing Windows run does
not establish its cause or close A12. Client read-only wording remains A13. Keep
real-site AI accuracy/throughput, approved drawing geometry/target CAD acceptance,
staging HTTPS/PC worker, recovery/device/accessibility and privacy-operation gates
open. Review potentially affected historical scientific values against original
evidence; do not overwrite signed records. No new modules, production deployment,
operational approvals, password resets or automatic reprocessing were performed.

## Project synchronization - 23 October 2026

The combined review branch is `chore/project-sync-20261023`, based on the saved
`b907601` project. It includes `6cf575d` (hosted role navigation and photo links
when local AI is disabled) and the `c4f77e2` audit/manual amendment, retained as
cherry-pick `8e84b8d`. Existing review branches and pull requests are preserved.
Current verification is recorded in `docs/development/PROJECT_SYNC_20261023.json`.

This synchronization does not resolve the audit findings or establish a production
release. In particular, SI unit case handling, non-ASCII drawing labels, approved
drawing references and full-site AI validation remain outstanding. GitHub `main`
and the deployment are unchanged. Operational data is preserved and migrations
0048-0050 have not been applied to the local operational database by this update.
Use the checkpoint and migration procedure before a normal operational upgrade.

## Release hardening verification — 21 October 2026

The current feature branch is `feat/secure-outbound-survey-workers`, based on the
reviewed `79d9772`. Read `docs/RELEASE_HARDENING.md` and the requirement/evidence
ledgers under `docs/development/RELEASE_HARDENING_*` before using older results.

This release adds private media delivery, audited abandoned-upload recovery,
lightweight progress/lazy details and an authenticated outbound PC worker bridge.
Installed Agency specialists implemented scoped areas and independent QA reviewed
the original requirements, Nginx, concurrency, browser flows and native processing.
The final native PDF/workbook job processed nine sources and produced real draft
PDF/DXF outputs after strict per-source mapping decisions fixed duplicate bindings.

Operational records, uploads, approval state and the original port8000 process were
preserved. Verification used isolated databases/media and loopback services. Before
normal local startup after updating, preserve a checkpoint and review/apply additive
migrations0048–0050. The operational database was not migrated during this task.

Remaining external dependencies are actual VPS access/TLS setup, verified
manufacturer CAD/approved measurements, and a field-reviewed full-site Z93004
benchmark reference. The bounded Z93004 result is not full-site accuracy or sustained
native-throughput verification. Do not merge or deploy automatically.

## Current integration verification - 21 October 2026

Use `docs/development/INTEGRATED_VERIFICATION_REQUIREMENTS.json` and
`INTEGRATED_VERIFICATION_RECEIPT.json` for the current evidence, rather than the
older baseline statements below. Work is on `feat/integrated-survey-verification`.

The existing editor and integrated survey pipeline were repaired and independently
verified. The final core suite passed **666 tests**; Django, migration-drift, pip
and modified JavaScript syntax checks passed. Real browser/native-model checks
completed both three- and four-layer approval routes, including explicit Engineer
application, independent QA, named Client where required and authorised release.
Native crash/restart recovery also completed photo, PDF, workbook cell and embedded
image sources after natural lease expiry. Actual 200-photo browser intake passed;
this is not a sustained 200-photo native-inference benchmark.

Live operational data stayed unchanged: 53 core tables, 806 stored files and 12
private/config files match the pre-change checkpoint
`.local/backups/project-checkpoint-20261021-204352`. Existing published revisions,
approvals, branding and originals are preserved. All approval tests used separate,
clearly synthetic Django records and media. Sample outputs and seven screenshots
are under `samples/drawings/integration-verification-20261021` and
`docs/images/integrated-verification-20261021`.

One runtime follow-up is blocked: automatic approval review rejected restarting
the existing port8000 app and survey worker with **blocked by policy**. That command
did not execute. Preserve those running processes; their imported Python modules
may remain older until a normal permitted local restart. The tested current source
ran in isolated Django instances on8886/8887. No merge, deployment, force-push,
customer approval or database replacement was performed.

Full 378-photo Z93004 plus complete-workbook native timing, field accuracy and
manufacturer geometry remain unbenchmarked/unverified. No approved DWG/DXF/PDF
reference was supplied in that site's source folder. Generic measured envelopes
are explicitly labelled; missing dimensions/unsupported sheets remain visible.
Use the updated `docs/manual/AI_SURVEY_TEAM_GUIDE.md` for exact startup commands.

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


## 19 October 2026 Workflow photo upload submission and approval testing

Resumed clean GitHub commit e9e36a2 on feat/local-photo-pilot. Python 3.12.10, migrations and local app startup were checked. Initial full 281 tests passed. Added six isolated CSRF-enabled HTTP acceptance cases covering multipart original upload, required-photo blocking before confirmed placement, explicit photo location, Engineer submission, QE decision, TL approval, optional Client closure and exact original download hash. Both legacy and independent modes pass with and without Client. Additional cases verify QC rejection/resubmission repeats the gate and a new photo after QC invalidates TL approval until fresh QC.

A deterministic submission interleaving reproduced late individual-photo upload and deletion after Engineer submission. custom_save, custom_upload and custom_photo_delete now recheck survey edit permission inside their transaction after locking the Checklist. The regression exercises late upload, valid answer save and photo deletion. Final full core suite: 288 tests passed in 22.394 seconds, with synthetic fixture-only MD5 override and production password hashing unchanged. Django checks and migration drift checks pass. No schema changes were needed.

Native Ollama initially reported vision capability but returned HTTP500 because its llama-server libraries were missing. Downloaded the exact official 0.40.5 runtime under F and verified archive SHA256/signature and equality with the installed executable. Automatic approval review blocked a separate runtime service launch; no alternate launch was attempted. A safer repair backed up the existing library directory under .local/ollama/original-lib-before-repair-20261019 and restored only matching missing libraries in the original installed software directory. The original executable, listener PID9728/127.0.0.1:11434, configuration and model originals were retained; project data was not moved outside F.

The original existing service then passed real native vision on a synthetic red-square/blue-circle image. scripts/check_photo_pilot.py was updated from obsolete automatic answer-draft expectations to the approved metadata-first contract. Its disposable SQLite/media pilot passed multipart upload, byte-preserved original export, native worker job 1/1 completion, valid compact metadata, proposed location, explicit human confirmation, required-photo coverage and report export. No automatic answers or approvals were applied. No real project photos were analyzed. Logs: .local/workflow-final-20261019.log, .local/native-photo-pipeline-20261019.log, .local/ollama/runtime-diagnosis.json. Receipt: docs/development/WORKFLOW_TEST_RECEIPT_20261019.json. The full 400-photo/30-minute target is not proven by these checks.

The app was restarted with only its verified launcher tree, current hidden launcher PID31060, local app and photo worker running at127.0.0.1:8000. Normal existing Super/Admin/Engineer/TL/Client sign-ins passed after the fixes; seven business-table original columns, existing account identities/password hashes/roles, existing approvals and all78 photo hashes were preserved. New tests and the transaction fix are saved locally; they have not been pushed to GitHub during this testing task.


## 19 October 2026 Role layout and palette chooser

Added standalone static prototype at http://127.0.0.1:8000/static/core/design_lab/index.html. Files: backend/static/core/design_lab/index.html, style.css and app.js. These do not change live application templates, authorization, workflows, accounts or records. All preview data and illustrated evidence are synthetic.

Six distinct role defaults: Super Admin command center/midnight violet; Admin portfolio canvas/teal-coral; Client editorial report/soft plum; Team Lead split workbench/charcoal-orange; Engineer field companion/blue; QA Engineer evidence ledger/forest-lime. Every role can independently select any of six layouts and six palettes. Controls include desktop/phone preview, Compare all roles, Keep this design, a visible kept-selection summary, Copy my choices with selectable fallback, one JSON download and confirmed reset. Choices persist in the current browser under isurvix-design-lab-v1; selection does not apply a theme to the actual app. Codes identify each role/layout/palette for later implementation.

Role previews follow the current permission boundaries, including read-only Super Admin Clients, industry-bound Admin Client management, Engineer capture/submission, assigned QA quality review, Team Lead approval after QA with optional AI sharing, and Client release. Mock controls announce preview-only actions and send no backend writes. No project photos or credentials are exposed.

Headless Edge passed 90 role/responsive/layout/palette cases, plus persistence, phone toggle, compare, copy, six-role JSON export, reset and denied-storage feedback; no browser exceptions. Tested widths1600/390/320. Comparison thumbnails resize to fill their cards. Screenshots and test helpers are under .local/design-lab-qa; receipt docs/development/DESIGN_CHOOSER_RECEIPT.json. No source changes were pushed or rolled into production views. User should open the chooser, keep a design for each role and paste Copy my choices into chat before applying chosen designs.


## 19 October 2026 Applied user selected role layouts

User confirmed Super Admin S1-6 Command center / Forest and lime, with Admin A6-2, Client C6-2, Team Lead T6-2, Engineer E6-2 and QA Engineer Q6-2 all using Evidence ledger / Teal and coral. These selections are now applied to the working local app, not just the prototype. Record: docs/development/SELECTED_ROLE_DESIGNS.json.

core.local_ai.local_context provides role_design {role,label,layout,palette,code} using the actual access.role_for account identity. Super receives command/forest; the other five selected roles receive audit/teal. Anonymous, inactive, locked, forged Super profile labels and unselected historical PM accounts receive no descriptor. A label or legacy session claim cannot grant a design or role authority. Primary navigation no longer uses a raw Super profile label to select Super chrome.

base.html and _primary_navigation.html now provide the selected body attributes, a desktop left sidebar and in-flow collapsible mobile navigation. role_layout.css and role_layout.js apply shared palettes, readable type, squared ledger panels and accented rows, with the separate forest Command center for Super. Existing routes, form IDs, CSRF, upload controls, project scope and review actions are retained. Existing System/Light/Dark preferences remain usable through synchronized appearance controls. New assets use selected-designs-1 cache keys.

Mobile photo pages put the active capture workspace before the site catalog. Site context is an accessible collapsed details panel on phones and open on desktop, retaining its inner IDs. Logout remains text-labeled even when external icon fonts fail. Non-Final read-only checklists now say Read-only view instead of incorrectly saying Approved record; Final retains that label. Internal prototype design codes remain in data attributes, not the live sidebar text.

Four new role-design/permission tests pass. Final full core suite: 292 tests passed in24.391seconds, with fixture-only MD5 override and unchanged production hashers. Django checks and migration drift checks pass; no migrations were added. Headless Edge checked17 actual rendered role pages at1440/390/320 (51 cases), plus12 mobile light/dark appearance cases, all passed. Fixtures use a private SQLite database and media in .local/selected-layout-qa, including real synthetic API JSON and photo URLs. Source-bound controls remain intact: Engineer capture inputs, named QA decisions, TL review after QC and Client read-only deliverables. Existing full photo/approval regression coverage is included in the292.

Stopped only the verified previous launcher31060 tree and started hidden launcher32324 through Start-iSurvix.ps1 -NoBrowser. App and independent photo worker are running at127.0.0.1:8000. Live normal Super/Admin/Engineer/TL/Client sign-ins verified their exact selected design codes, normal navigation and Super engineering403. Existing seven business-table original columns, accounts/password hashes/roles, approvals, Client1/client2 records and all78 original photo hashes are unchanged. No new real users, photos, review signatures or jobs were fabricated. No GitHub push or public hosting was performed during layout application. The standalone chooser remains available under/static/core/design_lab/index.html for future exploration.


## 19 October 2026 Compact enterprise task and inspection workspace

User's latest navy/white/blue compact enterprise direction supersedes the earlier forest/teal presentation choices. Existing Django/plain CSS/JavaScript stack and real scoped records retained. local_context now emits enterprise/navy/enterprise-1 for the six active roles; descriptors never grant authority. Header has permission-scoped module/project selectors, collapsible navigation, review-queue link, working help and user/logout menus. Super remains administrative only. Module hierarchy is Telecom Survey/Inspection and Construction Inspection when permitted projects exist.

New /governance/tasks/ (task_explorer; governance_tasks alias) unions scoped checklists and unlinked assignments in the database, paginates25 before per-row workflow display, filters/searches real fields, has clickable stored-status counters/module tabs, sorting, sticky task identifiers, browser-persisted column visibility and selected/filtered CSV with formula escaping and scope revalidation. No fake contractor/due date/site-name fields. Schema-backed tasks open the local photo workspace; separate review link uses the existing legacy or independent decision route. Assignment without checklist remains clearly read-only. Super cannot open or export operational tasks. Clients' personnel restrictions are preserved.

/local/photos/<id>/ is now a searchable, expandable resizable checklist/evidence split pane. Saved item results are distinct from evidence coverage and workflow stage. Checklist items link to the exact existing custom form field. Main source viewer supports previous/next/zoom/fit/metadata and36-at-a-time lazy thumbnail loading, keeping selected evidence separate from AI suggestions. Drawer/Escape on phones, keyboard resize, selected item/photo/scroll restoration and existing upload progress/retry/queue/mapping controls retained. Existing metadata now includes stored uploader and upload date; missing capture/GPS remain explicitly missing. No photo comment field or destructive original-delete API was invented. Existing photo mappings/confirmation and approval APIs remain authoritative; superseded AI placements are excluded from active item grouping. Review decisions stay in existing authorized forms; partial approval is offered only by workflows that already support it.

Shared enterprise.js validates return_to strictly against same-origin /governance/tasks/, stores context per user/task through existing POST redirects, propagates same-record links and restores filtered-list scroll. Enterprise photo context defaults collapsed to prioritize the evidence viewer; explicit expansion remains usable. No schema or migrations added, no real approvals or photos fabricated. Recovery checkpoint before edits: .local/backups/project-checkpoint-20261019-123029.

Validation:301 core tests passed24.273s, including existing CSRF/photo upload/submission/QE/TL/Client flows, new task scope/CSV and shell contracts. Test-only MD5 override; actual password hashing unchanged. Django check and migration drift passed. Browser QA evidence in .local/enterprise-layout-qa/browser-receipt.json covers22 actual private rendered pages at1440/390/320, safe return context, external URL rejection, and205 genuine synthetic private photos with paged thumbnails/navigation/search/zoom/drawer. This is not a400-photo inference timing benchmark. Receipt docs/development/ENTERPRISE_WORKSPACE_RECEIPT.json records scope and gaps.

Verified exact previous launcher32324 tree before stopping; new hidden launcher31284 runs current app and independent photo worker at127.0.0.1:8000. Python3.12.10, installed qwen3.5:4b reportsvision and existing worker capability gate retained. Native Ollama listener was not replaced. Normal Super/Admin/Engineer/TL/Client sign-ins and operational task pages passed. Read-only comparison with this task's checkpoint verified seven original business tables, account identities/password hashes/roles, existing approvals and78 original photo SHA256 values unchanged. Evidence .local/enterprise-live-verified.json. No GitHub push or public hosting during redesign.


## 19 October 2026 Super Admin window choices, professional profiles and official logo

User dislikes long Super Admin scrolling and requested five clean compact proposals with internal panel scrollbars and action-icon hover explanations. New /static/core/super_admin_choices/index.html provides SA-01 Window grid(recommended), SA-02 Tabbed desk, SA-03 Master and detail, SA-04 Command rail and SA-05 Focus board. Same navy/white/blue palette, People & invites/Industries/Clients/Projects/Sites/Audit, real hover/focus tooltips, keyboard/touch, desktop/phone/compare, browser-local Keep/Copy choice. It is explicitly synthetic preview only: no backend requests/writes or applied layout change. Current Super page links Compare5compact layouts. Clients remain read-only and operational signatures are excluded.54 chooser browser checks passed including bounded desktop document/internal scroll, all widths1440/390/320, tooltip hover/focus, persistence/copy and all tabs/focus-board keyboard activation. Evidence .local/super-admin-choices-qa/receipt.json.

User also requested profiles for every role and extra Engineer/QA professional experience visible to Clients. WorkProfile/ProfessionalExperience are separate additive models, migration0034 applied after verified pre-migration checkpoint .local/backups/project-checkpoint-20261019-125201. Authentication Profile and existing role rules unchanged. Self profile /governance/profile/, directory /governance/people/, detail /governance/people/<user_id>/. User menu now provides My profile and Work profiles (directory not offered to Super). Publication defaults off, self editing allowlists professional display name/headline/bio/publication. Engineer/QE can add/edit/delete own organization/title/dates/current/summary/qualifications; dates and ownership validated. Shared work information is self-reported, never an engineering approval. Every other-person read rechecks active/unlocked accounts, same company and active accessible-project intersection. Clients discover only published Engineer/QE/TL/Admin staff, never Super/other Clients. Unpublish/revocation/expiry removes access. Login usernames, emails, password/contact fields are not included in public professional content; empty name falls back to full name or Project team member. Audit stores publication/experience IDs, not private body text. Self GET lazily creates an empty professional row; no experience is fabricated.

User supplied new logo from E:/Online Storage/OneDrive/Documents/Personal Projects/iSurvix/Company Documents/General/765f753c-6a28-4662-bdfe-46622ab933ba.png. Copied byte-identically into F project at backend/static/core/img/isurvix-logo-20261019.png SHA256982a4851d3a09527ffeb3615aec47f39d5c0032830520db6fbce679596e0a202. Header/sidebar/login(via base), legacy home and new five previews use it with object-fit contain/white background; no image cropping/generation or source modification. All project assets/data remain F.

Validation:309 full core tests passed26.100s with synthetic process-only MD5 override, eight focused profile authorization/CRUD/privacy/CSRF tests and four Super console tests. Django checks/migration drift pass. QA rendered12 private profile/login pages at1440/390/320, verifying logo load and clipping; Add experience contrast corrected. Live normal Super/Admin/Engineer/TL/Client sign-ins, self profiles and allowed directory pages passed. Old seven business tables, identities/roles/password hashes, approvals and78 original photo SHA256 values remain unchanged against pre-migration checkpoint. Five live self GETs create only authorized blank profile rows, no experience or publication. Evidence .local/profiles-logo-live-verified.json and docs/development/PROFILES_LOGO_AND_SUPER_CHOICES_RECEIPT.json. Verified previous launcher31284 tree before stop; current hidden launcher35804 runs app plus photo worker127.0.0.1:8000. Native Ollama unchanged. No GitHub push, new public hosting or change to approval controls.


## 19 October 2026 Metadata -> checklist -> one-step links and applied SA-02

User requested metadata-first matching, auto suggested photo/checkpoint connections, a single dropdown confirmation workflow and a compact overall view. Existing native metadata extraction/cache was retained. photo_metadata.match_metadata now uses field labels plus optional description/help/question/instructions as subject anchors; section/type/upload group only provide context/ranking, never image proof. Generic words alone/absent defects/unsupported measurements still cannot create links. Unique strongly anchored candidates may have medium advisory lexical strength; multi-target candidates stay uncertain. METADATA_VERSION stays compact-vision-v1 so existing valid cache is reused. MATCHER_VERSION catalog-context-v2 plus per-job progress matched_photo_ids distinguish actual new matching from old completed jobs; no migration was required.

Photo state exposes analysis.workflow metadata-ready/pending, suggested/confirmed/manual/rejected, unmatched/multiple candidates and recommended cached-rematch source IDs. No old job is relabeled as reprocessed. New visible compact3stagebar+20-row paged table provides one combined section/item dropdown per photo, explicit reviewed selection and one batch confirmation action. Up to100 mapping decisions/request, source/proposal fingerprints rechecked after refresh, active-worker guards, low/ambiguous candidates never auto-selected, truthful partial-success reporting. Existing extra AI alternatives and all human links remain preserved; Advanced links retains explicit atomic correction/removal. Match saved metadata uses existing durable enqueue and validated cached observations, no new AI service. Upload remains visible, source/viewer side by side at wide widths, advanced metadata/mapping/coverage/job/draft details collapsed, lists bounded. A photo location is separate from checklist result or approval. No real78photo reanalysis/rematch was performed.

During implementation user explicitly chose SA-02 / Tabbed desk / navy white blue / compact internal scroll. Applied to actual Super Admin console, not just prototype: data-super-design SA-02, new super_tabbed_desk.css/js, main bounded workspace plus recent12 actual audit events in its own scroller. Dashboard local tabs People/Invite account/Admin industries/Project access/Invitations/Overview. All other administrative views retain real forms in internally scrolling tab panels; current Clients remain read-only. Actions are compact icons with hover/focus labels and preserved CSRF/confirmation handlers. Keyboard tabs/Home/End work; invalid form panel opens automatically. Mobile global nav can open without pushing the active panel outside the viewport. Shared role_design descriptor remains enterprise/navy/enterprise-1; console-specific selection is data-super-design SA-02. SELECTED_ROLE_DESIGNS.json now marks historical choices superseded and records current Super SA-02. governance_views adds Super-only limited recent_audit; Super can_client_approve flag is false. Invalid Super invitation errors correctly return to dashboard invite panel rather than Clients. No authority change to engineering decisions.

Validation:319 core tests passed26.909s with synthetic process-only MD5 override and unchanged real hashes. Three independent acceptance tests cover true mocked-native metadata/cache/worker/proposals/explicit confirmation, preserved human choices/reruns and100-success+1-failed atomic request accounting. Native qwen3.5:4b reports vision, checked before a real native disposable one-photo pilot; metadata/schema, original hash, explicit link confirmation, unchanged answers/approvals and completed job all passed. Native log .local/compact-metadata-native-pilot.log. QA private205-photo actual cached worker completed205/205 without native calls;9 compact browser cases cover layouts, single dropdown, worker/uncertainty guards,205 cached queue IDs and118 reviewed choices where100 saved then18 simulated request failures remain pending truthfully. SA-02 browser30 cases cover5views+invalidinvite at1440/390/320, six local panels, audit scroll, actual hover/focus tooltips/keyboard and nav-open viewport bounds. Receipts .local/compact-photo-qa/receipt.json and .local/sa02-live-qa/browser-receipt.json. No400-photo fresh-inference timing claim.

Verified previous launcher35804 tree before stopping; current hidden launcher22892 runs app and independent photo worker127.0.0.1:8000. Native Ollama unchanged. Live Super/Admin/Engineer/TL/Client sign-ins/navigation/profile pages and actual SA-02 markup passed. Read-only exact comparison with prechange checkpoint .local/backups/project-checkpoint-20261019-125536 verified seven old business tables, identities/password hashes/roles, approvals and78 original photo SHA256 values unchanged. Evidence .local/sa02-metadata-live-verified.json. No GitHub push/public hosting/schema migration in this task. Documentation receipt docs/development/METADATA_CONFIRMATION_AND_SA02_RECEIPT.json.


## 19 October 2026 Bottom-left appearance, ten color schemes, layout locked

User requested System appearance at bottom left with10 color schemes and a locked layout. Added a single authenticated-role control in base.html outside the sidebar so it remains reachable when navigation is collapsed/on phones. #appearance-toggle opens #appearance-panel with System/Light/Dark mode (#role-appearance) and10 keyboard-radio schemes: Navy(default), Teal, Forest, Slate, Violet, Indigo, Azure, Charcoal, Terracotta, Olive. Appearance exposes colors only; SA-02 Super Admin layout and operational workspace structures stay fixed. The former live Compare5compactlayouts link is removed, while historical static prototypes remain unlinked and cannot apply live layouts. Page-level theme selects were removed from operational/admin/template/invitation pages. Footer has constant60px clearance so the fixed button does not cover username text.

New appearance.css changes palette variables and component colors (header, surfaces, labels, links, inputs, task sticky cells/counters, photo tree/matching and profile content) without changing page/pane geometry. Only the new floating control defines its own fixed position. Existing role_layout.js yields mode ownership to appearance.js after retaining navigation/context setup. Removed the old unguarded photo-theme select code from photo_workspace.js; its absent element would otherwise break photoWorkspace initialization. Cache keys bumped to appearance-1. System follows OS mode; explicit mode is not overwritten by the legacy listener. Preferences are JSON localStorage per authenticated username under isurvix-appearance-v1:<encoded username>. Allowlisted scheme/mode defaults, graceful denied-storage feedback, Escape/focus return/outside close and keyboard radio arrows supported. No backend preference writes, account changes, schema/migrations or new dependencies.

Focused role/SuperHTTP13 tests passed1.450s using synthetic process-only MD5 override; actual hashes unchanged. Django check, JS syntax and75-file strict UTF8 checks pass. Browser evidence .local/appearance-qa/receipt.json verifies10 schemes in light/dark at desktop/mobile across roles/tasks/photos/profile, invariant header/sidebar/pane/table geometry, modes/persistence/keyboard/System/storage denial, actual photo API initialized and popup fitting320px. Dark photo count contrast and bottom-left footer overlap found during QA were corrected. Receipt docs/development/APPEARANCE_RECEIPT.json. No real photos were processed.

Live template caching required app restart: verified launcher22892 tree and confirmed0queued/running photo jobs before stopping. Current hidden launcher35524 runs local app and independent worker127.0.0.1:8000; native Ollama unchanged. Normal live Super/Admin/Engineer/TL/Client sign-ins read-only checked central controls, absence of duplicate selectors/layout picker and preserved SA-02. Against prior verified checkpoint .local/backups/project-checkpoint-20261019-130716, exact seven old business tables, existing account identities/roles/password hashes/approvals and78 original photo SHA256 values remain unchanged. Evidence .local/appearance-live-verified.json. No GitHub push or internet exposure.


## 19 October 2026 Header navigation and checklist wayfinding

User explicitly requested blue navigation tiles in the header, a second task heading, left-side checklist and the same clearer layout across the app. This supersedes the prior sidebar geometry while Appearance remains color-only. Shared permission-scoped header navigation now replaces the global sidebar. Engineer has My tasks / Projects & sites / Reports; other roles retain their permitted links. Human-readable titles and context headers link back to the filtered task list. Super SA-02 local administrative panels remain; its duplicated category bar is hidden because the same links are in the header.

Custom checklist answers now open by default; section evidence is an explicit alternate view. Desktop sections stay left, mobile uses a keyboard-accessible drawer. Template, site and workflow history details start collapsed; existing QE/TL decision forms remain outside those wrappers. Footer feedback/actions clear the bottom-left Appearance button. Existing upload, review, workflow and permission APIs are unchanged. No schema change or new dependency.

Validation: 24 focused role/Super/photo upload/approval tests passed; 330 shared-header browser cases and 12 custom-checklist cases passed across desktop/390/320 widths and applicable modes. Browser checks used private real Django-rendered fixtures with no operational writes. Live five-role sign-ins passed; seven original business tables, account identities/roles/password hashes and all78 original photo hashes match checkpoint20261019-131915. Receipt docs/development/HEADER_NAVIGATION_RECEIPT.json. No GitHub push or external hosting.


## 19 October 2026 Separate two-photo metadata matching queue

User asked for photo analysis first, then checklist interpretation/comparison and proposed connections, with unmatched photos parked separately in tiles of two and duplicate displays removed. Existing backend already observes each source through the vision-capability gate, caches visual metadata, then compares it against frozen checklist labels/descriptions/context and stores proposed placements. Matching is existing deterministic lexical/context retrieval, not an added second LLM reasoning call. The order is per photo, not a global all-photos-first phase. No new service, schema or live analysis run was introduced.

Photo workspace now has four clear stages and a separate Needs matching queue, two source cards per page, two columns desktop/one mobile. Each card has preview, saved observations, one section/item selector, advisory match status and explicit reviewed confirmation. Sources deduplicate by source ID in this view; existing per-checklist raw-SHA256 upload dedup and unique photo/field mappings remain authoritative. The evidence viewer and advanced history start collapsed, opening when a source is inspected. Confirmed/manual/rejected decisions and original photos are preserved. Ambiguous proposals require deliberate choices; active-job and stale-schema guards remain. This does not approve answers or sections.

Validation:18 focused metadata/confirmation/upload/approval tests passed2.747s,17 browser interaction cases passed with zero operational writes at1440/390/320, and live five-role/header/photo-page checks passed. Seven original business tables, account identities/password hashes/roles and all78 original source hashes match checkpoint20261019-131915. Evidence docs/development/PHOTO_MATCHING_TILES_RECEIPT.json and .local/photo-tiles-qa/. Existing342 header/checklist browser cases and24 focused navigation tests are recorded separately. No GitHub push or internet exposure.


## 19 October 2026 Raised tactile buttons

User requested all buttons appear visually 3D and depress on click. Shared button_depth.css is loaded last in base.html (raised-1). Native buttons and submit/reset inputs, styled action links, header tiles and upload labels use subtle inset highlights, a raised bottom shadow and a2px pressed translation without changing layout dimensions or action handlers. Existing palette/background colors remain. Disabled controls have subdued shadows and no press behavior; keyboard focus, reduced-motion and print rules included. No schema, backend or data changes. Six private browser cases passed at1440/390/320 in light/dark, checking real pointer press, keyboard focus and disabled style with no operational writes. Receipt docs/development/BUTTON_DEPTH_RECEIPT.json.


## 19 October 2026 AI Analysis progress and manual mismatch dialog

User requested AI Analysis wording in the front end, actual progressive status with matched/mismatched counts and a manual matching window. Photo-workspace presentation now avoids the internal technical term, including stored proposal reasons, tooltips and error wording. New ai_analysis.js uses durable analyzed IDs when idle and actual completed/total with the reported matching stage for the current active batch. No timer invents progress; queued/failed states remain explicit. The active batch is labeled, site-wide matched/mismatched/pending/confirmed counts remain separate. Matched counts unique source IDs with proposed/confirmed/manual links; mismatched counts only analyzed sources with no active link, never pending photos.

Mismatched opens native keyboard-accessible dialog with two independent searchable/scrolling tables: checklist points and unmatched photo thumbnails. Select both then explicitly confirm. Uses existing mapping API action manual, schema digest and fresh preflight; active jobs, changed schema, locked fields and no-longer-unmatched sources block writes. Read-only users can inspect but cannot confirm. Errors preserve selections; success refreshes counts; missing photos show a genuine missing-evidence message. No schema or AI integration change.

21 private browser cases passed at desktop/390/320, including synthetic request-spy success/error, guards, progress/counts, independent scroll and keyboard focus; zero operational writes.18 focused backend regressions passed; later complete327 core tests passed25.751s with in-process synthetic MD5 override only. Read-only comparison with135339 observed concurrent user changes to checklist1 answer_data/updated_at and photo-processing records; these were preserved, never reset to an earlier checkpoint. Recovery checkpoint140924 includes that work. Receipt docs/development/AI_ANALYSIS_PROGRESS_RECEIPT.json.


## 19 October 2026 Editable survey identity and photo capture prefills

User requested surveyor from the user account, organization from the Admin/company, survey date/time/location/site ID from available photos, and eventual mandatory profile completion while retaining manual development entry now. field_intake_service.survey_prefill_suggestions/site_information_fields derive unsaved defaults from the assigned checklist.user full name (professional display-name fallback), actual project.company, assigned project name, valid photo capture dates/times and GPS. Dates must agree on a capture day; earliest actual clock time is offered without inventing timezone. GPS must agree at six decimals; differing positions/dates remain blank with conflict notes. Region/city, engineering dimensions and other absent facts are never guessed. Explicit full-line Site ID/Code text from current hash-bound analysis is suggested; system assigned site identity is never changed by a photo or filename. Original photo details and files remain untouched.

Existing answer keys, including explicit blank/None/zero, always win. Approved/frozen/locked values are retained. Additional field keys stored_value, prefilled, suggested_value, suggestion_source/note/conflict support provenance. Both custom checklist and photo site-information pane show defaults with source/review hints. Save autofilled details or Save and submit collects only unsaved defaults plus user edits through existing validated APIs; no opening/GET causes a survey save. Photo-pane Save includes existing expected_updated_at. New photo-state defaults refresh only when no dirty manual input exists. Client/read-only views display saved values, not inferred replacements. Professional profile page explains identity/company origin; mandatory completion is deferred during development as requested. No schema/migration or AI service change.

Validation:327 full core tests passed25.751s, including8new prefill/integration tests and8intake regressions; actual custom GET tests cover absent defaults, explicit clears, SUBMITTED/FINAL read-only fields and unchanged updated_at/answers/review history.24 private browser checks passed at1440/390/320, covering both forms, provenance, default/manual values, zero initialPOSTs, explicit save payloads, stale-update token, dirty-input retention and footer/Appearance reachability. Six synthetic-spy save calls only; zero operational writes.21AIAnalysis browser cases also reran successfully on final JS. Live normal five-role sign-ins plus Engineer custom/photo pages passed. Compared with recovery checkpoint140924, seven business tables, account identities/roles/password hashes and all78 original photo hashes remain equal. This comparison preserves the concurrent user changes documented in the previous entry. Current hidden launcher14576 runs app/worker127.0.0.1:8000, native Ollama unchanged;0activejobs confirmed before restart. Receipt docs/development/SURVEY_PREFILL_RECEIPT.json. No GitHub push or public exposure.


## 19 October 2026 Owner-authorized clean two-checkpoint trial and rectification feedback fix

User explicitly requested removal of operational data and a fresh trial with two checkpoints and two photos because submission/rectification appeared broken. Read-only diagnosis: old Checklist1/Test1 was REJECTED with required answers complete, but quality_reviewer wasNULL and no QE account existed. The mandatory QE gate correctly blocked resubmission. No approval controls were removed. Separately, QE rejection reason was recorded only in quality_approval/history.reason while Engineer feedback displayed checklist.comment: quality_workflow now records comment/comment_by on rejection. base.html now renders accessible typed Django messages once above content and scopes child message loops empty to avoid duplicates. Submission failures are visible.

Stopped verified launcher14576 tree and saved verified recovery checkpoint .local/backups/project-checkpoint-20261019-142515. A fresh migrated database/media was staged under .local/clean-two-point-20261019-142515-v2 and validated before installation. Kept all18 existing account usernames/password hashes/roles/company/industry bindings and professional profiles; old operational projects, templates, checklists, answers, jobs, placements, decisions and history are absent from the fresh live dataset. Original DB and media are retained as retired-survey.sqlite3 and retired-media inside the checkpoint, in addition to the verified recovery ZIP. Install had rollback protection; Windows open-handle checks were resolved before final successful swap. No old source/approval/photo file was permanently deleted.

Live: one project Two-checkpoint workflow test, one TEST-SITE-001 DRAFT/PENDING task, exact two required inspection fields (Site identification sign condition; Tower structure and ladder condition), each requiring confirmed evidence, and exact two original photo copies from archived sign/tower sources. No answers, mappings, jobs or approval decisions seeded. Main accounts demo_eng01 / demo_lead01 / demo_client01 / demo_admin01. Created demo_qa01 through the normal Admin invitation/acceptance flow and assigned explicitly to the task. Existing accounts retain passwords and role authority; primary project grants were reset for the small trial. Client review is required after QE and Team Lead; Client draft access remains hidden. Private credentials and click-by-click testing instructions: .local/TWO_CHECKPOINT_TEST_GUIDE.md and .local/two-checkpoint-test-accounts.json. Do not copy passwords into source documentation.

Full328core tests passed26.350s. Eight actual disposable-browser workflow cases passed upload→submit→QE return→Engineer edit/resubmit→QE approve→TL approve→Client complete, including visible required-field errors and rejection reasons. Seven additional HTTP acceptance checks against an exact private copy of the fresh seed passed with CSRF enforced, including photo_required evidence gating and final closure; zero native inference calls and no live operational writes. Ten live credential HTTP checks and four actual desktop/mobile browser cases passed. Post-QA live state remainsDRAFT with2photos/0placements/0jobs/19accounts. Hidden launcher36376 runs app/independent worker127.0.0.1:8000; native Ollama unchanged, vision gate retained. No schema or GitHub push. Receipt docs/development/TWO_CHECKPOINT_RESET_RECEIPT.json. Earlier preservation assertions against the previous dataset are now historical and must not be rerun unchanged after this explicitly authorized reset.


## 19 October 2026 Explicitly requested two-photo checkpoint linking

After the user completed AI Analysis and saved two inspection answers, live coverage had an unassigned sign photo and an unconfirmed tower suggestion. User explicitly requested linking using saved observations or other solid evidence. Both current hash-bound AI observations and the actual previews were inspected. Photo1 clearly shows the site identification sign/label; photo2 shows tower structure and access ladder. Backed up the current database privately before linking. Through normal Engineer credential sign-in, CSRF and schema-checked mapping API, manually linked photo1→site_identification and confirmed the existing photo2→tower_structure proposal. No original, saved inspection answer, workflow status or approval was changed; no new inference or submission. Live task remainsDRAFT with2/2 required evidence slots covered and missing_required=[] as verified after the requests. This explicitly authorized action supersedes the earlier zero-placement test-state description. Receipt docs/development/TWO_PHOTO_LINKING_RECEIPT.json and .local/photo-links-confirmed.json.


## 19 October 2026 Preserve findings and investigate stronger photo/checkpoint validation

User requested retaining the current findings and investigating stronger rules/methods. Read-only source audit and primary-documentation research completed; no application code, template snapshot, observation cache, photo link, answer, approval or task status was changed. The two source originals match stored hashes; one manual sign link and one confirmed tower link remain intact. Private snapshot .local/research/confirmed-findings-20261019.json preserves source hashes, observations, schema, links, answers and decisions. Main research record docs/development/STRONGER_EVIDENCE_MATCHING_RESEARCH.json; proposed phased rules appended to docs/FIELD_PHOTO_WORKFLOW_PLAN.md.

Concrete current weakness: procedural instruction tokens inflate the matching denominator and visible Site ID text is excluded from anchors. Subject-specific label rules plus literal identification labels can improve candidate retrieval without another image call; broader semantic retrieval/OCR/QR/targeted vision need separate implementation and field validation. An in-memory2-photo/3-negative demonstration passed its illustrative conditions only; not a calibrated accuracy benchmark. No new dependencies/models or cloud service were introduced, and no inference or live operational writes ran. Human matching, evidence sufficiency, and engineering pass/fail must remain distinct. Cache/400photo support still does not establish the30-minute end-to-end target.


## 19 October 2026 Shared, versioned evidence analysis and controlled learning

Implemented the researched operational rules: subject-first checkpoint retrieval with contradiction/negation guards; strict optional evidence requirements per published template field; local RapidOCR text extraction with region/confidence provenance; local OpenCV QR decoding without following payload URLs; original capture-time/GPS context and blur/resolution indicators; local BGE semantic retrieval; bounded verification of ambiguous candidates using the existing vision-capable Ollama model. Numeric answers, measurements, N/A, inspection pass/fail and workflow approvals remain human-controlled. The optional later object-grounding model was not introduced.

New immutable evidence records are scoped to company/project/activity/site/source hash/frozen schema, actual model-file digest, tool/source/model-weight fingerprints, prompt/rule versions and explicitly adopted correction release. Source bytes and saved payload integrity are checked. Observations are reused across rule updates; unchanged complete assessments are reused without more inference. All authorized operational users receive the same saved findings. Historical observations are archived, not represented as digest-verified new results. The saved-analysis panel distinguishes historical versions; the evidence JSON report carries provenance. Independent submission snapshots bind saved evidence provenance.

Human photo confirmation, manual reassignment and rejection now capture pending correction examples. A different assigned QA Engineer or Team Lead must review an example. Publication creates an immutable project release, and applying it is explicit. Exact-source corrections affect suggestions only; similar-photo examples are retrieval hints for another visual check. Intrinsic evidence/contradiction guards remain enforced. This is controlled reference learning, not model-weight fine-tuning. Previously saved answers, confirmed/manual/rejected links, approvals and original photos are preserved. Active photo processing blocks submission/review gates.

The final critical-review layer reuses canonical findings across users for the same source snapshot and model/prompt version. Retry-only duplicate drafts do not change engineering inputs. Client visibility still requires Team Lead sharing of a current completed review. Immutable review bindings expose canonical provenance.

Runtime: Python3.12 local environment; RapidOCR1.4.4, OpenCV5.0.0.93 and FastEmbed0.9.0 installed in the F-drive venv. Semantic weights are under .local/models/embeddings, runtime downloads disabled. Reprovision using scripts/setup_evidence_models.py after installing backend/requirements.txt. Migrations0035 and0036 are additive. No cloud photo service or new Ollama service was introduced. Native Ollama remains external and unchanged.

Native two-photo validation: OCR succeeded on both sources; QR decoded on photo1. First complete versioned job2 processed2/2 in approximately141seconds on the currently CPU-only Ollama runtime. Both intended checkpoint matches were supported and both cross-matches remained insufficient. This is a functional probe, not an accuracy or400-photo timing benchmark. The400-photos/30-minute target is not demonstrated on this runtime. Final verification and preservation results are recorded in docs/development/VERSIONED_EVIDENCE_RECEIPT.json.

Final acceptance:382 core tests passed28.556s;12 desktop/mobile browser checks passed. Live final-version2/2photo run and four-role identical saved-record comparison passed. Cached replay of both photos completed0.015s with native inference/tool entrypoints instrumented to fail if called. Exact human-data preservation comparison passed; no pending jobs, no automatic approvals or changed links/answers. Final hidden launcher8788 serves127.0.0.1:8000. Receipt docs/development/VERSIONED_EVIDENCE_RECEIPT.json.


## 19 October 2026 Standard checklist library and construction room instances

Added the shared standard catalog at /devadmin/checklist-templates/standards/ with actual previews and four versioned sources: Telecom Survey Default from the previously uploaded FDED master; Telecom Inspection Built to Suit; Telecom Inspection Colocation and Modernization; Construction Inspection all stages. The FDED source remains byte-for-byte equivalent in its sections/field definitions: 16sections,172fixed spreadsheet rows and9equipment inventories,181fields total. Inspection baselines have56BTS fields,48Colocation/Modernization fields and55Construction base fields.

Construction stages are Preconstruction,Design,Grey Structure,MEP,Finishing,External works,Testing and handover. The room inventory supports24types and up to40named instances with optional floor/level. Repeated bedrooms/bathrooms keep separate section IDs, field IDs, answers and photo evidence. Room-specific points include wet-area,stairs,external-room and plant/garage topics. Stages and room instances are validated again on the server and in edited template configuration. Generated room fields include structured room context; a generic interior photo cannot establish room/floor identity for automatic suggestions. Explicit manual photo assignment remains available. Large room catalogs use semantic batches of at most500fields without dropping fields.

Super Admin can inspect the shared administrative catalog and source previews. Scoped Project Admins can create separate drafts only within their permitted industry, then use existing publish/assignment controls. Source templates are not engineering certification: approved project criteria, technical applicability and the existing independent review workflow are retained. Standard templates cannot be assigned to the wrong project industry or task workflow, including direct model/service callers. Existing custom templates without standard metadata retain their behavior. No SQL schema migration was introduced.

The three Telecom drafts were created for the existing scoped Admin through normal CSRF-protected invitation-era administration routes; they are not published or assigned automatically. Construction is available globally in the standard library for a Construction Admin; no synthetic live Construction project/account was created. The current two-checkpoint project, its published template, answers, approvals, photos and links were compared before/after and remain unchanged. Existing operational templates and project defaults were not reassigned. Frontend form errors preserve entered name, stages and room JSON; previews use actual selected stages/rooms, with no-JavaScript stage submission supported. Final acceptance evidence: docs/development/STANDARD_CHECKLISTS_RECEIPT.json.

Standard library final acceptance:403core tests passed29.378s;21desktop/mobile browser cases passed with zero writes. Actual server credential login/library/source-preview checks passed for Super Admin and Project Admin. Live3Telecom drafts created without publication or project reassignment; Construction shared standard available under its industry controls. Runtime hidden launcher36544. Receipt docs/development/STANDARD_CHECKLISTS_RECEIPT.json.

## 19 October 2026 Checklist Wizard, multi-checklist Excel and construction activities

Checklist Wizard is live at /devadmin/checklist-wizard/. Project Admins can create scoped blank drafts, modify owned drafts, independently replicate permitted sources, choose standards and preview Excel imports. Super Admin has administrative read/download access. Excel supports all eight existing field types and explicit existing evidence sufficiency conditions, repeated-table definitions, room context and lossless FDED/standard descriptive metadata. Unsupported conditions, formulas, macros, external links and malformed/oversized workbooks fail before draft creation. Actor/company-bound30minute immutable previews require matching digest and explicit atomic commit; replay returns the same drafts. No automatic publish, assignment, survey answers, AI runs or approval writes. Additive migration0037 stores preview batches. Published revisions remain immutable; Wizard draft saves reject stale edits and retain entered structure. Industry/workflow cannot be bypassed through the legacy editor.

Construction now has20 stage choices, retaining all7older codes plus13 detailed activities: excavation, engineering fill/compaction, FDT, lean concrete, foundation reinforcement/concrete, plinth beams, ground slab, lintel beams, first-floor reinforcement/concrete and reusable other-floor cycles. Each explicit activity ends in a required repeated test register with appropriate actual measurements, report/criteria references, units, human decision, reviewer and retest/N-A explanation columns. General legacy stage registers stay optional. No numerical engineering thresholds are invented. Ordinary draft sections can be copied with new IDs for additional floors; named-room copies use explicit room inventory instead. Existing published/site definitions are not regenerated.

Validated443full core tests40.514s, final17Wizard-focused tests,20actual desktop/mobile Wizard browser cases and4actual Engineer mobile FDT/slump save/reload cases. Starter XLSX in outputs/checklist-wizard-20261019 and backend/static/core/templates was authored with Artifact Tool;9sheets visually reviewed,2Telecom examples importable,0formulas and10dropdown rules. Runtime exports reuse installed openpyxl. Valid XLSX files with absent/incorrect optional dimension metadata are bounded using actual coordinates and parse correctly. Live credential GET/download/export checks pass for Super/Admin; Construction20stage workbook and original181field FDED export verified. Production imports0;2originalphoto hashes and allaccount identities/password hashes preserved.34business tables match checkpoint165637. Concurrent Super Admin industry created/updated/binding events changed IndustryCatalog/Profile and were retained, not reset. Normal sign-ins append audit/session timestamps. Current launcher18076, nativeOllama untouched. Receipt docs/development/CHECKLIST_WIZARD_RECEIPT.json. Next active user change: move project creation to scoped Admin and choose3/4layer workflow with one-step clarification returns.

## 19 October 2026 Private Admin projects, three/four layers and editable industries

User superseded Super project creation: only an active company/industry-bound Project Admin may create projects. ProjectForm fixes company/industry/administrator on the server, requires3or4review layers and grants the creator membership. Super creation is403 and all creation forms were removed from Super screens. Project.administrator is the unique owner; central accessible_projects now requires both owner and effective affiliation for an Admin. Same-company memberships, primary-profile pointers, forged filters and former-owner grants cannot expose another Admin's project, APIs, photos, reports or project-linked templates. Explicit Super ownership transfer is audited, preserves evidence/history and immediately removes former-owner access. Legacy trusted primary assignment claims only null ownership, never replaces an owner; migration0040 adopts only an unambiguous existing Admin and preserves already named owners. Existing live project1 remains owned by demo_admin01. Super retains administrative metadata/audit/ownership controls, no engineering signatures. Admin invitations can bind company and industry without any project; that Admin creates their first project after accepting. Operational invitations still require a scoped project; Clients remain Admin-only.

New project workflows:3layers Engineer->Quality Engineer->Team Lead closes after TL;4layers adds a named Client approval/rejection. Each new task freezes project_review_layers at creation and independent reviewer IDs in ReviewRoute; alternate service/model paths cannot downgrade it. Existing tasks without that marker retain their prior policy. Client rejection goes only to TL; TL rejection goes only to QA; QA rejection goes only to Engineer. Reviewer clarification keeps inputs frozen, requires an attributed reason and can respond one step forward or return one further step. Engineer corrections create a new parent-linked immutable SubmissionRevision and require fresh approvals. ReviewRouteEvent is append-only and supports repeated cycles without replacing old signatures. Current-route actions require CSRF, assigned current person/role/membership and fresh state token; Admin/Super cannot sign. Client access requires a TL sharing event for the exact current revision and excludes Engineer/unshared corrections; old already-shared snapshots remain readable through historical revision controls.

Industries now have description and a stable workflow_family. Super may edit code/name/description/active state through an atomic token-checked service; code changes retain IndustryCatalogPK/Admin and Client organization FKs and update Project.industry references. Existing family is fixed, new industry creation may choose Telecom/Construction/Other. All module/standard/assignment/qualification checks use stable family, not editable display code. New frozen routed snapshots include stable industry identity; administrative code/name changes retain historical labels during digest validation and do not rewrite approved snapshots. Local AI description generation is Super-only, JSON/CSRF protected, uses the existing inference lease and configured Ollama text model, returns an editable proposal and never saves automatically. Real error/retry and dirty-edit protections exist. No new AI service or photo inference was introduced.

Additive migrations0038through0042 applied. Final479core tests PASS46.874seconds (process-only test MD5 override),5actual route browser cases and5industry browser cases passed across desktop/mobile. Normal live Super/Admin logins and owner restrictions verified. Actual native qwen3.5:4b text description returned449characters with saved=false and unchanged catalog; no operational test data created.37existing business tables in shared pre-migration columns, all20account identities/password hashes and2original photo SHA256 values match checkpoint171154. Original legacy project/task routing preserved; production ReviewRoute/events0. New runtime hidden launcher26696; nativeOllama unchanged. Pre-upgrade checkpoint173411. Receipt docs/development/PROJECT_OWNERSHIP_REVIEW_AND_INDUSTRY_RECEIPT.json; live proof .local/project-industry-live-verification.json. No GitHub push/public hosting. All project/data remain under F:/iSurvix/iSurvix-Field.

## 19 October 2026 Compact People and invitations tables

People, project access, Admin industry bindings and invitation cards now enhance to compact tables using people_tables.js/css loaded on Super/Admin screens. The transformation moves the original permission-scoped form nodes, preserving actions, CSRF, confirmation handlers, select/input names, values and required flags. Project Admin People & invitations uses three keyboard tabs; existing Super SA-02 panels remain. Tables have bounded internal scrolling, sticky headings/person column, search/counts, expandable access/grant details and hover/focus-labelled action icons. Original server-rendered cards remain functional without JavaScript. No backend, permission or schema change.

20focused governance/console tests passed1.954s;16private browser cases passed1440/390/320 across Super/Admin. Browser source-vs-table form signatures match, search/empty states, keyboard tabs and grant/invitation panels pass; screenshots inspected. Normal live Super/Admin pages/assets pass;39business tables and account credentials match checkpoint173618 (normal sign-in audit/session updates only). No operational writes/native AI calls. Restarted only verified launcher26696 after0active photojobs; current hidden launcher33968. Private QA helper stopped. Receipt docs/development/COMPACT_PEOPLE_TABLES_RECEIPT.json.


## 19 October 2026 Seven account project team

Owner requested one Admin, two projects and Clients, with one shared Team Lead, QA and Engineer. Reused six existing linked identities and renamed logins: admin01, client01, client02, teamlead01, qa01, engineer01. Super Admin super_assim and all retained password hashes unchanged. Removed13unused temporary accounts after inspecting deletion cascades; original audit actor labels retained. No demo_/test_ usernames remain. Seven active accounts total.

Test Project1(ID2) and Test Project2(ID3) remain owned by admin01, both four-layer Engineer->QA->Team Lead->Client. Ten active grants: Admin/TL/QA/Engineer access both, client01 only2 and client02 only3. Admin-created Client1/Client2 organizations linked to corresponding project. Legacy Two-checkpoint workflow test(ID1), its draft/evidence and history remain stored with no active staff grants or owner. Super can inspect its administrative metadata. No technical decisions or historical identities were rewritten; no projects or tasks were invented or removed.

Verified seven actual HTTP credential logins and21allow/deny project requests; retained passwords unchanged; protected business tables and original media hashes match pre-cleanup checkpoint180751. Account-reorganisation receipt records the exact scope. Private Excel register updated in place with seven rows. Existing Word original is locked open, so current seven-account copy saved to .local/private/iSurvix_Current_Usernames_and_Passwords.docx without closing Word. Packaged native DOCX renderer unavailable because bundled LibreOffice is absent. Existing app/worker runtime unchanged; no code/schema migration or GitHub push.


## 19 October 2026 Live Telecom survey user test with real Z78005 photographs

Used normal live HTTP credential sessions for admin01, teamlead01, engineer01, qa01, client01, client02 and super_assim. No force-login or direct ORM writes for configuration, assignments, uploads, mappings or review actions. Admin published existing uploaded-FDED standard2(181fields) through Wizard and assigned it to Test Project1/2. Team Lead assigned siteZ78005 in Project2(Test Project1) to engineer01 with QA19, TL15 and Client12 under the existing four-layer route. ChecklistID2. General site information and coordinates22.64275,39.130271 came from the supplied source XLSX; original surveyorNaseer/ISG retained as source information. Task description explicitly marks live testing, not engineering certification.

Source E:/Online Storage/iSurvix/OneDrive - iSurvix/Nokia Project - Site Survey/Data from Surveyors/Ahmed/Z78005 contains1164JPEGs. Full readonly SHA/image audit890.51seconds found16exactduplicates,1148unique and0unsupported. Uploaded400distinct originals into F .local/media:57Civil,146Electrical,197Tower. Proportional chronological sample preserves20bootstrap photos uploaded through actual Engineer browser controls; final effective selection in .local/real-site-test-20261019/effective-upload-plan.json.748unique originals remain outside the existing400/site cap. Native deduplication at capacity and safe rejection of a401st new photo were tested through real CSRF-protected HTTP uploads. Z90039 directory exists but contains0files; no fictional coordinates, photos or empty engineering assignment created. Project3 has the full Telecom checklist ready for later input.

Verified Python3.12.10, actual Ollama/api/show vision capability of installed qwen3.5:4b digestd8b0f5... before native inference. Native processing is CPU only(size_vram0), with initial photos about135-139seconds/photo.400/30minutes is not demonstrated; this observed throughput is far too slow. PhotoJob4 is20bootstrap photos, Job5 is380queued photos. Processing is STILL ACTIVE in independent worker; do not claim400photos analyzed or a completed review cycle. Submission and final AI review are guarded while photos are pending; no QA/TL/Client technical signatures were recorded.

13live role/guard checks passed. Internal Engineer/QA/TL read identical immutable saved analysis payloads/digests; Clients cannot read unshared draft; Super is administratively restricted; QA/TL uploads and premature approvals blocked. First sign photo correctly displaysZ78005 but AI also suggested an unrelated tower nameplate and FPFH item. Engineer test session confirmedTAWALsign row23 and rejectedrow26/62. These create draft learning cases only; no correction release or engineering answer/pass was published. Mapping precision and native performance remain actual findings.

Found and fixed the main AI progress display using a current20photo batch as denominator when400site photos existed. ai_analysis.js now uses distinct site photos and saved processed IDs, retains current batch counts as a secondary label and half-step only for a genuinely unprocessed current source. Template query key bumped to ai-analysis-2. Cached browsers need Ctrl+F5. No restart because native work is active; launcher33968, web292 and worker4224 remain. Production files changed only static/core/js/ai_analysis.js and templates/dashboards/photo_workspace.html. No Python/schema/matcher/tool fingerprint or approval control changes.

400photo browser review at1440and390 passed;40image DOM nodes rather than400thumbnails, no root horizontal overflow, actual filtered task list->photo workspace->return retains project2/qZ78005. Node syntax and Django system checks passed. All400stored original hashes verified against source selection;146preexisting core rows preserved(except authorized Project2/3 template pointers and published Template2; runtime leases/governance mutex excluded). Seven account names/password hashes/roles unchanged. Older two-checkpoint draft/photos remain intact. Receipt docs/development/REAL_TELECOM_SITE_TEST_RECEIPT.json; private logs/screenshots/HTTP source states in .local/real-site-test-20261019. No GitHub push, new external AI service or public hosting.

## 19 October 2026 Dedicated GPU photo analysis pipeline

This supersedes the CPU-only runtime and active-job details immediately above.
Owner requested a separate, faster photo analysis pipeline. Detected RTX3060Ti8GB,
driver610.88; existing native Ollama11434 was CPU-only. Started the already installed,
signed portable Ollama0.40.5 from F .local/runtime/ollama-0.40.5 with model store
F .local/ollama/models, bound127.0.0.1:11435. Kept original11434 process untouched
for interactive chat. Verified qwen3.5:4b local vision before photos, exact same
digest d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04.
Native /api/ps reports3140495604bytes in VRAM rather than0; CUDA8.6 detected.
Cold vision probe43.875seconds includes36.877seconds model load. Warm image-only
probes4.406and4.203seconds. No new provider or model download.

Start-iSurvix.cmd/ps1 now connects or starts scripts/Start-PhotoAI.ps1; dedicated
photo endpoint is ISURVIX_PHOTO_OLLAMA_URL, falling back explicitly to original
queue if portable installation is unavailable. Local transport retains loopback,
no redirects/proxies, response bounds and cloud-model exclusion. Separate native
lease photo-inference avoids holding the chat lock; global photo-worker lease
prevents two consumers racing even with different endpoint configurations.

Migration0043 adds immutable PhotoObservation rows with original/model/prompt
fingerprints and payload digests. Existing data tables/rows were preserved.
Worker stages four images before checklist comparison, commits reusable vision
output before OCR/QR/semantic/targeted steps, and resumes from durable stages.
Fingerprint-qualified historical observations are reused; uncertified legacy
observations remain preserved and are reanalyzed once. Checklist text embeddings
are cached per worker, bounded4096texts; OCR ONNX threads limited2intra/1inter.
All existing hard evidence rules, targeted verification, published correction
controls and human confirmation remain. UI progress reflects durable analysis and
comparison halves, retains separate matched/mismatched/human-confirmed counts;
cache key ai-analysis-3. No timed fake progress.

Stopped only verified app/worker process trees for handoff; originals and cached
results retained. Historical jobs4/5 now superseded with maintenance handoff note,
old contexts/processed IDs unchanged. Normal engineer01 credential+CSRF enqueue
explicitly adopted current processing tools for all400sitephotos in Job6. At
19:07local snapshot:25/400complete, no error, running,25durable observations,
current-attempt average11.363seconds/photo (5.28/minute), last image stage3.36s,
last comparison9.5s. Prior full-photo average128.682s. Early throughput is not a
complete400photo benchmark; initial samples reuse old observations. The400/30min
target has NOT been demonstrated. Leave processing running; do not claim completed
analysis, engineering submission or approval. Task2 remains DRAFT.

All489coretests passed, plus55focused final queue tests; Django checks and pending
migration checks clean; JavaScript and both PowerShell launcher syntax passed.
Recovery tests cover failed matching without repeated vision, changed model digest,
tampered original/payload guards, lease loss, concurrent consumer exclusion,
embedding reuse/eviction and actor-independent saved output. Live Engineer/QA/TL
state200, Clientdraft404, Super403;24common saved-record digests identical across
internal roles. All402stored original hashes, seven users/auth hashes/roles,
checklist answers/schema/status/history/approval values and human photo decisions
were compared against a pre-handoff baseline and are unchanged. Real browser1440/
390passed,40thumbnail nodes, no root overflow, filtered task return retained.

Receipt docs/development/DEDICATED_PHOTO_PIPELINE_RECEIPT.json. Private benchmark,
protected baseline and handoff records under .local/photo-pipeline-20261019.
Pre-change verified recovery checkpoint .local/backups/project-checkpoint-20261019-185716.
Final launcherPID32628; app http://127.0.0.1:8000, photo runtimePID12616 on11435,
original OllamaPID9728 on11434. Verify current PIDs before future process actions.
Pipeline logs .local/pipeline-final-launch.*.log and latest worker-*.log. All work
and local data remain under F:/iSurvix/iSurvix-Field. No GitHub push/public hosting.

### Final native grounding recovery and current queue

The initial dedicated Job6 stopped after26photos: photo29's targeted model reply
claimed supported without at least20characters of concrete visible evidence.
Diagnosed against the real original and preserved its cached image analysis.
Targeted instructions now request short bounded explanations. A structurally valid
unsupported claim is explicitly downgraded to insufficient, with a missing-evidence
note, before the unchanged strict validator runs. This cannot create a link, answer
or approval. Injected answers, extra/unknown/duplicate fields, invalid reasons and
malformed structures still fail validation. Native photo29 retest under the final
current tools succeeded with3unconfirmedproposals; its image analysis was reused.
No evidence rules were removed to gain speed. Job6 and its failure/context/results
remain preserved as superseded; historical jobs4/5 also remain.

Normal Engineer credential/CSRF enqueue explicitly adopted the final tools for all
400photos in Job7. It is running independently; previously completed observations
survive, and historical human decisions/answers/approvals remain unchanged.
Early Job6 full-photo average12.721seconds versus128.682seconds previously;
these are early mixed cache/fresh measurements, not a completed400photo benchmark.
Warm image-only probes remain4.2–4.4seconds. The400/30minute target is still NOT
verified. Do not claim the analysis or submission/approval cycle has completed.

Final full core suite490tests passed in54.234seconds. Django check, migration drift
check and JavaScript syntax passed. Final live original SHA/account/answer/schema/
history/approval/human-link baseline comparison passed for402originals. Real browser
1440/390passed again with40thumbnails and retained project2/qZ78005 return filters.
Final launcherPID35564, loopback app8000, native photo server11435/PID12616; original
CPU assistant11434/PID9728 preserved. Logs .local/pipeline-verified-launch.*.log.
The current job ID is also in .local/photo-pipeline-20261019/new-job.json.
Use docs/development/DEDICATED_PHOTO_PIPELINE_RECEIPT.json for the final snapshot.

## 19 October 2026: requested five photos per second

Implemented a separate CPU batched image/text retrieval lane alongside the existing
GPU detailed verifier. Research and alternatives are recorded at the start of
docs/FIELD_PHOTO_WORKFLOW_PLAN.md; primary sources include Qdrant's paired CLIP
ONNX model cards, OpenAI CLIP, Google SigLIP2 and Ollama concurrency documentation.
Selected the two CLIP encoders supported by the installed FastEmbed stack; no new
Python dependency, hosted model or outbound photo transfer. Pinned revision and
official model SHA256 verification, plus tokenizer/preprocessing/runtime/source/
schema fingerprints, keep results versioned and shared across authorized users.
Models and caches remain under F .local/models/photo-search; reproducible installer
scripts/setup_photo_search_models.py. Actual vision architecture/weights are checked
before processing project images.

Final retrieval benchmark:400unique real Z78005 originals,41.019seconds,9.751photos/
second. Includes cold process model verification/load,181-field checklist text
encoding, original SHA reads, image decode/preprocessing, two-thread CPU inference,
rankings, permissions/schema checks and SQLite commits. Current version had0cached
vector hits;400rehearsal-version rows were preserved separately. This EXCEEDS5/sec
for INITIAL UNVERIFIED SUGGESTIONS. It does NOT establish detailed OCR/QR/vision
verification, engineering accuracy, submission readiness or approval at5/sec.
Estimated500initialsuggestions50-60seconds;500uniquephoto benchmark not run.
64-image encoder samples14-19/sec; final production setting uses2CPUthreads and
batches32 to leave capacity for the rest of the app. Benchmark and browser receipts
in .local/photo-search-benchmark. Research quality limits are explicit: no calibrated
confidence or cross-industry accuracy validation. The one existing human-confirmed
sign pointrow23 appeared in the top3(photo3); this is not a broad accuracy study.

Migration0044 adds immutable PhotoSearchVector/PhotoSearchResult only. New independent
photo_search_worker starts with Start-iSurvix.cmd alongside photo_worker and stops
with its launcher. Retrieval can run even if detailed verification has failed;
neither worker creates approvals. Fast-state GET uses the existing survey access
guard, paginates2results, hides internal suggestions from Clients and sets private/
no-store. A permitted Engineer can inspect a photo and manually choose a point using
the existing mapping API; QA/TL have read-only controls here. Existing human links,
rejections, answers, accounts and workflow locks remain unchanged. Fast completion
does not update PhotoJob.processed_photo_ids or open final-review/submission gates.

Photo workspace now separates Fast AI Analysis from Detailed AI verification, shows
two photo tiles/page, and expands saved detailed history lazily. Real desktop1440/
mobile390 tests passed; pagination changes actual photos, confirmation is disabled
until a point is selected, closed history builds0assessmentnodes, expansion builds
only the chosen181-item record, no root overflow, filtered task return retained.
The upload and enqueue cap is now500photos/site;20perbatch and5MiB/file remain.
Boundary tests accept500/refuse501 and permit duplicates at capacity.

During this task the old detailed Job7 failed after64photos because photo67's compact
observation exceeded256tokens. Invalid partial output was not cached. Increased the
bounded ceiling to768without relaxing schema/approval checks; actual photo67 retest
completed and saved valid observations. Historical Job7/context/error/results were
preserved as superseded. Normal Engineer credential+CSRF enqueue explicitly adopted
current tools ONLY for336remaining photos in Job8;64completed results preserved.
At19:37local snapshot Job8running16/336,80/400totaldeepcomplete,400/400fastready,
no current job error. Leave detailed processing running. Do not claim all400fully
verified or a finished review/approval cycle. Site2 remains DRAFT.

Full497coretests passed in50.087seconds; final focused16passed. Django check, migration
drift, four JS modules and PowerShell launcher syntax passed. Live Engineer/QA/TL
fast-state200 with identical saved suggestions; unshared Client404; Super403. All402
original SHA256s and baseline user auth/role/active state, answers, schema, approvals,
history and human mappings were rechecked unchanged. No GitHub push or new users.
Latest final launcherPID26272; .local/fast-photo-launch.pid is authoritative after
restart. Logs .local/fast-final-launch.*.log and photo-search-*.log. Original native
assistant11434/PID9728 and photo model11435/PID12616 preserved. Verify PIDs before
future process actions. Final receipt docs/development/FAST_PHOTO_ANALYSIS_RECEIPT.json.
Pre-change recovery checkpoint .local/backups/project-checkpoint-20261019-192530.


### Final visual relevance filter and delivered benchmark

Visual QA identified profile/contact fields among the initial generic text
similarities. Restricted retrieval to photo/inspection points or fields explicitly
requiring photo evidence, retaining the number/date/system exclusions. The live
181-field template has150eligiblevisualpoints. The sign's existing human-confirmed
point remains represented; no profile fields are suggested. Fast indexing covers
the full editable site, independently of a resumed deep job's remaining-photo
subset. Tests cover both conditions.

The final filtered cold run processed400unique originals in50.846seconds,
7.867photos/second, with0current-versionvectorcachehits while GPU verification
continued. This supersedes the earlier41.019second/9.751rate for the broader
catalog. Projected500initialsuggestions60-75seconds; full verification is still
slower and remains mandatory before final review/submission. Retained historical
rehearsal-version rows are not used as current results. No photo/answer/human
decision was changed by the filter or cache upgrade.

Final full core suite499tests passed; focused retrieval/capacity suite18passed.
Final launcherPID17496; .local/fast-photo-launch.pid remains the current source.
Logs .local/fast-release-launch.*.log; UI and API unchanged routes. Final performance,
quality limits, source links and live role results are in
docs/development/FAST_PHOTO_ANALYSIS_RECEIPT.json. Latest browser checks include
two-card pagination and lazy history at desktop/mobile widths.


## 21 October 2026 integrated survey checklist and drawings

Feature branch: `feat/ai-survey-drawings`, based on the saved/pushed
`feat/local-photo-pilot` checkpoint 4c435fc. Do not merge or deploy automatically.

The opt-in Checklist required setting belongs to published ChecklistTemplate
revisions and applies only to Telecom surveys. Existing templates default False,
so saved surveys and all inspection modules retain their existing behaviour.
Draft templates now also support an assigned company logo. Additive migrations
0045 and0046 were applied locally; existing data columns and all402 original
photo SHA256 values were checked against the pre-change recovery checkpoint.

New saved-survey route `/local/survey-processing/<id>/` contains submission,
background progress, generated checklist and linked source evidence, editable
extracted records, measured drawing records, rendered previews, private PDF/DXF/ZIP
downloads and revision history. Start-iSurvix.cmd starts survey_processing_worker
alongside the existing workers. Jobs persist image/document and checklist mapping
checkpoints; no model download or cloud fallback is used. qwen3.5:4b local vision
capability and installed drawing dependencies were verified.

Engineer Apply checklist & complete review is explicit: valid reviewed answers and
confirmed photo links are copied to the saved checklist, unrelated data/manual
rejections preserved, and an append-only resulting-input digest receipt binds the
unchanged original snapshot. Existing submit/required-field/approval controls
still apply. QA must independently check the exact package; a different Team Lead
releases only after the existing survey/optional Client route closes. Clients see
released outputs only. AI cannot approve or release.

Both exports use final shared A3 geometry, including title blocks, layers and
versioned generic DXF blocks. All sheets have PNG previews. Unsupported sheet
categories are listed rather than invented. Exact geometry needs source-bound,
explicitly verified measured records; generic envelopes are Typical - verify
against site. There is no verified manufacturer library or engineering design
calculation engine. Complete drawing bundles include linked logo assets.

Private native Z93004 pilot:3 realphotos ->181items/21findings/draftPDFDXF in
80.862seconds. Its workbook validates247imageplacements+3textsources, and native
cell-text/embedded-image probes passed. Full378-photo+wholeworkbook native
benchmark and field accuracy remain outstanding. No real approvals were created.
Native artifacts/receipts stay .local/survey-drawings-task; synthetic shareable
samples are samples/drawings. Browser checks use isolated databases and records.

Read docs/manual/AI_SURVEY_TEAM_GUIDE.md and
docs/development/AI_SURVEY_DRAWING_PIPELINE.md. Private pre-change checkpoint:
.local/backups/project-checkpoint-20261021-175047. Development verification receipt
is docs/development/AI_SURVEY_DRAWING_RECEIPT.json. GitHub PR targets the existing
feat/local-photo-pilot baseline, keeping this feature review separate from main.

## 21 October 2026: guided checklist creation and lifecycle table

Branch `feat/checklist-guided-wizard` extends `feat/ai-survey-drawings` without
merging or deploying. Admin Checklists navigation opens the internally scrolling
library at `/devadmin/checklist-templates/`; the dedicated action route is
`/devadmin/checklist-library/`. Search, status filters, 25-row pagination, selection,
icon tooltips and confirmed atomic lifecycle actions use actual scoped records.

Wizard new-from-zero now recommends sections first, then checkpoints only after
section acceptance. Standards are combined with up to 100 recent enabled,
published templates in the Admin's existing scope and matching workflow. Counts
rank suggestions; drafts, foreign definitions and site answers do not teach it.
Each generated structure remains an unpublished draft until explicit publication.
Custom sections and typed/required/photo-required checkpoints are supported.

Migration0047 adds ChecklistTemplate.disabled, default False. Every template used
by any saved task is structurally locked and cannot unpublish/delete. Unused
published templates can explicitly unpublish before edits. Disabling stops new
assignments but preserves historical work and current project defaults. Deletion
requires an unused unpublished draft with no project/historical references.
New task creation locks and rechecks its source template against lifecycle races.

One-sheet sample download: Wizard workbook `?format=simple`. Reusable authored
sample lives in `backend/static/core/templates/iSurvix_Checklist_One_Page.xlsx`.
It supports section/point, type, required answer, photo, choices, units and help.
Existing safe preview/explicit commit/replay handling remains. Import extra points
can append a reviewed matching-workflow workbook to an unused draft without
replacing its existing fields; stale target changes are refused.

Final594core tests passed60.688seconds; Django/migration/JS checks passed. Actual
synthetic browser creation/import/publish/unpublish/delete passed at1440/390 with
zero application JS errors and no outer-page overflow. Before/after comparisons
match all old columns of62live tables and402originalphoto SHA256s. No operational
test accounts, tasks, template changes or approvals were seeded. Checkpoint before
changes: `.local/backups/project-checkpoint-20261021-190149`. Private browser/test
receipts: `.local/guided-wizard-qa`. See docs/manual/CHECKLIST_CREATION_GUIDE.md.

## 21 October 2026: exact-revision checklist tree editor

Branch `feat/checklist-editor-tree` extends `feat/checklist-guided-wizard` with a
focused editor update. Wizard Edit and Replicate have independent selectors and
desktop columns. Explicit template/version form identity, canonical POST targets,
no-store responses and stale edit digests protect selection and concurrent saves.

The editor uses two compact header rows, collapsed three-column branding and a
Group / Section / Field tree beside Properties and Recommended additions. Group,
Ungroup, move and sibling reorder preserve existing IDs and rules. Optional JSON
`editor_groups` retains empty groups/order; `editor_recommendation_decisions`
persists accepted/dismissed choices. Legacy `section.group` remains supported.
No database migration is required. Advanced workbook round trips retain metadata.

Recommendations reuse the existing matching standards/scoped published catalog;
no inference service or fabricated suggestions are added. Users review/edit and
accept into an editable draft, then save. Stable recommendation IDs and target
label checks prevent duplicate additions. Published/disabled/used protections,
survey snapshots and the survey-only Checklist required gate remain in effect.
Import extra points and project assignment continue through their existing routes.

All 605 core tests passed in 63.548 seconds. The additional focused 11-test editor run
also verifies report branding. Browser checks at 1440/1024/390 widths cover exact source,
tree operations/save/reload, recommendations/dismissal/retry, branding replacement
and removal, published locks and keyboard selection with zero application errors.
All 62 existing tables and 402 original photo hashes match the pre-change checkpoint
`.local/backups/project-checkpoint-20261021-193725`; no operational fixtures seeded.

Synthetic editor screenshots are `outputs/checklist-editor-20261021/` (ignored).
Private QA receipts and isolated fixture database are `.local/editor-tree-qa/`.
See `docs/development/CHECKLIST_EDITOR_RECEIPT.json` and the updated checklist guide.
The five referenced layout screenshots were not attached to this request; the
numbered requirements guided the layout. Existing whole-site AI/drawing benchmark
limitations are unchanged. Review only; do not merge or deploy automatically.

## 21 October 2026: visible task creation and project site intake

Branch `feat/site-task-intake` extends `feat/checklist-editor-tree`. Admin and Team
Lead Overview/Tasks have a prominent Create task action; project cards also link
single and bulk site entry. `/governance/tasks/new/` is the dedicated screen. It
uses existing AssignmentForm, create_assignment, AssignmentIntakeBatch and frozen
review routes; no new models or migrations. Other roles cannot create tasks.

Single entry selects the project team, activity, source/CRS and recorded site data.
Published template metadata supplies the default activity. Project three/four-layer
rules remain authoritative and named reviewers are validated against active project
membership. Inspection independence and existing qualification gates remain intact.
The new UI does not expose per-task overrides of the project layer count.

Bulk entry pastes IDs into an editable 200-row table, skips repeated pasted IDs and
uses durable preview/atomic confirmed creation. Retrying the same confirmed batch
returns the same results. Existing CSV preview/commit remains, adds named basic
site columns and downloads its actual server template with review columns included.

Recorded basics map deterministically to matching checklist general fields once;
explicit preload values take precedence. Additional data remains in intake_metadata
site_information. Original field IDs, published definitions, previous answers and
approvals are not rewritten. No compliance or approval decisions are auto-filled.
Task rows and Overview show the actual saved workflow and current stage, including
one-step clarification returns. Site name appears beside its ID when recorded.

Isolated browser checks exercise both roles, single/bulk entry, project switching,
Client selection, duplicate paste/replay, mobile layout and Engineer delivery.
Private QA and the pre-restart database snapshot are `.local/task-intake-qa`.
Screenshots: `outputs/site-task-intake-20261021/` (synthetic data, ignored by Git).
The recovery checkpoint before changes is
`.local/backups/project-checkpoint-20261021-200810`. Live user sign-ins and edits to
an existing draft occurred during development and were retained. Original business
records and all 402 original-photo hashes remain; historical definitions/approvals
are unchanged. Read the development receipt for final tests and delivery details.

Final 617 core tests passed in 73.978 seconds; focused 42-test checks, Django,
migration drift, JavaScript syntax and browser checks passed. Details are in
`docs/development/SITE_TASK_INTAKE_RECEIPT.json`. The web app was restarted to load
the new task routes; existing workers were left running. No merge or deployment.
