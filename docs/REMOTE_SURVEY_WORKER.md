# VPS website with an outbound local survey worker

The website, authentication, original evidence, immutable jobs, source checkpoints,
checklist proposals, review decisions and PDF/DXF files remain on the VPS. The PC
makes outbound HTTPS requests and runs the existing bounded evidence and mapping
functions against its loopback Ollama. The PC opens no inbound service. It never
connects to the VPS database, approves a survey or releases an output.

## Deployment prerequisites

Use the same reviewed commit and Python dependencies on the server and PC. Worker
protocol, pipeline, evidence, mapping versions and evidence/mapping implementation
hashes must match (Windows/Linux line-ending differences are normalized). Do not copy the development SQLite database over a live server
database. Migrate the intended database after a recoverable backup. Preserve all
original evidence and branding. Keep `DEBUG=False`, set a private
`DJANGO_SECRET_KEY`, configure `DJANGO_ALLOWED_HOSTS`, and use a valid HTTPS
certificate. The supplied Nginx example denies the entire `/media/` prefix;
authenticated Django endpoints deliver files after project and role checks.

`backend/isurvix-field.env.example` lists the production variables. Create the real
`/etc/isurvix-field.env` privately, replace all placeholders, and restrict it to the
service owner before installing the service. Update the `YOUR_USER`/application
paths in the supplied systemd and Nginx examples to the actual checkout. The
systemd service reads this environment file and uses `UMask=0077` for new files.
Keep the existing server database/media paths intact unless a separately verified
data migration is deliberately scheduled.

The VPS needs the ordinary application/drawing dependencies, including Pillow,
PyMuPDF, openpyxl, ReportLab and ezdxf. It does not need Ollama or a GPU. Do not run
the local `survey_processing_worker` for remotely assigned projects; its claim
function deliberately excludes those queues. The web application stays available
and jobs remain queued when the PC, network or local model is unavailable.

The revised `backend/deploy.sh` defaults to validation only. It never upgrades
packages, recursively changes permissions, installs firewall rules, starts TLS
issuance or restarts services. Its explicit `--apply-reviewed-migrations` mode
requires `ISURVIX_BACKUP_VERIFIED=yes` after the intended backup has actually been
verified, then applies migrations and collects static files; release/restart
remains a separate reviewed operational step.

## Server preparation and credential provisioning

Run from the server checkout's `backend` directory with the production environment
loaded and the server virtual environment active:

```sh
python manage.py check --deploy --settings=checklist.settings
python manage.py migrate --plan --settings=checklist.settings
# After the planned database backup and release review:
python manage.py migrate --settings=checklist.settings
python manage.py collectstatic --noinput --settings=checklist.settings
python manage.py provision_survey_worker --settings=checklist.settings \
  --admin PROJECT_ADMIN_USERNAME --project PROJECT_ID \
  --server-url https://YOUR_DOMAIN \
  --output /PRIVATE_DIRECTORY/isurvix-worker.json --hours 720
```

Repeat `--project PROJECT_ID` to scope one PC to several projects administered by
that same Admin. Provisioning verifies the Admin's current role, company,
membership and project ownership. The token expires in 30 days by default (maximum
90 days). Only its SHA-256 hash is stored on the server. The command writes the
token once into a new exclusive file, restricts POSIX permissions or Windows ACLs,
and never prints it. Existing files are not overwritten. Transfer this file to the
PC through a private encrypted channel; do not email, commit or put it in media.

The configuration enables remote processing for those projects. Existing jobs
and previous results are preserved. Provisioning and remote claim, completion,
interruption, failure and revocation events appear in the governance audit.

To revoke a PC credential, use the UUID `credential_id` from the private file:

```sh
python manage.py provision_survey_worker --settings=checklist.settings \
  --admin PROJECT_ADMIN_USERNAME --revoke CREDENTIAL_UUID
```

Revocation stops subsequent requests, including downloads and heartbeats. No
evidence or results are deleted. The queue remains recoverable after the active
lease expires and a replacement authorised PC connects. Credential revocation
does not silently switch the project to a different inference provider.

## Windows PC startup

Keep the checkout and private files under `F:\iSurvix\iSurvix-Field`. Save the
transferred configuration as `.local\private\remote-worker.json`. Start the
already-installed Ollama with `qwen3.5:4b` and keep it bound to loopback. Do not
download another model or expose port 11434/11435 publicly.

From the project folder, run:

```powershell
.local\venv\Scripts\python.exe backend\manage.py remote_survey_worker --settings=checklist.settings_local --config .local\private\remote-worker.json
```

For a single queued job, append `--once`. The command validates installed local
vision capability before claiming work. Normalized images are downloaded in
bounded, hash-checked requests; the actual image content reaches the existing
vision function. Checklist mapping uses bounded text batches after analysis.

The local result cache defaults to a private `remote-worker-cache` directory next
to the configuration file. It is restricted to the current OS user. Completed
inference is cached atomically before upload so an interrupted result transfer can
resume without repeating that inference. Server source checkpoints remain the
authoritative record. Preserve this cache during updates; it contains private
derived evidence and must never be served by the website.

The optional normal local website remains independent:

```powershell
.local\venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8000 --noreload --settings=checklist.settings_local
```

## Processing, recovery and review

An assigned Engineer completes the real survey/uploads and submits the approved
checklist-required survey. A server job waits safely for an authorised PC. The PC
claims a ten-minute lease, heartbeats every twenty seconds, and sends versioned
source-bound results. Django validates field IDs, input hashes, observation shapes,
units/source references and uncertainty. Worker-provided confirmation/approval
flags are discarded; source findings remain `needs_review`, not accepted answers.

Each source and mapping checkpoint has a unique job/key binding. Identical result
delivery is idempotent; a changed result cannot overwrite an immutable checkpoint.
A stopped PC's expired lease can be reclaimed and completed checkpoints are reused.
Malformed model output creates an explicit failed job; the assigned Engineer can
use the existing retry action. Busy local inference requeues automatically. Network
failures back off up to sixty seconds, with no cloud fallback. A revoked account,
project assignment, credential or expired lease cannot continue downloading inputs
or returning results. An outdated PC/server release is rejected before inference.

After analysis and mapping, Django generates the existing draft PDF/DXF drawing
set. The Engineer corrects/accepts proposed records in the normal survey workspace;
ordinary technical review and authorised release remain mandatory. AI cannot
submit those human decisions. Clients only receive outputs permitted by the normal
released-output gate. Unsupported geometry and missing dimensions remain visible.

## Update and rollback

1. Record server and PC commits and preserve database/media/config/cache backups.
2. Stop only the dedicated outbound PC worker normally (Ctrl+C). Do not stop
   operational jobs through destructive database edits.
3. Install the reviewed release on both server and PC; preserve private config,
   original evidence and the local result cache. Install recorded requirements.
4. Review and run server migrations, Django deployment checks and focused bridge
   tests; collect static assets. Reload the web application using the established
   server release procedure only after approval.
5. Start the PC command above and verify one labelled test survey through its
   existing Engineer/QA/release workflow. Check the governance audit and logs.

If versions differ, keep jobs queued and align the releases; do not weaken the
compatibility check. Before rolling back, review migrations and restore only a
verified backup into an isolated restore first. Never overwrite a newer operational
database or remove uploaded originals to make a release appear healthy.

## Remaining server actions

The application connection and disposable HTTP integration can be tested locally.
Production DNS, TLS, firewall/Nginx installation, production secret/environment
values, server database backup/migrations, project-Admin credential provisioning,
private transfer to the PC and a real HTTPS smoke test require access to the chosen
VPS. Repository changes do not perform these operational actions automatically.
