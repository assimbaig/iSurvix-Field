# iSurvix Field

The opt-in saved-survey **AI Checklist & Drawings** workflow is documented in the
[team guide](docs/manual/AI_SURVEY_TEAM_GUIDE.md), with
[implementation and worker instructions](docs/development/AI_SURVEY_DRAWING_PIPELINE.md)
and [synthetic PDF/DXF samples](samples/drawings/README.md).

Telecom survey and inspection, construction inspection pilot controls, checklist configuration, evidence and governed review.

The current local application runs through `Start-iSurvix.ps1` at `http://127.0.0.1:8000/local/`. It uses Django, SQLite and a verified local Ollama vision model. Its code, database, originals and private recovery checkpoints stay under `F:\iSurvix\iSurvix-Field`. The static frontend preview below is retained historical source; it is not the current operational application.

## Applied product roadmap

The [roadmap application register](docs/roadmap/APPLICATION_PLAN.md) maps the18October2026 PDF to this checkout. Delivered local foundations include five primary navigation areas, industry/workflow selection, optional independent Engineer/Team Lead/Project Manager review, frozen submissions and reports, criteria qualification, blocking findings and independent retest, named Client correction/release, and expiring project access. Existing activities retain their approval flow and400-photo metadata pipeline. Later design/commercial/construction execution, assets, services and finance modules remain planned; local tests do not establish production or field acceptance.

End-user guidance is in [the Software Manual](docs/manual/iSurvix_Field_Software_Manual.pdf). Internal implementation evidence remains separate in the [Development Guide](docs/development/iSurvix_Field_Development_Guide.pdf) and [local handoff](docs/LOCAL_CODEX_HANDOFF.md).

## Contents

| Directory | Contents |
|---|---|
| `frontend/dist/` | Latest editable static frontend, CSS, JavaScript, branding and image assets |
| `frontend/check-site-routing.cjs` | Functional checks for the current assembled frontend |
| `backend/` | Django application, original Excel checklist, templates, migrations and tests |
| `docs/` | Handoff and integration notes |

## Latest frontend behavior

- Team lead Sites opens a status summary and site register.
- A Site ID in Sites opens the read-only site wizard.
- Review lists only sites Under Review; a Site ID opens the review wizard.
- Wizard progress is saved per Site ID and mode, with site-specific URLs.
- Full approval, multi-section partial approval and full rejection.
- Separate Engineer workspace: assigned sites, Pending and Complete lists, guided checklist, photos and submission.
- Latest supplied iSurvix logo.
- Admin checklist builder with configurable sections, fields, client logos and published revisions.

## Run the frontend

```bash
python -m http.server 8000 --directory frontend/dist
```

Open http://localhost:8000. No build or package installation is required.

```bash
cd frontend
node check-site-routing.cjs
```

The preview uses sample data and browser localStorage. Its role selector is a demonstration feature, not real authentication. Local records and uploaded photographs are not shared between devices and are not included in this repository. Browser visual verification remains pending.

For a static preview, upload the contents of `frontend/dist/` to a separate web directory. Do not overwrite a running Django installation with these static files.

The additional component checks `check-preview.cjs`, `check-workspace.cjs`, and `check-engineer.cjs` are also retained. They exercise earlier component layers; `check-site-routing.cjs` loads the complete current frontend stack.

## Django source

The backend includes the custom checklist builder and section-review changes through migration `0015_section_reviews`. Existing client templates and published survey revisions remain separate from the browser-only preview data.

Use Python 3.12+ and a virtual environment. Install `backend/requirements.txt`. Set `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, and `DEBUG` in the process environment. `.env.example` is a reference; Django does not automatically load it.

For local development, set `DEBUG=True` and a non-production secret key in your local environment, then run from `backend/`:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Backend checks, after environment setup:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test core.test_template_builder
```

Read `docs/INTEGRATION_AND_DEPLOYMENT.md` before staging or production deployment. Legacy deployment guides and scripts in `backend/` are retained source references and may assume old server paths; review them before use.

## Current status

The updated frontend is published at https://isurvix-survey-redesign.mirza-assim.chatgpt.site/ . Transferring code here does not deploy to Hostinger or connect the preview to Django.

The original application audit identified legacy permission and data-integrity problems. The checklist-builder update is not a blanket remediation of those older routes. Enforce authentication, project/site scope, view-only access and approval locks on the server, and verify those legacy paths before production use.

No production database, credentials, uploaded survey photographs, logs, or installed dependencies are included.

## Run on your Windows PC with Ollama

Open `Start-iSurvix.cmd`. The launcher creates an isolated Python environment, installs
dependencies, initializes a separate local database and asks you to create an admin account.
It starts the app at `http://127.0.0.1:8000/local/` and checks your local Ollama model.
Default: `qwen3.5:4b`. See [Windows and local AI setup](docs/LOCAL_SETUP.md).

The new Local workspace provides real saved survey links and a local AI assistant.
The `/local/` entry now opens an invitation-based role workspace. The separate `/app/`
sample website is retired. See [roles and invitations](docs/ROLES_AND_INVITATIONS.md).

Real surveys now also link to an authenticated **Photo evidence** workspace with
batched uploads, a durable local vision queue, evidence references and explicit draft
acceptance. Existing approval locks and checklist exports remain in place. Keep this
checkout and its `.local/` data under `F:\iSurvix\iSurvix-Field`.

Company access now supports multiple explicitly granted projects per Admin and optional
additional projects for Team Leads, Engineers and Clients. Non-Admin workspaces default
to the primary project. Team Leads can request an internal critical AI checklist review
and explicitly choose whether to share a current report with Clients; Client access
still requires Final status. Existing approval signatures and data remain protected.

Documentation is split into the [Software Manual](docs/manual/iSurvix_Field_Software_Manual.pdf)
and internal [Development Guide](docs/development/iSurvix_Field_Development_Guide.pdf).
See [documentation distribution](docs/README.md): final user releases include only the
Software Manual. `scripts/package_user_manual.py` creates the allowlisted user package.

The field workflow now opens Engineers directly into grouped Civil/Electrical/Tower
uploads, editable site preloads, AI photo-location proposals, evidence coverage and
manual corrections. Team Leads can preview and commit bulk CSV site assignments.
Confirmed photo links appear in checklist and Excel exports; originals and approval
locks remain. Engineers can request their own private AI review; only Team Lead
controls Client sharing. See [field workflow plan](docs/FIELD_PHOTO_WORKFLOW_PLAN.md).
