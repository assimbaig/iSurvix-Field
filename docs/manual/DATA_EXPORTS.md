# My exports

- Open **My exports** from your account workspace. Choose a data section and optionally one permitted project, then **Prepare Excel**. Continue working while the independent export worker prepares the file.
- The table keeps each request, section, requested/prepared dates and times, status, row count and download action. Files use `YYYY_MM_DD_HHMMSS_section.xlsx`. Refreshing does not remove saved requests.
- Each standard workbook includes **Data**, **Columns** and **Export** sheets. Column-reference workbooks are available under **Columns, limits and retained history**. They describe the export structure; they are not import forms.
- Availability follows current account, company, project, assigned task and released-client access. An export belongs to its requester; nobody else can download it through this screen. Changed source records or access can make an old file unavailable. Request a fresh export rather than reusing a stale copy.
- Supported sections: projects, tasks, sites, clients, people, checklist answers, photo information, document information, review history, drawing/output register, DC power inventory, tower equipment inventory and electrical inventory. Only permitted sections appear.
- Engineers export their own assigned survey data and reported inventories, without internal review history. Clients receive shared current checklist/photo information and appropriately released output metadata, without internal review history, private documents or raw mutable inventory. Platform owners receive administrative projects, clients and people only.
- People and client exports reuse existing administrative screen scopes; they are not a company-wide database bypass. An administrator with no visible project members may receive an empty people workbook.
- Original photographs, sketches, PDF/DXF files and private AI payloads are not included. Inventory dimensions/readings/units are exported exactly as reported, without inferred measurements or approval claims. Passwords, credentials, provider configuration, support-repair data and arbitrary database tables are excluded.
- Limits: 50,000 rows, 30 MiB file size, 64 MiB source text, two active exports and 20 requests per rolling 24 hours. Narrow a request if it exceeds a limit. Formula-like text is made inert in Excel.
- Queued work remains saved when the worker is stopped. Failed preparation shows a useful error and supports up to three attempts. Retrying does not create another request or overwrite a completed file.
- Files expire after 48 hours. Download access stops at expiry; the running export worker removes only expired export artifacts. If the worker is offline, physical removal waits for its next run. Request/audit history stays recorded; original evidence is untouched.

## Windows worker

From the local project directory, start a second terminal with the existing environment:

```powershell
.local\venv\Scripts\python.exe backend\manage.py run_data_export_worker --settings=checklist.settings_local
```

For one controlled worker tick, append `--once`. This uses the configured local database; development verification must use isolated databases/media instead of operational surveys. The hosted runtime supervises an independent export process after public readiness. It does not require Ollama or email to be enabled.
