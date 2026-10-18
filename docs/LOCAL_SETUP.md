# Windows local deployment and Ollama

This adds a local runtime to iSurvix Field. It does not alter Hostinger or import a production database.

## First launch

1. Install Python **3.12** for Windows, including the Python launcher (`py`). Ollama is the user's previously selected AI runtime.
2. Keep this checkout at `F:\iSurvix\iSurvix-Field`. Its environment, database, photos, secret and logs stay in the `.local` folder beneath it. Do not move or replace existing local data when updating code.
3. Open Ollama. If your model has not finished downloading, run `ollama pull qwen3.5:4b` in PowerShell. The launcher does not silently download models.
4. Double-click `Start-iSurvix.cmd`. First launch needs internet for Python packages. Subsequent launches reuse the environment unless requirements change. The launcher also starts the independent local photo worker.
5. On the first-run browser screen, choose your **own local admin username and password**. This setup closes after the first administrator is created. No default credentials are shipped.
6. Open **http://127.0.0.1:8000/local/**. The launcher prints this address and opens your browser. After setup, use your own administrator credentials to sign in.

The app keeps its Python environment, random Django secret, SQLite database, uploads, and logs under `.local/`. This directory is ignored by Git. Back it up if your local surveys matter. Do not delete it to update code. Local survey records survive stopping/restarting the app.

Stop the app with **Ctrl+C** in the launcher window. Launch the same `.cmd` again to restart. Ollama may continue running independently.

## Available screens

| Address | Purpose |
|---|---|
| `/local/` or `/governance/` | Role workspace: projects, invitations, tasks, review and client decisions |
| `/local/assistant/` | Local AI chat and actual saved survey links |
| `/login/` | Sign in using the account's invited role |
| `/devadmin/checklist-templates/` | Checklist builder and editable client branding |
| `/custom-checklist/<id>/` | Real versioned Django survey with saved answers/evidence |
| `/local/photos/<id>/` | Real survey photo evidence, durable processing jobs and reviewed draft answers |
| `/governance/audit/` | Project-scoped audit history; all projects for Super Admin |
| `/governance/maintenance/` | Super Admin access reset, preserving all survey data |
| `/local/checklist-review/<checklist_id>/` | Critical checklist AI review; Team Lead requests and optionally shares; authorized Client sees current shared reports only after Final |

To begin: create a project, create/copy and publish the FDED template, assign that template to the project, then create a survey/assignment through the existing app. Your local administrator can manage users and project roles. No live site information is copied automatically.

The separate sample frontend at `/app/` has been removed from local routing. Use the
real role workspace and assigned survey links. The former `/admin/` and `/devadmin/`
account editors are retired; users enter through invitations. See
[roles and invitations](ROLES_AND_INVITATIONS.md) for permissions, client decisions
and the non-destructive access reset. Legacy destructive tools are disabled.

## Local AI

The browser calls authenticated same-origin Django routes. Django checks the signed-in user's checklist access, then sends the question and explicitly selected checklist context to Ollama on **127.0.0.1:11434**. No OpenAI API or cloud key is used.

- Select one of your installed local models. Default: `qwen3.5:4b`.
- Select an accessible survey, or choose a general question with no survey shared.
- Ask for missing information, a summary, draft observations, review comments, or checklist explanations.
- Text chat context includes saved text answers, required-field gaps, status, approved-section IDs, and photo counts. Use the separate **Photo evidence** workspace to explicitly select and queue images for local vision analysis.
- The assistant has no tools and cannot edit answers or approve/reject records.
- Each question is independent; chat history is not stored.
- Local cloud aliases are excluded. HTTP endpoints outside loopback and redirects are rejected. No CORS changes or exposed Ollama port are required.
- Text chat and the independent photo worker share a database lease so one inference runs at a time. Overlapping chat requests get a retry message. The first model load may be slow. Each model request has a 180-second timeout.

This integration uses Ollama's [chat API](https://docs.ollama.com/api/chat) with `stream: false` and [installed-model list](https://docs.ollama.com/api/tags).

## Troubleshooting

**Python not found:** Install Python 3.12 including the launcher, reopen the terminal and run `py -3.12 --version`.

**Ollama unavailable:** Open Ollama or run `ollama serve`. Verify `Invoke-RestMethod http://127.0.0.1:11434/api/tags`. Click **Check connection** in the app.

**Model missing:** Run `ollama pull qwen3.5:4b`, wait until it completes, then check the connection again. You can select another installed local model from the app.

**Port 8000 busy:** In the repository folder run `powershell -NoProfile -ExecutionPolicy Bypass -File .\Start-iSurvix.ps1 -Port 8001`. The launcher only changes execution policy for that process; no machine-wide policy change is made.

**Another model:** Run the launcher with `-Model 'YOUR_INSTALLED_MODEL'`. Download it in Ollama separately if needed.

**Forgot local admin password:** In PowerShell from the repository:

```powershell
$env:DJANGO_SETTINGS_MODULE = 'checklist.settings_local'
Set-Location backend
& ..\.local\venv\Scripts\python.exe manage.py changepassword YOUR_USERNAME
```

## Build a custom checklist from sections or items

As Super Admin or your project's Admin, open **Checklist revisions**, then **Choose
sections & items**. Select the full FDED master or an accessible existing revision as
the source. Check whole sections or individual items; search keeps selections intact.
The live preview shows the selected sections and items in source order.

Enter a name and choose **Create custom draft**. Review the resulting draft in the
existing editor, then publish it and assign it to the project when ready. Selected
field IDs, required settings, table columns and source branding are retained. The
source template and existing survey snapshots/approvals remain unchanged. The catalog
uses its actual item count, including metadata and inventory fields.

## Photo evidence pilot

Open a real published-version survey from `/local/`, then choose **Photo evidence**.
Upload JPEG, PNG or WebP photos (5 MB each, 200 per project/site). The browser sends
at most 20 files per upload request. Originals and filenames are preserved, exact-byte
duplicates within the survey are identified, available GPS/time metadata is extracted,
and normalized previews are used for inference. Blur/low-detail flags are advisory.

Select photos and queue analysis. The worker checks installed local models and the
selected model's reported vision capability before sending native base64 image input
to loopback Ollama. No cloud fallback is enabled. The published field catalog is
processed in bounded batches without dropping fields. Results remain proposals:
inspect the source, uncertainty and missing information before accepting an answer.
Acceptance rechecks project access, approval locks, field validation and stale values;
it does not approve a section. Download the JSON evidence report for proposals,
source references, suspected anomalies and audit history. Existing checklist Excel
exports and review controls remain available through **Review checklist**.

`Start-iSurvix.cmd` starts the separate worker automatically and stops that worker when
the web server exits. For a separately managed worker, from this checkout run:

```powershell
$env:DJANGO_SETTINGS_MODULE = 'checklist.settings_local'
Set-Location backend
& ..\.local\venv\Scripts\python.exe manage.py photo_worker
```

Queued jobs survive restart. Interrupted running work resumes after the inference
lease expires (normally five minutes); completed photos are checkpointed. Failed jobs
can be retried without resetting their original answer baseline. Worker logs stay in
`.local`. Do not delete `.local` to recover a job.

For a synthetic local vision check that never reads project photos:

```powershell
& .\.local\venv\Scripts\python.exe scripts/check_local_vision.py
```

## Verification and limits

The Python/Django implementation is tested in the available Linux workspace. Tests use simulated Ollama replies to verify auth, CSRF, project scope, data isolation, context, cloud-model exclusion, disconnected/busy handling and localhost controls. No live connection to the user's Windows Ollama service can be made from that workspace.

Python 3.12.10 and the Windows local Django first launch were verified in this checkout.
The installed `qwen3.5:4b` reported vision capability and correctly described a synthetic
image through Ollama's native image API. A disposable synthetic end-to-end pilot also
passed upload, queue, real inference, explicit answer acceptance and report export.
Edge browser checks at 1440, 390 and 320 pixels used rendered synthetic content and
stubbed API responses; no real survey data was inserted for browser tests.
Real site-photo quality and throughput still
require a few user-selected photos before scaling. The Django development server binds
to loopback and local-only middleware rejects non-loopback clients. External fonts/styles
used by the existing app may still need internet; this is not a fully offline asset bundle.
