# Survey release hardening — 21 October 2026

Review baseline: `79d977227e88db0ddab437aca3ffd3a6da5c60fb`.
Feature branch: `feat/secure-outbound-survey-workers`. No production deployment or merge is performed.
The authoritative acceptance ledger is [development/RELEASE_HARDENING_REQUIREMENTS.json](development/RELEASE_HARDENING_REQUIREMENTS.json).

## What changed

* Every direct `/media/` path is denied by the Nginx example. Existing authenticated,
  project-scoped photo/document/output routes remain; retained legacy attachments
  now use an authorised exact-record file endpoint. The production URLconf includes
  these existing photo/review routes too. Files are streamed by Django, not a public alias.
* Upload envelopes track browser heartbeats and concurrent transfer leases. The
  assigned Engineer, project Admin or Team Lead can recover an interrupted/stale
  envelope with a reason. A live batch prevents recovery. Completed files remain.
  Recovery and closure are idempotent and audited. A delayed expired upload cannot
  append files after recovery and a new submission.
* Progress polling fetches small status summaries. Selected revision details,
  findings, audit history and retained drawing editions load separately. The
  interface pauses in hidden tabs, backs off when idle/offline, and pauses mutations
  until an authoritative refresh succeeds. Revision selection survives reload.
* An outbound PC worker now retrieves scoped jobs and normalized inputs from the
  website. It uses the existing loopback Ollama model and returns validated
  proposals into the existing Django pipeline. Credentials expire, leases heartbeat,
  checkpoints survive interruption and duplicate results cannot replace immutable
  records. Software versions are pinned; mismatched implementations are rejected.
* Native mapping now constrains model output to the exact submitted source keys
  and selected checklist IDs. Unknown, repeated and contradictory bindings still
  fail independent validation. The actual schema counts against the prompt bound.
* Ordinary automated tests use temporary databases/media/model directories and deny
  external network access. Native Ollama verification is separate.

Migrations `0048`, `0049`, `0050` are additive. Original evidence, branding,
approved records and previously generated files are preserved. No model download,
cloud inference, operational approval or public Ollama listener was introduced.

## Local Windows operation

Keep the checkout and data at `F:\iSurvix\iSurvix-Field`. For the normal local
application, double-click **Start-iSurvix.cmd**. For explicit process startup, from
that directory, first follow the backup/migration update steps below. The launcher
runs local setup/migrations; a direct `runserver` command does not:

```powershell
.local\venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8000 --noreload --settings=checklist.settings_local
.local\venv\Scripts\python.exe backend\manage.py survey_processing_worker --settings=checklist.settings_local
```

Run those two commands in separate windows for projects processed entirely on this
PC. Keep the configured Ollama endpoint on loopback and the already-installed
`qwen3.5:4b` available. Do not start a second consumer for the same queue.

For a hosted website, use the existing local environment with the separate outbound
worker instead of sharing its production database:

```powershell
.local\venv\Scripts\python.exe backend\manage.py remote_survey_worker --settings=checklist.settings_local --config .local\private\remote-worker.json
```

The project Admin provisions that private file on the server. Exact provisioning,
revocation, credential transport, update and rollback instructions are in
[REMOTE_SURVEY_WORKER.md](REMOTE_SURVEY_WORKER.md). The website remains usable and
jobs wait safely while the PC is offline. Expired worker connections show a saved
checkpoint/reconnection message.

Before updating the actual local database, use the established checkpoint process,
review the migration plan and stop the application/worker normally. Apply the
reviewed migrations, then restart. This verification used separate isolated
databases and did not restart or migrate the operational instance on port 8000.

```powershell
.local\venv\Scripts\python.exe .local\save_project_checkpoint.py
.local\venv\Scripts\python.exe backend\manage.py migrate --plan --settings=checklist.settings_local
.local\venv\Scripts\python.exe backend\manage.py migrate --settings=checklist.settings_local
```

## Engineer, reviewer and release guide

1. Open the assigned saved survey, complete its required site data and upload photos
   in bounded batches. Add PDF/workbook/sketch evidence under **AI Checklist & Drawings**.
2. Finish active uploads. If an old interrupted upload blocks submission, inspect
   its owner/activity and use **Recover abandoned upload** with a reason when
   permitted. A genuinely active batch must finish or its lease must expire.
3. Confirm uploads are complete and submit. Repeated submission reuses the same
   immutable revision/job. Changed inputs retain a new revision.
4. Review proposed checklist answers and linked evidence. Correct uncertain data,
   resolve conflicts and explicitly accept reliable proposals. A photo alone is
   not compliance. Unsupported measurements remain missing.
5. Add drawing geometry only from checked recorded measurements and units. Generic
   envelopes are identified as typical; source evidence remains linked. Complete
   the explicit Engineer apply/review action.
6. Assigned QA reviews the exact package. Complete the normal project review
   route (Engineer → QA → Team Lead → assigned Client when required).
7. The authorised Team Lead releases outputs only after the route closes. Clients
   see appropriately released outputs, with no internal AI proposals or comments.

Use **Load more** for retained findings, history and drawing editions. A previous
input revision remains available, but cannot replace the current release. A failed
save or offline refresh pauses edits until saved state is reloaded.

An implementation-version change deliberately cannot reuse an incompatible worker
lease/checkpoint. Align the server and PC to the original reviewed release to resume
that revision. If source inputs genuinely change, submit the changed inputs as a
retained new revision. Do not edit version pins, original snapshots or approvals to
force a retry through an upgrade.

## Reproduce automated checks and performance measurements

```powershell
.local\venv\Scripts\python.exe scripts\run_backend_tests.py --verbosity 2
.local\venv\Scripts\python.exe backend\manage.py check --settings=checklist.settings_local
.local\venv\Scripts\python.exe backend\manage.py makemigrations --check --dry-run --settings=checklist.settings_local
.local\venv\Scripts\python.exe -m pip check
cd frontend
node check-preview.cjs
node check-workspace.cjs
node check-engineer.cjs
node check-site-routing.cjs
cd ..
```

The four frontend scripts check the retained development preview; actual Django
browser checks are recorded separately. The isolated runner uses the real Django
test database and standard hashers; it permits only HTTP listeners created inside
the same test process. It does not prove native model quality.

The optional benchmark creates synthetic records only in its dedicated `.local`
database. It never touches the operational survey database:

```powershell
.local\venv\Scripts\python.exe scripts\benchmark_survey_progress.py --seed
.local\venv\Scripts\python.exe scripts\benchmark_survey_progress.py --phase current
```

The seed refuses to overwrite an existing fixture. Measurements use 20 revisions,
200 photos/fields, 8,000 findings, 4,000 source checkpoints, 400 events and 40 draft
editions. The measured local baseline was 1,737.961 ms / 176 queries / 11,715,760 bytes
per full status update. Final progress was 7.118 ms / 12 queries / 4,623 bytes;
selected detail was 63.975 ms / 28 queries / 423,335 bytes (five samples, medians).
These are test-client measurements on this PC, not internet latency or AI throughput.

## Evidence and remaining operational dependencies

Current test counts, browser/native receipts, sample exports and requirement results
are recorded in [development/RELEASE_HARDENING_EVIDENCE.json](development/RELEASE_HARDENING_EVIDENCE.json).
Checked synthetic examples are under [../samples/drawings/release-hardening-20261021](../samples/drawings/release-hardening-20261021).

The authorised Z93004 source inventory contains 378 JPEGs, one workbook with 150
embedded images, one MP4 and four PDFs (two duplicate reference sets). The available
4-page antenna and 11-page survey drawings are marked **FOR REVIEW**, not verified
manufacturer CAD or an approved dimensional baseline. A bounded native electrical
photo benchmark is reported separately; it is not full-site accuracy or sustained
200/500-photo throughput verification. Unsupported manufacturer/site geometry must
remain missing until verified source measurements and references are supplied.

Live VPS DNS/TLS, private environment values, database backup/migrations, Nginx and
systemd installation, Admin credential provisioning/transfer and real public HTTPS
verification require server access. Before activation, set the service working
directory/Gunicorn paths to the checkout's `backend` directory, Nginx static alias to
that directory's `staticfiles`, and replace historical domain/IP placeholders. No
production service was deployed, merged or exposed by this task.
