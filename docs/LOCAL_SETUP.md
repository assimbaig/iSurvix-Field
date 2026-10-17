# Windows local deployment and Ollama

This adds a local runtime to iSurvix Field. It does not alter Hostinger or import a production database.

## First launch

1. Install Python **3.12** for Windows, including the Python launcher (`py`). Ollama is the user's previously selected AI runtime.
2. Clone or download this repository branch and extract it to a normal folder, for example `C:\Users\YOUR_NAME\iSurvix-Field-Local`.
3. Open Ollama. If your model has not finished downloading, run `ollama pull qwen3.5:4b` in PowerShell. The launcher does not silently download models.
4. Double-click `Start-iSurvix.cmd`. First launch needs internet for Python packages. Subsequent launches reuse the environment unless requirements change.
5. When prompted, create your **own local admin username and password**. No default credentials are shipped.
6. Open **http://127.0.0.1:8000/local/** and sign in. The launcher prints this address and opens your browser.

The app keeps its Python environment, random Django secret, SQLite database, uploads, and logs under `.local/`. This directory is ignored by Git. Back it up if your local surveys matter. Do not delete it to update code. Local survey records survive stopping/restarting the app.

Stop the app with **Ctrl+C** in the launcher window. Launch the same `.cmd` again to restart. Ollama may continue running independently.

## Available screens

| Address | Purpose |
|---|---|
| `/local/` | Local AI chat and actual saved survey links |
| `/devadmin/` | Existing app administration for projects and assignments |
| `/devadmin/checklist-templates/` | Checklist builder and editable client branding |
| `/custom-checklist/<id>/` | Real versioned Django survey with saved answers/evidence |
| `/app/` | Redesigned frontend preview using separate browser sample data |
| `/admin/` | Django account/database administration |

To begin: create a project, create/copy and publish the FDED template, assign that template to the project, then create a survey/assignment through the existing app. Your local administrator can manage users and project roles. No live site information is copied automatically.

The redesigned frontend is **not yet integrated** with the Django database. Its sample records are not real survey records. Use saved surveys linked from `/local/` for AI context and durable survey work. Older unversioned legacy routes retain their existing implementation and audit issues. This local setup is not a production-readiness certification.

## Local AI

The browser calls authenticated same-origin Django routes. Django checks the signed-in user's checklist access, then sends the question and explicitly selected checklist context to Ollama on **127.0.0.1:11434**. No OpenAI API or cloud key is used.

- Select one of your installed local models. Default: `qwen3.5:4b`.
- Select an accessible survey, or choose a general question with no survey shared.
- Ask for missing information, a summary, draft observations, review comments, or checklist explanations.
- Context includes saved text answers, required-field gaps, status, approved-section IDs, and photo counts. Actual image bytes are not sent; photo analysis is not implemented.
- The assistant has no tools and cannot edit answers or approve/reject records.
- Each question is independent; chat history is not stored.
- Local cloud aliases are excluded. HTTP endpoints outside loopback and redirects are rejected. No CORS changes or exposed Ollama port are required.
- One inference runs at a time; overlapping requests get a retry message. The first model load may be slow. The request timeout is 180 seconds.

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

## Verification and limits

The Python/Django implementation is tested in the available Linux workspace. Tests use simulated Ollama replies to verify auth, CSRF, project scope, data isolation, context, cloud-model exclusion, disconnected/busy handling and localhost controls. No live connection to the user's Windows Ollama service can be made from that workspace.

Windows PowerShell execution, browser layout and GPU/model performance require the first launch on the user's PC. The Django development server binds to loopback and a local-only middleware rejects non-loopback clients. It is intentionally not a LAN/public deployment. External fonts/styles used by the existing app may still need internet; this is not a fully offline asset bundle.
