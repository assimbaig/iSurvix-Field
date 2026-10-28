# Company-bound worker credentials

Task04, 28 October 2026. The worker's existing project scope is now intersected
with its immutable **issuing employer Company**, the current issuer's persisted
company/role/status and each current project's company and named administrator.
ClientOrganization is not this employer boundary. No new worker API or role was
introduced.

## Reproduced defect and correction

The old credential had no issuance-company record. A retained token could follow
its issuer and project from CompanyA into CompanyB and claim a new CompanyB job.
An isolated HTTP test reproduced200/job allocation instead of403. The fix records
`RemoteWorkerCredential.issuing_company`, checks it when authenticating and when
using a retained service object, and scopes every job/lease/input/result operation
through those current checks. Original evidence and other projects' jobs remain
unchanged. The new company pin cannot be changed through model save.

Ordinary file and processing routes already constrain parent checklist/project
and nested photo/document/source/output IDs. New real HTTP contracts prove both
directions of company denial and permitted own-company byte delivery, including
legacy attachments, logos, PNG originals/previews, document and source previews,
PDF/DXF/ZIP paths, processing progress and queued job actions. These file fixtures
test delivery and scope, not engineering accuracy or export readability.

## Migration0054 and existing installations

`0054_remote_worker_company_pin` adds a nullable protected Company reference.
No credential, lease, token hash, queued job, immutable result or original is
deleted. New provisioning requires a currently scoped Admin with a known Company
and records that Company in the existing issuance audit event.

Backfill accepts only explicit company IDs in the credential's provisioning
audit, with exact project coverage and coherent current issuer/project ownership.
Missing, contradictory, boolean or partial proofs are not guessed from current
ownership. Older releases did not record that company fact, so their unproven
credentials remain NULL and authentication fails closed. Their owning scoped
Admin must issue a fresh credential after reviewing the target company/project
scope. Jobs/checkpoints remain queued or recoverable under their normal lease
expiry/retry rules; no engineering answer or approval is changed.

The current local baseline has zero worker credentials. This compatibility note
also applies to other target databases; a zero local count does not establish
that a VPS has none. No operational migration or token reissue was executed by
this development task.

During an authorized rollout, back up first, deploy the matching reviewed server
and PC code, apply the migration to the intended database, and review unbound
credentials. Use the existing `provision_survey_worker` management command as the
authorized owning Admin. Its `--help` lists project, server URL and exclusive
private-output arguments. It writes the secret once to a private file and does
not print it. Preserve old configuration for recovery, securely transfer the new
file, then test an allowed job and a foreign-company denial before resuming work.
No credentials are exposed through a new dashboard or unscoped list endpoint.

## Verification

- Unit and HTTP tests execute the original cross-company claim RED then GREEN.
- Real MigrationExecutor tests cover explicit proof, missing/contradictory proof,
  missing project coverage and invalid boolean company IDs.
- An independent in-memory nondefault database migration initially changed an
  unrelated default fixture. A meaningful RED test demonstrated it; every migration
  queryset now uses `schema_editor.connection.alias`. The same test proves default
  rows stay unchanged and the scratch tenant alone receives its valid backfill.
- The runtime model's immutability check also uses its save/database alias; an
  actual nondefault save RED/GREEN test proves the company pin cannot be changed.
- Existing remote-worker tests retain expiry/revocation, input transfer,
  idempotent results, compatibility checks and restart/retry behavior.
- Real own-company normalized image bytes are delivered to an allowed worker;
  a foreign token with a known valid lease cannot download or submit results.

Ordinary tests use disposable databases/media with external/model requests
blocked. These checks do not establish native Ollama readiness, production Nginx
configuration or a deployed VPS connection. Existing A12 and separately held
security findings are not repaired by this change.
