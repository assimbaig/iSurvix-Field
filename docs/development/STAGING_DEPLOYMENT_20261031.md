# Task07: reproducible staging deployment preparation

Status: application/configuration preparation, local focused checks and an
**actual disposable Linux Docker clean-install/upgrade/restart rehearsal passed**.
The target VPS is not deployed or accepted. Do not mark Task07 accepted for the
real staging target on the disposable rehearsal alone.
The owner must approve the exact target, artifact and configuration before any
staging installation. No production service, DNS, firewall, database, public Ollama
listener or external registry publication was changed by this work.

## Existing application and release unit

The existing Django application, SQLite database, authenticated evidence routes
and outbound authenticated PC worker are retained. There is one Gunicorn web
process with four request threads, SQLite IMMEDIATE transactions and a30s busy
timeout. This is a bounded initial staging configuration, not an assertion that
SQLite supports an unlimited number of writers.

`deploy/staging.py prepare-release` exports only a clean exact Git commit into a
new build directory. Ignored private data and `.git` are excluded. A generated
`RELEASE` file records the reviewed commit. The image contains that read-only file;
`settings_staging.py` refuses a mismatching configured release. It does not claim
that an arbitrary environment variable identifies deployed code.

Promote the **built immutable image**, not a fresh package installation on every
restart. Production Compose requires an inspected `registry/image@sha256:...`
reference, or an already imported verified local `sha256:...` image ID. No real
digest is invented in `.env.example`. An application image is not published by
this repository's verification job.

`requirements.staging.txt` pins the12 current direct application dependencies and
tests that they satisfy existing backend requirement ranges. It is explicitly
**not a resolved Linux/transitive lock**. The image build records actual Linux
`pip freeze --all` and OS package versions as `/app/DEPENDENCIES.lock` and
`/app/OS-PACKAGES.lock`. Review these and the base/application digest before
promotion. A bit-for-bit repeatable source build or a vulnerability-free package
set is not established by `pip check`. Existing dependency ranges were preserved.

## Files and ownership

- `backend/checklist/settings_staging.py`: explicit secure hosts/origins, private
  secret file, baked release identity and persistent paths. No import-time directory,
  key or database creation. A missing database fails unless a one-off initialization
  command explicitly sets `ISURVIX_INITIALIZE_DATABASE=yes`.
- `deploy/Dockerfile`, Dockerfile-specific ignore file and direct constraints:
  existing application image running as UID/GID10001. No source/data/model cache
  is fetched at web startup; native inference is disabled on the VPS.
- `deploy/compose.yaml`: persistent data mount; read-only, capability-dropped
  application/proxy containers; loopback-only host ports8080/8443; no exposed web,
  database or Ollama port. The web process remains attached only to the internal
  application network. The proxy additionally joins an ordinary ingress bridge
  so Docker can publish its loopback ports; this does not make them public.
  The PC continues outbound HTTPS through the approved proxy.
- `deploy/nginx.conf.template`: TLS1.2/1.3, HTTP redirect, request correlation,
  private access logs without URL/query/authorization values and a global deny
  for `/media` and `/media/`. Nginx mounts **static assets only**, never media or DB.
  Django authorizes project-scoped private files. Host including the public port
  is retained; forwarded scheme is overwritten from the actual proxy connection.
- `backend/deploy.sh`: reused read-only check and backup-flag-gated migrations.
  File-backed secrets work only with the staging settings module; no key value is
  read into shell output and no second plaintext key is required. Existing
  plaintext configuration and no-restart behavior remain supported.
- `deploy/healthcheck.py`: actual container-local readiness check with the correct
  Host and trusted proxy scheme. It never probes the PC or model. Proxy health is
  configuration validation; external TLS/HTTP smoke testing remains separate.

Nginx uses UID/GID101 and high internal ports8080/8443. Only `/tmp` is writable
for its PID/log/temp files. New private evidence defaults to modes0600/0700;
public collected static assets use0644/0755 so the read-only proxy can serve them.
File-source Compose secrets do not reliably remap ownership; the host file must
actually be readable by application UID10001, and the private TLS key by UID101.

## Disposable Linux verification

`.github/workflows/staging-verification.yml` prepares the exact clean commit and
invokes `deploy/verify_staging.sh` on an isolated Ubuntu24.04 Docker runner. It can
also be run manually on an isolated local Linux Docker daemon:

```bash
release="$(git rev-parse HEAD)"
python3.12 deploy/staging.py prepare-release --repository "$PWD" \
  --output /tmp/isurvix-reviewed-context --release-id "$release"
ISURVIX_DISPOSABLE_REHEARSAL=yes bash deploy/verify_staging.sh \
  /tmp/isurvix-new-disposable-runtime /tmp/isurvix-reviewed-context
```

Both targets must be new. Never reuse a customer data directory. The script
refuses remote Docker contexts and uses a unique Compose project. It resolves
official Python3.12/Nginx discovery tags to real immutable digests before testing,
builds the image, records package manifests, verifies non-root secret/key reads,
and exercises:

1. Fresh bootstrap with synthetic data, real schema0054→current upgrade preserving
   a synthetic Company and private sentinel.
2. Quiesced backup and new-target restore, with restored SQL/file checks.
3. Actual TLS readiness, static delivery and private-media denial.
4. Actual web/proxy restart with database/private-file hash preservation.

It does not claim a previous published cloud image exists. The upgrade is an
explicit old-schema migration rehearsal using the current reviewed image.
Fixtures, keys, backups and databases are not uploaded as CI artifacts. Only
verification/build logs, readiness responses and dependency manifests are retained.
No customer data, native inference or target VPS is involved.

Docker remains unavailable in the current Windows environment, but the hosted
Linux workflow has now actually executed successfully. The final successful run
is [41214056349](https://github.com/assimbaig/iSurvix-Field/actions/runs/41214056349),
at commit `7e88049e0640d15f353f1ab209d48687409ff091`. The two preceding failed
attempts and their functional repairs are recorded in the final addendum below.
The lead retains the downloaded verification artifact and resolved image IDs in
the cloud-staging acceptance evidence. A passing disposable hosted run does not
establish that an actual target-VPS installation or physical phone test passed.

## Prepared installation commands — require staging approval first

Prerequisites: approved isolated Linux Docker/Compose host, approved DNS/TLS files,
an approved immutable application image or verified image archive, reviewed source
commit and a private deployment environment. The current checkout supplies none
of those external approvals or credentials. Keep `deploy/.env.example` as a shape
reference and store real configuration outside the source checkout.

Example host preparation by the authorized operator:

```bash
sudo install -d -m 0700 -o 10001 -g 10001 /var/lib/isurvix-staging
sudo install -d -m 0700 -o 10001 -g 10001 /var/lib/isurvix-staging/media /var/lib/isurvix-staging/upload-tmp
sudo install -d -m 0755 -o 10001 -g 10001 /var/lib/isurvix-staging/static
sudo install -d -m 0700 /etc/isurvix-staging
# Place the existing/new approved secret privately; do not regenerate it on restart.
sudo chown 10001:10001 /etc/isurvix-staging/django-secret
sudo chmod 0400 /etc/isurvix-staging/django-secret
# TLS directory is mounted alone. Its protected host parent stays0700.
sudo chown -R 101:101 /etc/isurvix-staging/tls
sudo chmod 0755 /etc/isurvix-staging/tls
sudo chmod 0400 /etc/isurvix-staging/tls/privkey.pem
sudo chmod 0444 /etc/isurvix-staging/tls/fullchain.pem
```

Load only the trusted, reviewed configuration (it contains paths/image IDs, not
the secret value). Configure the exact approved hostname and release. Render a
**new** reviewed proxy configuration; the renderer refuses to overwrite files:

```bash
set -a
. /etc/isurvix-staging/staging.env
set +a
python3.12 deploy/staging.py render-nginx --host "$STAGING_HOST" --upstream web:8000 \
  --static-root /data/static --certificate /tls/fullchain.pem --key /tls/privkey.pem \
  --http-port 8080 --https-port 8443 --output "$ISURVIX_NGINX_CONFIG"
python3.12 deploy/staging.py validate --initialize-database
dc() { docker compose -f deploy/compose.yaml "$@"; }
# Only for an intentionally NEW staging database, never an upgrade or typoed path:
dc run --rm --no-deps -e ISURVIX_INITIALIZE_DATABASE=yes web python manage.py migrate --noinput
dc run --rm --no-deps web python manage.py collectstatic --noinput
dc run --rm --no-deps web python manage.py check --deploy --fail-level WARNING
python3.12 deploy/staging.py validate
dc up -d --wait --wait-timeout 180
```

No accounts, projects or engineering approvals are seeded by these commands.
Set up the approved test accounts through the existing controlled workflow.
Ports remain loopback-only. Phone/remote-worker reachability needs an explicitly
approved private route/VPN or separately approved gateway configuration; do not
make the website or Ollama public as a shortcut.

## Restart, upgrade and recovery

Restart preserves the configured database/media mount and private secret:

```bash
dc restart web proxy
dc up -d --wait --wait-timeout 180
```

For an upgrade, retain the current approved image/commit/configuration and secret.
Using the **current release configuration**, stop proxy/web writers and create
and verify a new private backup; mount a pre-created private backup directory
writable only by UID10001. The outbound PC cannot write the DB directly, and
unreturned PC results remain in the existing durable worker cache.

```bash
dc stop proxy web
dc run --rm --no-deps -v /var/backups/isurvix-staging:/backups web \
  python manage.py staging_backup --destination /backups/NEW_REVIEWED_BACKUP --quiesced
dc run --rm --no-deps -v /var/backups/isurvix-staging:/backups web \
  python manage.py staging_restore --backup /backups/NEW_REVIEWED_BACKUP --destination /backups/NEW_RESTORE_PROOF
```

After checking those receipts, explicitly switch the private configuration to the
approved new immutable image and matching commit. Validate it, then reuse the
existing backup-confirmation gate. Do not set the flag before backup verification:

```bash
python3.12 deploy/staging.py validate
dc run --rm --no-deps -e ISURVIX_BACKUP_VERIFIED=yes -e ISURVIX_PYTHON=/usr/local/bin/python \
  web bash /app/backend/deploy.sh --apply-reviewed-migrations
dc up -d --wait --wait-timeout 180
```

Do not automatically reverse migrations or overwrite current evidence to roll
back. Rehearse the old reviewed image against a **new restored data directory**;
check schema compatibility, original file hashes and human history before any
approved pointer/configuration switch. Migration0055 reversal drops onboarding
history, so a blind reverse migration is not a recovery procedure.

## Executed checks and limits

From `.local/b4`, existing Python3.12 environment:

```powershell
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' scripts/run_backend_tests.py core.test_staging_deployment --verbosity 1
& 'C:\Program Files\Git\bin\bash.exe' -n deploy/verify_staging.sh
& 'C:\Program Files\Git\bin\bash.exe' -n backend/deploy.sh
```

Final focused result: **20 passed in16.613s**, zero external attempts. Unit and
actual subprocess integration cover fail-closed host/origin/key/release/data
configuration, real Django deployment checks, existing DB-byte preservation,
clean Git source export, direct dependency compatibility and production policy
rendering. Actual Git Bash invocation of the existing deploy helper with a file
secret passed real pip/Django/migration-plan checks without a migration or key
disclosure. Shell syntax and Python compilation passed.

Meaningful RED receipts precede implementation. An initial fixture leaked an
SQLite handle on Windows and incorrectly expected Django check not to create an
absent SQLite file; the fixture now explicitly closes its connection and checks
existing DB bytes. A separate executed RED established missing-DB startup needed
an explicit bootstrap exception. YAML parsing found unquoted tmpfs comma options
became multiple mounts; a failing mount-count test preceded quoting both entries.
The existing helper's missing file-secret support and changed Nginx policy
acceptance were independently reproduced RED and repaired before final freeze.

Private receipts and13-file source freeze:
`.local/cloud-staging-20261031/deployment/`. Root owns the full repository gate,
actual portable-Nginx/HTTP QA evidence, independent security review and final
delivery ledger; those are not inferred from these focused results.

External blockers: Docker and WSL/Linux remain unavailable on this PC; no approved
staging target/credentials were supplied. The initial direct Windows Docker Hub
metadata lookup failed certificate-expiry validation; validation was not disabled
and no digest was invented. The hosted Linux build subsequently resolved actual
registry digests and built the image with normal verified connections. Review its
recorded artifacts before promotion, then perform the approved target-server
install/restart/upgrade/device tests. Existing A12/native inference acceptance and
prior approval-held security findings remain separate and unchanged.

## Final Linux test–fix–retest addendum

The following are actual disposable GitHub Actions attempts, not projected
results or mocked container launches. No customer VPS or operational records
were involved:

| Attempt | Executed result | Functional repair and regression |
| --- | --- | --- |
| [41213150689](https://github.com/assimbaig/iSurvix-Field/actions/runs/41213150689) | Exact source export, official image pulls and application image build succeeded. Host validation then failed with Permission denied while the runner tried to traverse application-owned0700 data. | Kept data/key ownership and private permissions. Both host validation phases now run only the read-only stdlib validator under explicit sudo, preserving an allowlist of eight configuration path/identity variables. System `/usr/bin/python3` avoids hosted-interpreter loader dependencies. Portable Bash invocation assertions were executed RED then GREEN; actual Linux rerun passed this boundary. |
| [41213609956](https://github.com/assimbaig/iSurvix-Field/actions/runs/41213609956) | Build, host validation,0054→0055 upgrade, backup/restore, static collection and Django deployment checks passed. Both containers were healthy, but the first HTTPS connection was refused. | A proxy attached only to an internal Docker network had no effective published host port. Kept the web service solely internal with no host ports; attached only the proxy to an additional ordinary ingress bridge. Loopback bindings, TLS verification, private-media denial and health checks remain intact. A network-graph regression failed before the change; CI now also asserts the actual published mapping before the unchanged real HTTPS probe. |
| [41214056349](https://github.com/assimbaig/iSurvix-Field/actions/runs/41214056349) | **Succeeded** on commit `7e88049e0640d15f353f1ab209d48687409ff091`: actual Linux image build and fresh install, synthetic0054→current upgrade with retained Company, quiesced backup/new-target restore, real verified TLS readiness, public-static delivery, direct-private-media denial and restart with retained database/original hashes. | This is the final executed disposable Linux deployment evidence. Actual registry/image identifiers and verification JSON are retained by the lead; no values were guessed and no certificate verification was disabled. |

The network repair follows the documented separation between an externally
connected frontend bridge and an internal backend network. See the primary
[Docker networking overview](https://docs.docker.com/engine/network/) and the
matching [Docker Engine internal-network port-publishing discussion](https://github.com/moby/moby/discussions/53256).

The final local deployment module contains20 passing unit/integration tests;
shell syntax checks also passed. The private deployment source-freeze manifest
was refreshed after the functional repairs. These fixes did not change the held
D1/D2/CS1/CS2 findings, dependency pins, production log retention, workflow
selection policy or engineering approval rules. No security finding was silently
remediated after review.

**Still blocked/unverified:** approved target-VPS installation and its operating
permissions, public DNS and publicly trusted TLS, physical phone acceptance,
actual target-connected Windows PC/vision processing, off-device recovery, and
resolution of the owner-held release/security findings. A12/native-model evidence
is not supplied by this deployment rehearsal. Do not propose public launch from
these results alone. The lead's final full-suite and independent review evidence
are recorded separately; they are not inferred from this CI success.
