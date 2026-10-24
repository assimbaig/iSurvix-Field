# QA two-pane review and evidence reuse

24 October 2026. Follow-up to the owner's revised QA requirements on branch
`fix/qa-guided-documents-pause-20261024`. The earlier working feature is retained
in checkpoint `9ad13ec`; the pre-edit source/data archive remains
`.local/backups/project-checkpoint-20261024-140010`.

## User workflow

The blue Site information / Review evidence / Decision subheading tabs remain
aligned on desktop and wrap within the available mobile width.

Site information is one table and one scrolling work area. Approved checklist
fields appear first, followed by all submitted source facts. Edit unlocks one
permitted QA value; Save requires a source-backed note, saves through the existing
audited answer service and relocks the cell. Cancel preserves its saved value.
System identity can be explicitly confirmed without changing it. Submitted source
values, source-only facts and approved sections remain protected. Their reasons
are displayed rather than presenting fake Edit controls. On mobile the actions
remain available inside the same table and Edit brings the QA value into view.

Review evidence has two panes: one compact category/section/checkpoint tree and
the photo workspace. The tree keeps General Info as site data, Civil/Electrical/
Tower groups, required zero-evidence checkpoints, expansion controls and Not
Assigned. The right pane retains the viewer, thumbnails, single/multiple selection
and the approved point's instruction. Assign selected adds evidence links. Move
selected links moves only links from the selected checkpoint and requires a
reason; other valid links and Engineer upload categories remain intact. Failed
or partial saves report their actual result. Assignment, confirming a match,
accepting a QA answer and engineering approval remain separate actions.

## Processing changes

Repeated QA progress polling now uses the actual private scalar endpoint
`/local/photos/<id>/capture/review/progress/`. Counts/status update without
reloading all evidence. A selected photo can load only its saved observations.
A changed review token, result or stage refreshes details; each count tick does
not. Hidden tabs, dirty edits, backoff, failure/recovery messages and manual QA
review while AI is pending/failed remain supported. Permission checks no longer
eagerly load large historical snapshots; snapshots still load when actually used.

The local worker reuses raw observations only when the inference input matches:
actual normalized image bytes, text, recorded metadata, source reference/type,
field catalog, full approved schema/template, model identity, prompt, extraction
version, output schema and inference options. Search stays within the same task
and the latest twenty compatible revisions. Changed data/context or corrupt
cache records cannot silently reuse a result. Reused findings receive current
source IDs and remain unverified; human answers, link confirmations, decisions
and release approvals are never imported from an older review.

Metadata identity checks and fully reusable work no longer occupy the GPU
inference lease. The Windows launcher starts two existing durable survey-worker
consumers, sharing one GPU inference slot. A cached submission can therefore
finish while another task performs native inference; new model requests remain
serialized through the existing shared lease.

Exact duplicate annotations use the full decoded source pixels after EXIF
orientation. Similarity hashes produce only Possible duplicate advisories.
Similarity is never an inference-cache key. Originals, photo IDs and valid links
are retained. Legacy immutable analyses can gain independently verified
fingerprint annotations through an append-only event without being rewritten
or inferred again. A photo may show Reused analysis separately from its
duplicate label; reuse does not confirm the match or accept the work.

## Measurements and limits

On the same synthetic project, task, actor and database with twenty historical
revisions, 200 photos, 200 fields and 2,000 current findings:

| Request | Median | Queries | Response bytes |
| --- | ---: | ---: | ---: |
| Full review formerly used on each tick | 256.234 ms | 41 | 4,306,668 |
| Scalar progress | 5.500 ms | 10 | 251 |
| Progress plus one photo's observations | 6.395 ms | 12 | 10,519 |

Five real ORM/serialization samples were collected for each handler. This is a
serialization measurement on synthetic metadata, not an upload or model-throughput
benchmark. Evidence: `.local/qa-resume-20261024/qa-progress-performance.json`.

The actual installed qwen3.5:4b processed a synthetic photo and rasterized PDF in
an isolated saved-data workflow. That first pass made two real image requests;
the unchanged Engineer resubmission then reached Ready for review in **1.578s**
with **zero generation requests** and both raw analyses reused. The first pass
took **46.922s** including contention with the operational GPU queue. The second
pass completed while another task deliberately held the GPU lease. Prior source
hashes were retained and no answer was automatically accepted. This establishes
reuse across real revisions, not the speed of new unique photographs. Evidence:
`.local/qa-resume-20261024/native-reuse-final/result.json`. Independent QA
recomputed both cache identities against the final source and verified the
actual native-result badges using an isolated read-only database copy. Earlier
native measurements used a subsequently changed identity and remain diagnostic.

A paired compact-JSON experiment did not demonstrate an improvement: two sources
generated703 canonical versus714 compact output tokens; native decoding was
also slower for the compact experiment. Production therefore keeps the canonical
output format, context, image resolution and evidence requirements. The strict
compact decoder remains explicitly opt-in for controlled comparisons, without
a product setting. Measurements use the API's native token/timing fields.
[Ollama usage metrics](https://docs.ollama.com/api/usage).

GPU sampling found the RTX3060Ti/8GB already processing on the GPU. More parallel
requests multiply context-memory requirements; an unmeasured parallelism change
was not enabled on the running field queue. No shared-memory forcing, clocks,
power limits, extra model download or paid/cloud fallback was introduced.
[Ollama concurrency and memory guidance](https://github.com/ollama/ollama/blob/main/docs/faq.mdx#how-does-ollama-handle-concurrent-requests).

New unique photos still require local inference. Sustained200/500-photo throughput,
physical-device behavior, manufacturer/site accuracy and a Z93004 benchmark are
not established by these synthetic checks.

## Verification and security

New functional checks include failing browser reproductions for the old three-pane
layout and missing table/cell controls, unit/integration tests for cell permissions
and preserved evidence, actual single/bulk matching, failed saves, scroll/keyboard
and mobile behavior, lightweight polling, exact/possible duplicates and badges
from a read-only copy of the actual native-reuse database. Seven frontend scripts
pass; the latest receipt contains **71 unit assertions**. The final source-stable
backend run passed **1,030 tests in 344.692s**, with zero failures, errors or
skips, zero external network attempts and 33 in-process HTTP fixture connections.
Command: `.local\venv\Scripts\python.exe scripts\run_backend_tests.py`.
The before/after source fingerprint was
`110152861b8d06dee79154bb44a2deaaf125abf3ba3a7a45782aa8cbf1155cf2`.
Django system checks, migration drift, pending migrations and `pip check` passed.
PowerShell readiness tests (five cases), the two-consumer startup unit check and
startup/helper syntax parsing also passed. These ordinary tests use isolated
database, media and model-cache directories; the native checks are separate.
Independent QA recorded **212 successful browser assertions across17 runs**,
including79 assertions for the latest refinements. Desktop1440/mobile390 layouts,
actual saved matching, failure recovery, per-cell edits, revision provenance and
the Engineer-to-QA-to-Team Lead/Client synthetic lifecycle were exercised. No
JavaScript exceptions occurred in these successful runs. The evidence checklist
records41 verified scoped behavior/procedure rows; its security-review row means
the review was performed, not that the findings below were remediated. Latest
preservation checks found1,915 preexisting files unchanged and no deleted records,
prior immutable-record edits or changed operational approvals. Running workers
can legitimately append later analyses/events and update leases/progress.

Security reviews are separate from implementation:
`SECURITY_REVIEW_QA_DOCUMENTS_PAUSE_20261024.md` and
`SECURITY_REVIEW_QA_REFINEMENT_20261024.md`. The closing refinement review executed
fourteen adversarial probes (including its earlier ten) and rechecked the prior
thirteen without external or model calls. Some
probes reproduce an undesirable state; their successful execution is not a
security acceptance certificate.

Unapproved S1 Medium (old Resume replay), S2 Low (Admin retained-file route policy)
and S3 Low (missing-task500) remain unchanged. New R1 Low records same-task photo
membership versus submitted-revision membership in progress, returning empty
observations. Warm duplicate-cache integrity and future parser-version discipline
are hardening observations. New **R2 Low** records partial launcher startup:
failure to start the second survey worker can leave the first outside the
caller's cleanup scope. Normal exit cleanup covers both workers. Recommended
remediation is one cleanup scope covering all startup with handles captured as
each process starts. This finding has not been fixed. No new Critical/High/Medium
exploit was established in the refinement review.
These findings require owner approval before remediation.

## Start and review

Double-click `Start-iSurvix.cmd`; local access is `http://127.0.0.1:8000/login/`.
The existing project runtime on loopback11435 is verified. The standard installed
11434 service still has a missing runner binary and is not treated as ready merely
because metadata responds. Exact manual app/worker commands and formats/limits
are below; formats/limits remain in `QA_REVIEW_DOCUMENTS_PAUSE_20261024.md`.

For manual startup, use separate PowerShell windows in the project root. Set both
variables in **each** app/worker window:

```powershell
$env:ISURVIX_OLLAMA_URL='http://127.0.0.1:11435'
$env:ISURVIX_PHOTO_OLLAMA_URL='http://127.0.0.1:11435'
```

Start the app once:

```powershell
.local\venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8000 --noreload --settings=checklist.settings_local
```

Start **two copies**, in separate windows, of the durable survey consumer:

```powershell
.local\venv\Scripts\python.exe backend\manage.py survey_processing_worker --settings=checklist.settings_local
```

Start one of each existing photo/search worker:

```powershell
.local\venv\Scripts\python.exe backend\manage.py photo_worker --settings=checklist.settings_local
.local\venv\Scripts\python.exe backend\manage.py photo_search_worker --settings=checklist.settings_local
```

If the project-local runtime is stopped, use the installed existing model:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\Start-PhotoAI.ps1 -Model qwen3.5:4b
```

To test manually: open an assigned QA task; edit one permitted Site information
cell with a source-backed note; save and refresh; switch to Review evidence;
expand a category; select a checkpoint; assign or move one/multiple photos and
refresh. Confirm failed saves retain input, unassigned/zero-evidence points stay
visible, and matching does not approve engineering work. Pause/Resume is scoped
to the current AI revision and stops at a durable source boundary. Review known
security findings before using this candidate beyond local testing.

The updated app/worker processes must load the new Python code; static-file changes
alone do not update a running `--noreload` server. Restart preserves completed
analyses and durable jobs; an in-flight source may retry after its saved lease
expires. No operational record was approved/rejected by the test harnesses.
