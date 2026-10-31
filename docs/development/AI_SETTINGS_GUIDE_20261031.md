# AI Settings: company administrator and operator guide

## Administration

Open **AI Settings** in the existing top navigation. A company Admin opens only
their company's settings; the platform owner selects a company for configuration
administration. Operational reviewers do not receive configuration controls.

1. Keep configured routing disabled to retain existing local processing.
2. To enable policy-controlled processing, select the primary route, model,
   daily provider-attempt limit and timeout. Zero quota blocks configured work.
3. For an approved HTTPS connection or fallback, choose an operator-created
   alias, enter the provider's vision-model name and explicitly permit external
   evidence processing. This sends actual survey evidence, not only filenames.
4. Save. A confirmation follows the successful server write. If another person
   saved first, the conflict preserves your input; reload and reconcile it.

Saving does not start jobs, download models, regenerate completed results,
change published checklists, accept findings or approve engineering work.
The first durable pin controls the route. Existing native-model-pinned jobs stay
on their original local/PC worker after company routing is enabled; saved source
checkpoints are retained and are not analysed again. Company provider settings
apply to new jobs that have no native pin or saved provider policy. Jobs with a
saved provider policy keep that policy revision. API-only workers do not claim
native-pinned work, and enabling settings does not transfer an existing PC lease
to the server. No pin, policy or source result is deleted or rebound. Results
continue through existing human review.

## Operator connections and credentials

No alternative connection is enabled by default. Configure
`ISURVIX_AI_PROVIDER_REGISTRY` privately in the **worker/server** environment as
JSON alias metadata, for example:

```json
{"approved_vision":{"endpoint":"https://inference.example.org","credential_env":"ISURVIX_APPROVED_VISION_TOKEN"}}
```

The referenced token value is supplied separately using the operator's private
secret-management process. Never paste tokens into the company form, tracked
configuration, browser JavaScript, URLs, pull requests or support logs. Startup
rejects malformed registry metadata without echoing it. Registry entries are
**shared platform-operated connections**, not company-owned credential vaults.
Company consent, policies, quotas, source results and permissions remain separate.

The implemented alternative protocol is a bounded **HTTPS Ollama-compatible API**
(`/api/tags`, `/api/show`, `/api/chat`), with certificate verification, disabled
environment proxies, no credential redirects and bounded responses. It is not
universal vendor API compatibility. No OpenAI-specific adapter or key provisioning
was added, no paid request was made and no extra model was downloaded. A different
provider protocol requires its own reviewed adapter and live acceptance.

Provide the registry and credential environment to both the relevant Django
service and the policy-aware worker. Compose does not automatically inherit all
host variables: an operator must explicitly configure a private, untracked
environment override and worker egress, while preserving private DB/media mounts,
release identity, TLS and the website's internal-network boundary. Do not expose
Ollama or the database publicly. Actual VPS integration remains a separate gate.

## Workers

After reviewed source integration, dependency checks, backup and authorised
migration, existing local installations run the existing worker:

```powershell
Set-Location 'F:\iSurvix\iSurvix-Field'
& '.local\venv\Scripts\python.exe' backend\manage.py survey_processing_worker --settings=checklist.settings_local
```

On a properly configured staging host, the same application can run a worker
restricted to approved company HTTPS-primary policies:

```text
python backend/manage.py survey_processing_worker --configured-providers --settings=checklist.settings_staging
```

Add `--once` for one bounded worker iteration. Hosted local-only policies remain
queued; this option does not start a local model. This hosted worker mode
cannot provide API-to-local fallback through the PC: when local inference is
disabled, the attempt records `local_worker_required` without a loopback call.
The legacy outbound PC worker
cannot execute a newly configured company policy and explicitly defers it rather
than bypassing its quota, credentials or consent. Existing unconfigured outbound
jobs retain their original mechanism. Enabling a policy during an old PC lease
prevents further ungoverned task/result exchange; preserved jobs recover through
the appropriate policy-aware worker after lease recovery.

## Quotas, retries and recovery

The unit is a source-provider or checklist-mapping-provider **attempt**, not a
photo, token or invoice amount. Failed attempts and fallback count; capability
requests and a bounded truncation retry are part of that attempt. Each source
request has a bounded retry limit and durable lease. Quotas use the server's UTC
day. This is not a currency budget or commercial billing estimate.

Use the existing survey retry mechanism after correcting configuration or a
provider failure. Completed requests reuse integrity-checked results without a
second quota charge. Changed source inputs cannot overwrite a completed receipt;
use the retained new-submission-revision workflow. Stale leases cannot publish a
late result. Original uploads and human decisions remain authoritative.

Configured processing deliberately does not reuse visual inference across survey
revisions; within-revision checkpoints remain durable. Legacy local reuse remains
unchanged. This avoids treating a different provider policy as the same model.
These settings govern the integrated survey evidence/checklist processing worker.
The separate conversational assistant and legacy photo worker retain their
existing configuration; this feature does not claim to reroute those services.

## Verification limits

Controlled providers prove transport, structured validation, timeout and saved
workflow behavior. They do not prove native-model accuracy, a commercial
provider's availability, cost, real target VPS networking or off-device recovery.
See the requirements ledger and final evidence report for executed checks and
remaining approvals. Previous security holds remain unchanged.
