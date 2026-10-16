# Integration and deployment handoff

The latest frontend source was transferred from the published Site commit `2e3e77d6acf21724e30c72167a1138413462654b` on 16 October 2026. The Django source is the current locally available checklist-builder application, including migration 0015 and section-review tests. No production backend deployment was performed during transfer.

## Work remaining

1. Back up the existing Hostinger application, database and media.
2. Confirm the actual hosting plan, service configuration and database before changing deployment files.
3. Establish authenticated Django APIs for the frontend. Replace browser localStorage and the demonstration role switch with real sessions, project/site permissions and persistent data.
4. Serve the Team lead site register independently from the review wizard. Return read-only site records from Sites, even when a survey is Under Review.
5. Allow the review wizard only for a server-confirmed Under Review record. Partial approval leaves pending sections; verify correction and resubmission behavior against the backend's actual status machine.
6. Enforce assigned-site access and submission/approval locks on every write, upload and download endpoint. Frontend guards are not a security boundary.
7. Protect uploaded media behind authenticated routes. Keep private evidence out of publicly served static media directories.
8. Reconcile the new frontend workflow with legacy checklist routes and exports. Template-based section review is implemented separately from older fixed-form routes.
9. Test on staging: assignment, template publication, submission, section approval, full rejection, resubmission, view-only access, photos, reports, migrations and backup restoration.
10. Deploy only after the staged integration and legacy audit repairs are validated.

## Existing backend configuration

Environment variables are required; no live secrets are shipped. Review `.env.example`, settings and proxy behavior. The included nginx and service/script files are examples retained from the source and must be adapted to actual server paths. Do not run old deployment scripts blindly.

The default database configuration is SQLite. Production storage and concurrency choices require explicit deployment configuration. The frontend image limit and backend custom-evidence limits are separate implementations; do not assume the preview's browser storage supports production photo volumes.

## Scope of saved assets

The original Excel template, application logos, sample illustration assets, static source, migrations and tests are included. Production survey images, databases, local browser records, caches, virtual environments and logs are excluded. The Sites-specific hosting identity and source credentials are not transferred to this repository.

`CHECKLIST_BUILDER_HANDOFF.txt` records the earlier builder handoff; its validation counts refer to that earlier update. Refer to `TRANSFER_MANIFEST.json` for the current transferred files, and run the available tests against your deployment environment.
