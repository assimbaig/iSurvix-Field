# iSurvix Field — Hostinger release readiness

Checked on 23 October 2026. **Not deployed; live acceptance remains pending.**

## Release candidate and topology

The operational survey application is in `assimbaig/iSurvix-Field`. This change
builds on `feat/secure-outbound-survey-workers` at
`b907601b8cac59cc111cb02f37489cc25073c866`. The `main` branch remains at
`2d9440cf22770521abc17a2b35c659c79aea0b36`; deploying `main` would omit the later
survey, evidence, review and outbound-worker work.

The proposed application address is `field.isurvix.com`, subject to confirming the
chosen VPS and existing DNS. Run the Django application behind Gunicorn and Nginx
with `checklist.settings`, `DEBUG=False` and private production environment values.
The company website is a separate deployment.

The existing outbound PC worker can process project-scoped AI survey jobs over
HTTPS while the VPS retains accounts, evidence, job state and outputs. The PC and
server must use compatible reviewed code. Follow [REMOTE_SURVEY_WORKER.md](REMOTE_SURVEY_WORKER.md)
for provisioning, private configuration transfer and recovery. Live model quality
and processing performance were not measured during this preparation.

## Deployment defect corrected

The production configuration omitted the role layout context, while templates
also hid primary navigation and site-photo upload links whenever local AI was
disabled. A production-mode request returned HTTP 200 with neither the role layout
nor primary navigation. Four of the six new regression checks failed before the fix.

Role context is now shared by local and hosted settings. Navigation uses the
authenticated role presentation; photo-library links no longer depend on a local
inference service. Existing project authorization, read-only states and upload
permissions still govern access. Local AI stays disabled in production.

## Verification completed

| Check | Result |
|---|---|
| Full isolated backend suite | 735 passed in 118.489 seconds; exit code 0 |
| Production-mode regression suite | 6 passed with `checklist.settings`, HTTPS requests and local AI disabled |
| Django production security checks | Passed with warnings treated as failures |
| Migration drift | No changes detected; no new migrations |
| Dependency consistency | `pip check`: no broken requirements |
| Retained preview checks | All four frontend check scripts passed |
| JavaScript syntax | Survey-processing and photo-field-workflow scripts passed |
| Whitespace | `git diff --check` passed |

The backend runner isolates databases, media and model caches, denies external
connections, and permits its own HTTP fixtures. Its full run recorded zero external
network attempts. Worker inference in deterministic tests is controlled; these
results do not prove the real PC model or a deployed HTTPS connection.

Validation used Python 3.12.14 with all declared requirements installed, including
Django 6.1.2, Pillow 10.4.0, PyMuPDF 2.0, ezdxf 1.4.5 and Gunicorn 21.2.0.

## Remaining operational work

1. Restore Hostinger server-control access and list the actual VPS, account,
   hostname, IP, operating system and running applications. No VPS, account or
   existing installation could be verified in this session.
2. Read the existing Nginx, service, database and media configuration. Establish a
   recoverable backup and check restoration before applying changes to an existing
   installation. Keep production and local Windows data separate.
3. Prepare an isolated staging installation of the reviewed candidate. Adapt
   `backend/checklist.service` to the actual service user and `backend` directory.
   Replace the historical company-domain/IP values and static path in
   `backend/nginx_config.conf` with the confirmed Field hostname and installation.
   These example files are not ready to install unchanged.
4. Create the private environment file with a new secret and confirmed allowed
   hosts. Review migrations using `backend/deploy.sh --check`, then follow its
   reviewed migration procedure. Bootstrap the initial administrator privately
   with `createsuperuser` before exposing an empty installation.
5. Configure Field DNS, HTTPS and the actual proxy. Keep `/media/` denied and use
   the authenticated evidence endpoints. Confirm storage persistence across code
   updates and configure database/media backups.
6. Complete desktop/mobile browser checks on staging: sign-in, role navigation,
   scoped assignment, photo upload, queued processing, engineer correction,
   review, release and protected PDF/DXF downloads. Provision the outbound worker
   for a test project and verify a real end-to-end HTTPS job using the PC model.
7. Release only after those checks pass, then add the Field login link to the
   company website using the confirmed application URL.

Browser verification could not run here: the required Chromium download returned
an invalid archive. No claim of browser acceptance is made. Hostinger server
controls were absent from the active tool set even though their configuration
entries existed. No server configuration, DNS, credentials, database, uploaded
evidence, corporate website or production service was changed.
