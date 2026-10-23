# QA AI processing, recovery and progress

23 October 2026. Follow-up on `fix/engineer-general-information-20261023`,
starting at `52a0881`. Recovery archive:
`.local/backups/project-checkpoint-20261023-230246` (2,507 files, SQLite integrity
and ZIP CRC verified). Existing sources, submissions and operational decisions
remain preserved.

The owner reported that AI still appeared unavailable in QA, requested a progress
bar beside the numerical count, and asked about using 50% of the GPU for speed.

## Actual reproduction

The QA photo workspace is different from the text assistant tested previously.
Read-only inspection found a current 460-photo submission actively persisting
source analyses, a separate 400-photo job waiting in the local queue, and a failed
historical revision. Final checklist suggestions are assembled after the submitted
evidence has been analysed; zero proposed links during extraction does not mean
that no photo processing occurred.

The old processing pin hashed the entire Ollama `/api/show` response, including
installation-specific information. The repaired service returned a different pin.
The two installed stores contain matching model/projector/configuration layers;
the changed pin alone does not prove the weights changed. The GUI launcher also
previously selected the dedicated service even when the installed local service
already reported the required local vision capability.

The current GPU is an NVIDIA GeForce RTX 3060 Ti with 8 GB VRAM. Direct samples
showed approximately 74–75% GPU activity and 5.2 GB total VRAM use. `ollama ps`
reported the model entirely resident on the GPU, which is a placement indicator,
not a claim of 100% compute utilization. No GPU power, driver, clock or percentage
cap was changed. Restricting current activity to 50% would not provide additional
processing capacity. These samples do not establish sustained photo throughput.

## Ownership

Installed Agency Backend Architect owns model identity/recovery, endpoint checks
and backend regressions. Frontend Developer/UX Architect owns the existing QA
status markup, styling and controls. Independent Reality Checker/API Tester owns
actual QA browser reproduction, regression review and saved-data verification.
The application lead owns the recovery checkpoint, launcher consistency, GPU
inspection, integration and delivery. No additional roles or modules are added.

## Requirement evidence

| Expected behavior | Verification | Status |
| --- | --- | --- |
| Verify actual QA photo-job state, distinct from text chat and historical failures | Assigned-QA browser/API, persisted source count and worker state | Verified |
| Display a visible progress bar directly beside numerical progress on desktop and mobile | Real browser rendering, count/percentage and stage checks | Verified |
| Distinguish queued, analysing, mapping, ready and failed states without fabricated progress | Saved-state and negative browser checks | Verified |
| Pin the actual photo endpoint's installed manifest; ignore volatile installation metadata | Identity and endpoint regressions, live metadata-only verification | Verified |
| Preserve legacy pins unless exact metadata proof establishes compatibility | Positive/negative cache and pin migration tests | Verified |
| Allow explicit assigned-QA recovery only with zero prior inference/results/drawings and unchanged unlocked sources | Auth, cross-project, stale, lock, duplicate and rollback tests | Verified |
| Fetch model metadata outside the database write lock and recheck before saving | Transaction/permission regression and independent review | Verified |
| Retain completed inference, original bytes, immutable submissions and human decisions | Preservation evidence and existing workflow regressions | Verified |
| Reuse an existing suitable local service at GUI startup; retain the existing fallback | Actual PowerShell selection-block tests | Verified |
| Verify current GPU acceleration and report its limits honestly | NVIDIA counters, `ollama ps`, official Ollama documentation | Verified |
| Run the final source-stable backend suite and repository checks | Native test exits and stored receipts | Verified |

Private evidence is under `.local/qa-ai-live-20261023`; authentication, browser
profiles and source metadata must remain local. Current native work is not a
destructive test, and no operational engineering decision is made by this repair.

## Verified repair

- The visible QA bar is directly beside the saved count and percentage. Queued,
  analysing, preparing, ready and failed states remain distinct. Preparing stages
  use an indeterminate bar; they do not claim that photo count is overall completion.
- Installed model identity uses the verified manifest on the photo endpoint.
  Legacy opaque pins migrate only when current metadata reproduces the exact old
  hash. A scoped remote worker uses the same identity and audited proof rules.
- Assigned QA can explicitly select the current model only for an unchanged,
  unlocked submission with no completed source analysis, result or drawing. A
  reason and confirmation are required; stale/cross-project/unauthorized requests
  are denied. Repeat delivery produces one audit event. Metadata requests run
  outside the database write lock and all conditions are checked again before save.
- The launcher reuses a suitable installed service instead of always selecting
  another model store. Missing native-runner guidance explicitly calls for
  repairing/restarting Ollama. Model capability metadata is not a substitute for
  the worker's actual image analysis.
- Resume no longer writes a smaller completed count while walking cached sources.
  The regression first reproduced `[1,2,3]` after a saved checkpoint of2; it now
  records `[2,2,3]`, preserves cached payload hashes and infers only the missing
  source. No response validation, uncertainty or human-review guard was relaxed.

## Actual workflow evidence

Independent QA opened four real operational pages at1440px and390px, with zero
JavaScript errors or horizontal overflow. The saved count advanced54 to55/460
over35seconds, with the bar and number beside each other. This establishes
progress, not completion or sustained throughput. Operational customer images
remain private; committed screenshots show only clearly synthetic data.

The worker was handed over at a saved68-photo boundary. All68 previous analysis
digests were retained, the exact legacy identity was migrated with an append-only
proof event, and real native analysis continued without reducing the count. Only
the stopped worker's lease was expired; source snapshots, answers and approvals
were untouched. The first process-stop command encountered the already-exited
Windows wrapper and rolled back its database transaction; verified process-death
recovery then completed the fenced handover. The native Ollama service was not
restarted.

The separate400-photo job had zero source analysis and an obsolete opaque pin.
Under the owner's retry instruction it was recovered through the existing scoped
QA action with an explicit reason and current-model metadata verification. It
retained the same source/review digests, job and revision, with one recovery audit.
It remains queued behind the active460-photo job. This maintenance used the
assigned QA authorization context directly, not a claimed browser action; no
interactive session was rotated by that maintenance call.

Independent isolated verification covered eight saved states on desktop/mobile:
55 final read-only browser assertions,55 guard/preservation assertions and26
focused backend tests passed. The positive browser recovery used real installed
model metadata, kept all24 synthetic originals/eight snapshots and was idempotent.
A first harness assertion misclassified intentionally blocked CDN GETs as
mutations; that raw receipt is retained, and the corrected browser rerun passed.
Source-endpoint wrapper and cached-header/new-script defects encountered during
implementation were repaired and checked at the real transport/browser boundary.

Final stable full backend run: **948 passed in 330.540s**, native exit0, no failures/errors/skips. Source fingerprint: `4de1e621f7551ea6ea0420c5a5b84a6e1ab065b9bed11f617638722763e0f4ff`.

Django checks, migration drift/pending migrations, dependency check, four retained
frontend scripts,33JavaScript syntax checks, PowerShell launcher syntax/selection
checks and Git whitespace checks passed. Focused/browser counts overlap the full
suite and must not be added into a unique total. The recovery checkpoint's1,762
media/private files matched their hashes; all59core tables were compared,
existing original/hash/task references remained intact and SQLite integrity passed.

Exact principal commands:

```powershell
.local\venv\Scripts\python.exe scripts\run_backend_tests.py
.local\venv\Scripts\python.exe backend\manage.py check --settings=checklist.settings_local
.local\venv\Scripts\python.exe backend\manage.py makemigrations --check --dry-run --settings=checklist.settings_local
.local\venv\Scripts\python.exe backend\manage.py migrate --check --settings=checklist.settings_local
.local\venv\Scripts\python.exe -m pip check
```

The app and workers continue using repaired loopback11434/qwen3.5:4b. Existing
Windows startup commands are in the local handoff. No new model, cloud service,
schema, role or product module was added. The current submissions are still
processing/queued; whole-site completion, accuracy and throughput remain
unverified. A historical failed revision stays retained. The large review-state
response remains a separate performance follow-up; this repair does not claim a
new sustained photos/second rate or an exact GPU utilization cap.
