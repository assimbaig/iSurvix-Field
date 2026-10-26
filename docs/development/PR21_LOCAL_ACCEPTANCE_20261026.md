# Review and accept the PR21 repairs on the actual PC

These repairs do not deploy the application, change your local records or install
another AI model. Keep a verified recovery checkpoint before changing your checkout.
Preserve `.local`, original media, the database, private worker configuration and
remote-worker cache. Do not extract a ZIP over operational data or copy a development
database over a VPS database.

## Get the reviewed branch

From the existing `F:\iSurvix\iSurvix-Field` checkout, inspect `git status --short`.
Commit or separately preserve your own unfinished changes first; do not force checkout.

```powershell
git fetch origin
git switch -c review/pr21-readiness-20261026 origin/fix/pr21-readiness-20261026
```

The PR targets `feat/secure-outbound-survey-workers`, which contains merged PR21.
The older `main` preview is not the repair base. Keep server and desktop worker on
the same reviewed release; compatibility checks must not be disabled.

## Record the actual native environment before investigating A12

Use the installed, verified local endpoint; 11435 is the documented working PC
example, not an instruction to reconfigure or restart your service.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Collect-iSurvixDiagnostics.ps1 -PhotoOllamaUrl http://127.0.0.1:11435 -TextOllamaUrl http://127.0.0.1:11435
```

The JSON stays private under `.local/diagnostics`. It records package/runtime
metadata and bounded crash-signal categories, without raw logs, credentials,
survey photos or uploads. Metadata alone does not resolve A12. Reproduce the
original native failure on permitted synthetic evidence and obtain a backtrace/
OS crash record before selecting a dependency or runtime repair. Do not silently
replace the installed model or infer native stability from mock tests.

## Run automated verification

```powershell
.local\venv\Scripts\python.exe -m pip check
.local\venv\Scripts\python.exe scripts\run_backend_tests.py --verbosity 1
cd frontend
npm ci
npm run install:browser
npm test
cd ..
```

The browser command installs test Chromium, not an AI model. An existing Edge can
be selected with `PLAYWRIGHT_BROWSER_CHANNEL=msedge`. The backend runner isolates
database/media/cache and blocks external/model calls. Windows must execute the
native launcher-alignment and real owned-process-tree tests that Linux skips.
Inspect every skip/failure; a green Linux run is not Windows acceptance.

## Check the worker connection without starting work

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Start-RemoteSurveyWorker.ps1 -PhotoOllamaUrl http://127.0.0.1:11435 -TextOllamaUrl http://127.0.0.1:11435 -CheckOnly
```

Use the existing project-Admin-issued `.local\private\remote-worker.json`; never
paste or commit its token. CheckOnly validates local installed-model metadata and
configuration shape, not real VPS connectivity, credential authorization, native
inference or throughput. Remove CheckOnly only for an authorised processing test.

## Target-machine acceptance still required

- Confirm Pause/Resume from two tabs: an old command cannot undo a newer one.
- Confirm a startup failure leaves no owned worker behind and preserves unrelated processes.
- Test real phone uploads, interrupted transfers and recovery with permitted test data.
- Measure a representative full-size site: elapsed AI time, unsupported/missed links,
  human correction effort, duplicate handling, retry and restart recovery.
- Review generated PDF/DXF geometry, units, missing dimensions and CAD imports.
- On VPS staging, verify TLS, private media denial, scoped HTTPS PC worker operation,
  concurrent users and a consistent database/media/job-state restore.

Automatic cloud fallback remains absent. An offline PC leaves jobs queued. Public
production release remains a separate action after the recorded acceptance gates.
