# Engineer category submission and QA matching: delivery audit

23 October 2026. This is the focused Engineer/QA task, not a production security
certification or a claim that all historical roadmap requirements are complete.

## Version and preservation

- Project and all local data remain under `F:/iSurvix/iSurvix-Field`.
- PR14 baseline: `6b6ce6ee3d7b808f8fef80a4c58826158863ecb4`.
- Feature branch: `fix/engineer-category-qa-intake-20261023`.
- Local Engineer implementation checkpoint: `913f71d`.
- Pre-edit recoverable archive/database checkpoint:
  `.local/backups/project-checkpoint-20261023-194306`.
- No database models, migrations, requirements or published templates changed.
- Preservation comparison: all59 application tables checked, all1020 archived
  media files and10 archived private/config files retain identical bytes. Existing
  rows remain intact. Three live job/lease tables differ: one additional107-photo
  legacy job failed on the existing default Ollama service at19:59; its107 photo
  relationships were retained. Worker lease heartbeats also changed. No source,
  answer, approval, signature, upload or credential was reset to conceal this.

## Implemented behavior

Engineer capture uses the existing saved task and authenticated photo endpoints.
It shows four categories, bounded multi-upload, progress/failure retry, original
preview, pre-submit move/remove and one Submit to QA action. Removal excludes a
photo from active capture while retaining its original row/file/history. Engineer
matching, confidence, AI verification and all legacy AI endpoints are unavailable.
Historical checklist answers and signatures remain stored.

Submission freezes source/category hashes, creates the existing persistent AI
revision/job and immediately advances the real task to QA. Checklist completion
is no longer an Engineer photo-submission prerequisite. Necessary reviewer,
identity, permission and upload-session checks still apply. Repeats reuse the
same revision/job. AI failure retains the QA submission and photos and permits
manual review when its approved checklist is available. A missing template keeps
the submission visible with an explicit configuration error; matching/completion
wait for authorized template configuration and a valid submitted revision.

QA has category/checkpoint/photo panes, distinct item/photo counts, approved
requirements, source viewer/AI details, confirmation/correction/unlink, native
drag/drop and touch/click alternatives. The last Not Assigned entry remains
visible at zero and counts only globally unlinked photos in the selected source
category. Display order is personal and does not edit the template. Assignment,
confirmation and work acceptance are separate. QA completion freezes the derived
review package; the existing engineering approval action remains distinct.

All edits are authenticated, named-QA/project/task/photo/field/revision scoped,
audited and guarded by source/review digests and approved locks. Late AI does not
erase manual corrections. Reassignment removes only the explicit old link and
retains other valid links. Failed saves leave the prior state visible. Client
return through Team Lead reopens only current authorized QA locks; historical
signatures remain. Team Leads use the same compact workspace read-only.

The twelve owner layout references and `Notes for Layout.txt` under
`F:/iSurvix/references` informed layout only. No reference customer evidence,
branding or requirements were imported.

## Agency ownership and independent review

Installed definitions under `C:/Users/Muhammad Assim Baig/.agency-agents` were
read and applied: Orchestrator/integration lead, Backend Architect, UX Architect,
Frontend Developer, Reality Checker/API Tester, and Application Security Engineer.
Backend, frontend, independent functional QA and AppSec had separate ownership.
This uses the installed role definitions in agent sessions; it does not claim
automation of the separate Agency desktop application.

The independent AppSec reviewer reproduced and verified repairs for six defects:

1. Legacy Engineer AI JSON reads bypassed the simplified UI.
2. Optional, unaccepted AI findings could appear in a Client projection.
3. Alternate capture views exposed detailed processing errors to other roles.
4. Client rejection followed by a valid QA return left obsolete active locks.
5. Current exports/field-photo reads could revive an unlinked legacy image.
6. Older governance aliases allowed Admin/Team Lead mutation of frozen category
   sources. Unmarked legacy edit behavior remains supported.

## Executed checks

Initial Engineer/QA audit run: **894 tests passed in283.484 seconds**, zero failures, errors or
skips; native process exit0. The application/test source SHA256 fingerprint was
identical before and after the entire run:
`78a38a1ee08c1d9c303205a3cf02c9f8b2e8e35f675eb7a1ee11add490531d19`.

The subsequent Engineer bulk-selection follow-up passed **903 tests** and120
desktop/mobile/lazy-thumbnail browser assertions. Its final source fingerprint,
commands and evidence are in `ENGINEER_BULK_CATEGORY_MOVE.md`.

The machine-readable42-requirement ledger and final full-suite result are in
`ENGINEER_CATEGORY_QA_WORKFLOW.json`. Private raw receipts are under
`.local/engineer-category-qa-20261023`; they include fixture credentials and must
not be published wholesale.

Commands from the project root:

```powershell
.local\venv\Scripts\python.exe scripts\run_backend_tests.py
.local\venv\Scripts\python.exe backend\manage.py check --settings=checklist.settings_local
.local\venv\Scripts\python.exe backend\manage.py makemigrations --check --dry-run --settings=checklist.settings_local
.local\venv\Scripts\python.exe backend\manage.py migrate --check --settings=checklist.settings_local
.local\venv\Scripts\python.exe -m pip check
```

All four retained `frontend/check-*.cjs` scripts and33 backend JavaScript syntax
checks passed. Retained frontend VM checks are distinguished from real Edge
browser verification. `git diff --check` passed. Earlier full-suite failures were
investigated: tests of retired Engineer checklist/AI HTTP behavior were moved to
the actual permitted QA/Team Lead operations, retaining explicit Engineer denial,
worker failure/recovery, source preservation and approved-lock assertions. Legacy
history service tests remain explicit historical tests. No test was skipped or
fake HTTP success substituted to preserve the old behavior.

Independent focused results (overlapping, not summed):47 acceptance/regression
tests and59 AppSec tests passed. Actual Edge journeys passed74 behavioral checks
plus44 final read-only visual/state checks at1440px and390px. No unhandled JS
exceptions were observed. Final screenshot refresh made zero writes and retained
all12 fixture business tables and28 original file hashes.

Saved-data browser coverage includes Engineer category uploads,503 retry,
move/remove, immediate QA, drag/drop and touch assignment, same-category display
ordering, refresh, failed-save rollback, queued/failed AI manual review, QA
completion, Team Lead rejection, Engineer resubmission and Client
rejection/clarification/closure. Actual Excel export was opened and its reviewed
values and embedded source checked. Existing drawing checks remain in the full
suite; this focused change does not claim a new field/CAD acceptance benchmark.

## Actual local vision

Installed qwen3.5:4b advertises vision. Actual requests to default11434 fail with
HTTP500/missing `llama-server.exe`. The already installed, signed project runtime
`.local/runtime/ollama-0.40.5` and existing model store work on loopback11435.
No model download, paid service or public Ollama exposure was introduced.

Eleven synthetic images passed actual native job processing: a two-image retry,
a seven-image late-AI run and a final fresh two-image submission. The latter used
the actual final code, approved contact/manufacturer IDs and pixel-only labels;
it produced advisory Taylor Example/KESTREL-72 links. Explicit confirmation of one
link left both engineering items unaccepted. The source revision and original
bytes stayed unchanged. Receipt:
`.local/category-native-final-20261023/verified-native-proposals.json`.

An older pinned-job model-identity mismatch was deliberately retained as a visible
error rather than silently changing its model identity. Queue/retry recovery was
separately verified on a fresh unpinned job. The main site's old failed job has
not been retried or repinned by this task.

## Windows start and update

For normal use, close the old launcher and double-click `Start-iSurvix.cmd` in
Explorer. It starts the dedicated local photo runtime and existing workers, then
opens the app. Do not run duplicate launchers/workers. Keep `.local` intact during
updates. Never reset the database or download a replacement model for this fix.

For manual startup, run the following in PowerShell from the project root; keep
each long-running app/worker command in its own terminal:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\Start-PhotoAI.ps1 -Model qwen3.5:4b -Port 11435
$env:ISURVIX_PHOTO_OLLAMA_URL='http://127.0.0.1:11435'
.local\venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8000 --noreload --settings=checklist.settings_local
```

In each worker terminal, set the same photo URL before its command:

```powershell
$env:ISURVIX_PHOTO_OLLAMA_URL='http://127.0.0.1:11435'
.local\venv\Scripts\python.exe backend\manage.py survey_processing_worker --settings=checklist.settings_local
```

Retain the existing `photo_worker` and `photo_search_worker` commands for older
jobs/search, with the same environment and settings. Existing pinned failed jobs
need explicit operator review; they are not automatically reset by startup.

The local app is at `http://127.0.0.1:8000/`. This is a loopback development
service, not a public deployment. No production merge or deployment is authorized
by this delivery.

## Remaining limits

- Real-site matching accuracy, large-site sustained throughput and physical
  phone/tablet usability require field acceptance; eleven synthetic images do
  not establish five photos/second or500-photo performance.
- Default Ollama11434 needs native runner repair separately; the existing11435
  project path is verified. Historical native crash A12 remains unexplained.
- Ambiguous custom checkpoint categories fall back honestly to General Info;
  the published template is never changed to guess a category.
- Missing manufacturer references, measured site geometry, CAD compliance and
  production hosting/TLS/Nginx acceptance remain their own dependencies.
- All42 focused requirements are verified in the recorded isolated environment;
  this does not imply universal correctness or completion of unrelated modules.
