# Cloud staging: tasks07–09

Owner: Dot. Worktree `.local/b4`, branch `feat/cloud-staging-readiness-20261031`.
Parent: company onboardinge312197, draft PR27 (after draft PR26). These changes
reuse the existing Django database, media, permissions and outbound worker.

| ID | Expected behavior / original acceptance | Implementation location / owner | Verification method | Actual result | Status |
| --- | --- | --- | --- | --- | --- |
| 07.1 | Reproducible reviewed build/configuration, explicit private secrets and persistent paths. | deploy/ and settings_staging.py; deployment agent | Executed RED/GREEN config tests; clean Linux image build | In progress; Docker/WSL unavailable locally | In progress |
| 07.2 | Exact built release identity matches runtime configuration. | Baked RELEASE/image metadata and settings; deployment agent | Wrong/missing identity fails; correct identity/readiness matches running artifact | In progress | In progress |
| 07.3 | Clean staging install, restart and upgrade pass. | Deployment lifecycle scripts/CI; deployment agent | Actual fresh Linux install, restart, upgrade with retained database/media | No approved staging target/SSH credentials; no Docker/WSL locally | Blocked |
| 07.4 | Private media stays protected through the real proxy; authorized downloads still work. | Nginx template + existing Django file routes | Real Nginx anonymous/foreign/role/released-output requests | Official portable Windows Nginx signature and rendered configuration test passed; HTTP behavior pending | In progress |
| 07.5 | Website remains available when the PC worker is offline; no public Ollama/database. | Existing outbound worker; isolated deployment network | Queued jobs/manual QA plus topology and disconnection checks | In progress | In progress |
| 08.1 | Minimal public probes and current platform-owner-only aggregate diagnostics. | operations_service/views; operations agent | Unit/HTTP access, missing-schema/storage and offline-worker cases | In progress | In progress |
| 08.2 | Worker failure/restart retains checkpoints, uploads and accepted results. | Existing lease/client recovery; operations agent | Isolated actual HTTP transfer with controlled inference, interruption/retry and DB assertions | In progress; native model not exercised | In progress |
| 08.3 | Consistent backup/verified restore preserves SQLite and media bytes. | operations_backup and management commands; operations agent | Quiesced disposable backup/new-target restore, hashes, corruption rejection | In progress | In progress |
| 08.4 | Actual deployed recovery and off-device restore preserve uploads/results. | Approved staging infrastructure | Stop/restart deployed worker/web, external backup restore drill | Staging target, off-device store and deployment approval unavailable | Blocked |
| 08.5 | Existing backup/helper findings stay under their original approval status. | Lead and independent reviewer | Source comparison of held helpers and operations boundaries | New production recovery tool is separate; old private BR1 helper remains untouched | In progress |
| 09.1 | Phone/upload/concurrency/workflow tests pass on controlled real Django records. | Independent QA fixtures/browser | Real proxy HTTPS desktop/mobile viewport, upload/review/persistence/permission cases | In progress | In progress |
| 09.2 | Actual staging phone/device, concurrency and complete workflow acceptance. | Approved staging environment | Physical device, public-valid TLS/DNS, representative approved load and end-to-end worker | No staging access/device participation; native/cloud integration not verified | Blocked |
| 09.3 | Separate post-functional security review recorded; findings not fixed without approval. | Independent AppSec role | Adversarial proxy/files/health/backup/config tests after source freeze | Pending functional completion | Not started |
| 09.4 | Full repository regression and preservation checks on final source. | Lead | Full backend/frontend/system checks, source fingerprint and protected file/table digests | Pending implementation freeze | Not started |
| 09.5 | Review-only delivery; no proposal to launch publicly without evidence and exact approval. | Lead | Requirements ledger, blockers, draft PR and recovery bundle | No server mutation or launch authorized/performed | In progress |

## Environment evidence and boundaries

The main checkout remainsfd365f1 with two existing untracked audit reports.
Operational schema remains0053. Fresh checkpoint
`.local/backups/project-checkpoint-20261031-174052-platform-customer-admin`
contains verified SQLite/source/Git recovery proof;3,595 protected files matched
the trusted full recovery archive. The suffix comes from the existing helper;
it is not an operational deployment. No live migration or native AI call occurs.

Docker executable was not found; WSL explicitly reports it is not installed.
There is no configured SSH alias, staging environment credential or connected
Hostinger tool. The legacy example server/IP is not an approved staging target
and must not be treated as one. Complete independent code/tests/configuration,
then identify the exact infrastructure input and approval needed for live gates.

Portable Nginx1.31.8 is used only for disposable loopback proxy behavior. Its ZIP
was obtained from the official HTTPS download and verified with the official
published release signer's PGP key. The fixture uses a private self-signed
certificate; this proves neither public certificate trust nor Linux throughput.
See [official downloads](https://nginx.org/en/download.html),
[release signer keys](https://nginx.org/en/pgp_keys.html) and
[Windows limitations](https://nginx.org/en/docs/windows.html).

No model download, paid service, public Ollama listener, shared internet database,
production deployment or automatic merge is introduced. Previous A12/BR1/D1/D2/L1
and other held findings retain their approval status. New post-functional security
findings must be reported with severity/evidence/recommendation, then remain held
until owner approval. Installed Agency DevOps, Backend Architect and Reality
Checker/AppSec profiles are used with non-overlapping file ownership.
