# iSurvix Field

Telecom site survey, checklist configuration, evidence and approval workflows.

This repository contains the latest published frontend preview and the available Django checklist application source. The frontend preview and Django backend are separate applications; their integration and Hostinger rollout remain pending.

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
The redesigned `/app/` interface remains a separate sample-data preview.
