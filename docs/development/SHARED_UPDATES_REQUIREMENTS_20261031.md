# Shared release and customer updates: tasks19-21

Owner authorised these tasks on31 October2026 during the approved CP1/CP2
repair. Continue existing application and package work; do not deploy, merge or
publish an owner-approved release automatically. The existing security and
licence holds remain explicit.

| ID | Expected behavior | Implementation location | Verification method | Actual result | Status |
| --- | --- | --- | --- | --- | --- |
|19.1|One exact source and immutable image identity for cloud/customer editions|Existing deployment and candidate bundle, shared release gate|Compare release/image/manifest hashes across edition records|Inspection underway|In progress|
|19.2|Failed, missing or stale checks block candidate publication|Shared CI gate|Negative and positive unit/HTTP integration plus actual CI|Pending|Not started|
|19.3|Traceable provenance and package integrity; trusted authenticity distinguished|Release metadata and download/verify guide|Exact SHA/run/artifact binding and tamper tests|Pending|Not started|
|20.1|Actual authenticated Update Center in existing application|Existing Django routes/models/templates|Saved-data role/CSRF/browser checks|Inspection underway|In progress|
|20.2|Verify package, support compatibility and require explicit authorised maintenance|Existing package validator and independent local operator|Wrong package/version/permissions/incomplete transfer tests|Pending|Not started|
|20.3|Backup verified data before update; interrupted/invalid work fails safely|Existing backup/restore and privileged local update operation|Failpoints/restart/concurrency/idempotence tests|Pending|Not started|
|20.4|Website never receives Docker socket or silently runs privileged commands|Deployment boundary|Configuration and security review|Pending|Not started|
|21.1|Supported version pairs are explicit; unsupported upgrades rejected|Release compatibility record and migration check|Clean/install upgrade matrix with actual migrations|Pending|Not started|
|21.2|Failed upgrade recovers previous exact source/data/outputs|New-target backup/restore workflow|Actual disposable Linux drill plus retained hash comparisons|Pending|Not started|
|21.3|Original evidence, saved reviews, source revisions and user decisions survive|Existing operational records|Isolated fixture before/after hash and logical-record checks|Pending|Not started|
|QA|Executed TDD, unit/integration, independent workflow QA and separate AppSec|Agency developers/reviewers|Frozen-source regression and actual installation rehearsal|Pending|Not started|
|Target|Actual customer machine and owner exact-release acceptance|Owner/operator|Authorised target run and release approval|No target/access or exact release approval supplied|Blocked|

First package target remains Linux/amd64 Docker/Compose. Offline application
updates require pre-transferred trusted package/images and preinstalled platform
prerequisites. No model downloads, public Ollama, paid service, production update,
automatic engineering approval or deletion of historical records is authorised.
A checks-passed candidate is not a licence grant or production release approval.
