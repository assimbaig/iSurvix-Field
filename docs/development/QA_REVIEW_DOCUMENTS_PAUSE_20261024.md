# QA review, supporting documents and AI processing controls

24 October 2026. Branch: `fix/qa-guided-documents-pause-20261024`.
Preserves paused WIP `3668cbb`, merged PR16 `8aeb872` and local merge `5ceb0a7`.
Pre-edit recovery archive: `.local/backups/project-checkpoint-20261024-140010`;
2,910 files, both SQLite integrity checks and ZIP CRC passed.

## Implementation

QA opens My reviews and follows Site information -> Review evidence -> Decision.
The same saved workspace retains source data, category/checklist navigation,
photo viewer, evidence matching, human answers, review decisions and history.
Advanced tools are secondary. Save & next advances only after a confirmed save.
Desktop panels and mobile drawers/tabs preserve selection and scroll state.
The engineering route and its completion, rejection, stale-token and role rules
remain the authority; no new approval system was added.

Engineer capture has a separate Sketches & reports tab. General Info remains
site data and Civil/Electrical/Tower remain photo categories. Supporting PDFs,
Excel workbooks and supported images use existing immutable SurveyDocument
storage and extraction. Transfers share existing durable upload sessions and
are bounded to five documents/request, 30 MB/file, 50 retained originals/site.
Soft removal excludes a source from the next submission and preserves its bytes,
database row and previous revision. Retrying/restoring the same bytes reuses its
identity. Upload failure blocks submission until retried or removed.

New opt-in document metadata binds documents into both human review signatures
and processing snapshots. Older signed snapshot shapes remain unchanged. Frozen
download links include their revision; the older protected download route uses
the same membership rules for category capture. QA can inspect document analysis;
Engineer and Team Lead receive source files without new AI action items. QA answer
edits retain document provenance; document-only evidence cannot satisfy a
photo-required checkpoint. No database schema changes or migrations were needed.

Assigned QA can pause/resume a current, unlocked processing job. Queued jobs pause
immediately; running jobs enter Pause requested and stop after saving the current
bounded evidence task. Source analyses, mappings, outputs and model pins remain.
Busy/error handling cannot erase a pause request. Expired workers settle the
request without reclaiming paused work. Resume keeps the revision and checkpoints,
and repeated requests cannot reset an already claimed resumed lease. The existing
outbound PC worker follows the same boundary protocol. The Engineer has no new AI
control through either current or legacy HTTP routes.

## Verification evidence

All ordinary tests use isolated databases/media and blocked external network.
TDD red receipts and focused runs are under `.local/qa-resume-20261024` and the
retained `.local/qa-quick-review-20261023`; the initial document missing-contract
and pause missing-action failures were reproduced before implementation.
The inherited QA redesign was WIP before this resume; new regression fixes use
failing tests, rather than retroactively claiming that WIP was created with TDD.

Independent saved-data browser runs: smoke 26, guided QA 33, documents/pause 29,
return/resubmission/existing-processing 12, scroll regression 4, drag/drop and
accessible category navigation 8, submitted-document source checks 4 and clean
upload-status checks 9: **125 assertions**,
zero JavaScript exceptions across the successful runs. Screenshots are in
`output/screenshots/qa-resume/`. These include failed upload/save feedback,
original-byte hashes, soft removal/restoration, immediate QA queue visibility,
duplicate submission, manual review with pending/failed AI, real stale decisions,
one-step return, retained evidence and desktop/mobile refresh persistence.

New frontend units: 21 document, 18 guided QA, six processing readiness assertions
(45 total).
Seven frontend check scripts pass; runtime readiness adds five PowerShell unit
cases. Backend tests cover uploads, documents, snapshots, current/historical
delivery, role/CSRF/stale guards, source boundaries, local/outbound worker restart,
duplicate delivery, lost resume replies and final-transition races.
The final source-stable full-suite result is recorded below when available;
earlier 948-test success and a changing-source diagnostic run are not current
release evidence.

Before restarting the operational app, all 69 database tables were compared
against the pre-edit consistent backup: zero changed tables. All 1,908 existing
media-file SHA-256 hashes matched. An independent QA comparison also verified
59 core tables and 1,915 existing media/private files. These are preservation
checks; subsequent authorized user activity/worker progress may change records.

The native synthetic integration used real application uploads and submissions,
one actual photograph-like test label and one rasterized PDF sketch, then the
real worker and installed qwen3.5:4b. Two schema-constrained image requests carried
38,160 and 50,281 bytes. The job reached Ready for review in **19.094 seconds**,
without accepted engineering answers or released outputs. Original hashes matched.
This establishes small-input integration, not 200-photo throughput/site accuracy.

Three generated PDF pages were rendered and visually inspected. All three DXFs
passed ezdxf audit with zero errors. Outputs retain Draft - For Review, Not to
Scale, missing-information notes and pending human review. They are evidence
schedules where geometry is unsupported. Synthetic samples are in
`output/samples/qa-resume-synthetic/`; no manufacturer/site geometry is claimed.

Large progress fixture: 20 revisions, 200 photos, 200 fields, 4,000 saved sources,
8,000 findings. On identical isolated data/user, median request time was
6.049 ms before and 6.194 ms after; 10 -> 11 queries, 4,626 -> 6,533 bytes.
The existing lightweight response is retained with modest capability-field
overhead. This change does not claim a progress endpoint speedup. An explicitly
paused legacy editable survey rechecks its current source to suppress stale
Resume actions; normal progress does not load all historical snapshots/results.

## User verification

1. As Engineer, open an editable assigned site. Save General Info; upload photos
   by Civil/Electrical/Tower without selecting checklist points.
2. Open Sketches & reports, choose a type and upload a supported image/PDF/XLSX.
   Preview/download it; test remove and restore before submission.
3. Confirm uploads finished and Submit to QA. The Engineer now sees confirmation
   and retained read-only evidence.
4. As assigned QA, open My reviews and the same task immediately. Read source
   data/documents; use Review evidence to match/correct, enter answers and Save &
   next. Pause/Resume affects analysis, not manual review or engineering approval.
5. Use Decision for existing completion-gated approval or a reasoned return.
   A returned Engineer receives retained evidence; correction/resubmission keeps
   the previous revision. Published requirements and approved sections stay locked.

## Windows startup and update

GUI: double-click `Start-iSurvix.cmd` in the project. Its launcher now tests bounded
generation, because metadata alone can respond when the native runner is missing.
It reuses the existing project runtime if the installed service cannot generate;
it does not download a model. Stop previous app/worker windows before another
launch. The app and all local/private data remain under this F: project.

Manual startup, separate PowerShell windows from the repository root:

```powershell
$env:ISURVIX_OLLAMA_URL='http://127.0.0.1:11435'
$env:ISURVIX_PHOTO_OLLAMA_URL='http://127.0.0.1:11435'
.local\venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8000 --noreload --settings=checklist.settings_local
```

Set both variables in each worker window and run:

```powershell
.local\venv\Scripts\python.exe backend\manage.py survey_processing_worker --settings=checklist.settings_local
.local\venv\Scripts\python.exe backend\manage.py photo_worker --settings=checklist.settings_local
.local\venv\Scripts\python.exe backend\manage.py photo_search_worker --settings=checklist.settings_local
```

Each command is a separate long-running process. Start the existing project AI
runtime first if needed:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\Start-PhotoAI.ps1 -Model qwen3.5:4b
```

For later updates, stop this project's processes, take the established checkpoint,
fetch/review changes without resetting local work, install reviewed requirements,
check migration drift/pending migrations and restart matching server/worker code.
Outbound workers require the same reviewed compatibility version as their server.

## Limitations and security approval

The standard Ollama 0.40.10 service on 11434 still returns HTTP 500: its installed
llama-server executable is missing. Metadata is not proof of readiness. The
existing signed project runtime on loopback 11435 passes native image and text
checks and is the verified workaround; the global installation was not repaired
or replaced. Do not expose either service publicly.

DOC/DOCX parsing, physical-phone/network acceptance, large-site sustained AI
throughput, manufacturer references and production hosting are not established
by these changes. No operational survey was approved/rejected for testing.

Development rules: `DEVELOPMENT_RULES.md`. The separate post-completion security
review reports findings with severity/recommendations; those fixes require owner
approval. Functional completion is not production-security sign-off.

The separate review is complete: `SECURITY_REVIEW_QA_DOCUMENTS_PAUSE_20261024.md`.
Thirteen isolated adversarial probes reproduced S1 Medium (old Resume can override
a later Pause), S2 Low (owning Admin retained-file policy differs by route) and S3
Low (missing task can return500). H1 Medium/H2 Low record PDF-original and draft
visibility/deployment-hardening opportunities, not established code execution or
cross-project exposure. These findings have not been fixed and await owner
approval. In particular, avoid conflicting Pause/Resume commands from different
tabs until the control-generation fix is authorized and verified.

The local app and three existing workers were restored after preservation checks,
using loopback11435. Job progress, inference leases, and any authorized user
actions after startup are expected to change operational rows; they are not
described as an unchanged database after services resume. No operational
engineering approval/rejection was performed by the verification harnesses.
