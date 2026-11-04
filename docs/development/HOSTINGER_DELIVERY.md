# Guarded GitHub-to-Hostinger delivery

This extends the existing application and immutable release pipeline. It does
not migrate the local F: operational database, change engineering approvals,
deploy paid AI, expose Ollama, or make the old default main branch current.

## Exact approval and source policy

Target repository: assimbaig/iSurvix-Field. Active release branch:
feat/ai-settings-routing-20261031. Target protected beta: app.isurvix.com.

Developer flow is local tests -> PR -> owner review -> merge -> successful
exact-head application/staging/customer/shared checks -> authenticated host
delivery. A merge performed by assimbaig is explicit owner approval. Another
authorized merger requires the latest owner review on that exact head to remain
APPROVED. Fork, unmerged, wrong-branch, stale-branch, missing/revoked approval and
failed/pending checks are rejected independently by the server.

The delivery workflow runs only on a push to that maintained integration branch,
using its trusted pushed commit, never a pull-request execution ref. An
unprivileged first job calls GitHub's commit-associated PR API and then reads
canonical PR details. Exactly one closed, merged, same-repository PR must target
the integration branch and name that exact push as its merge commit. Direct
pushes, missing/duplicate associations, foreign PRs and wrong merge identities
fail before the protected environment or SSH key is requested. A successful
resolution only identifies the PR; it does not replace the server's independent
owner approval, current-branch, exact-head CI and artifact checks.

Keep the `hostinger-beta` environment restricted to the integration branch only.
No `refs/pull/*/merge` wildcard or unrestricted environment is needed. GitHub's
pull-request environment rules evaluate PR execution references rather than the
base branch; moving this workflow to the trusted branch push avoids granting
environment credentials to unmerged PR workflows. Remove any temporary exact
PR execution-ref rule after its one-off delivery has finished. Workflow reruns
must still pass the receiver's current-source and approval checks.

Use normal merge commits. The current branch head must equal the PR merge SHA,
and GitHub's actual PR-head tree must equal its actual merge tree. If a merge
adds base changes, rebase/update the PR and rerun CI. Deploy the already-tested
PR-head artifact and retain its head identity; never rebuild or relabel it as
the merge SHA. Squash/rebase flows that do not satisfy the same verified source
and upgrade-ancestry evidence are unsupported and stop safely.

The server rechecks every latest same-head required check using the existing
release_gate. Its shared producer and unique unexpired artifact must name that
head, expected repository and successful workflow. Outer bytes/digest, safe ZIP
members, existing package-consumer hashes, inner manifest/record/images and
real install/upgrade proof are verified. Candidate installer scripts are never
executed as root. A new branch/approval change during transfer or before public
opening blocks activation.

The package's supported_from must explicitly include the actual deployed
PR-head source. The public deployment metadata channel and CI upgrade rehearsal
are maintained separately by the release workflow. A stale baseline requires
rerunning the checks; it is not waived. Draft/license/security holds remain
recorded. This policy authorizes protected-beta application updates, not an
unrestricted production release or engineering approval.

## Dedicated SSH receiver and private credentials

Install the reviewed controller/helpers manually as root once. The deploy user
is not root, belongs to no Docker/sudo group and receives no interactive shell,
PTY, forwarding or arbitrary sudo operation. Its locked-password account needs
a usable /bin/sh for OpenSSH's fixed ForceCommand invocation. Keep its authorized
keys root-owned under /etc/ssh/authorized_keys/ifield-delivery, not in a writable
user-home .ssh directory. Use the key option `restrict` as another boundary.

Example root installation layout:

```text
/opt/isurvix-delivery/deploy/hostinger/controller.py
/opt/isurvix-delivery/deploy/release_gate.py
/opt/isurvix-delivery/deploy/customer/customer.py
/opt/isurvix-delivery/deploy/customer/upgrade_fixture.py
/opt/isurvix-delivery/backend/core/operations_backup.py
/etc/isurvix-delivery/policy.json
/var/lib/isurvix-delivery/            root0700
```

Install only those reviewed code files, root-owned with no group/world writes;
parent directories also root-owned and not writable by the deploy user. Do not
install a new host controller from each downloaded candidate automatically.
Keep the previous trusted installation and policy checkpoint before updates.
The immutable application and existing read-only runtime adapter stay separate.

```sh
install -d -m 0700 /etc/isurvix-delivery /var/lib/isurvix-delivery
install -d -m 0755 /opt/isurvix-delivery/deploy/hostinger /opt/isurvix-delivery/deploy/customer /opt/isurvix-delivery/backend/core
# Copy ONLY reviewed tracked files to the matching paths above; mode0644 root.
install -m 0600 deploy/hostinger/policy.example.json /etc/isurvix-delivery/policy.json
# Reconcile actual existing paths, then enable:true only after review/rehearsal.
```

Use the provided sshd and sudoers examples only after checking their exact local
Python/sudo paths. Validate new files with `sshd -t` and `visudo -cf FILE`, keep
the current authorized root session open, and test the new restricted account
before relying on it. Never replace unrelated SSH configuration or keys.

Receiver command, fixed in ForceCommand and narrow sudoers:

```text
/usr/bin/python3 -I /opt/isurvix-delivery/deploy/hostinger/controller.py
```

Remote command is `deliver` (or empty); arbitrary commands are never executed.
The only stdin shape is bounded to8192 bytes:

```json
{"pr":34,"github_token":"EPHEMERAL_WORKFLOW_TOKEN_SENT_IN_MEMORY_ONLY"}
```

Unknown keys, duplicate keys, caller URLs/paths/commands and missing/invalid
credentials are rejected. Use the current job's ephemeral repository token
with contents/actions/pull-requests read access, not a stored PAT. Send JSON
through stdin; never put its token in command arguments, files, shell tracing,
SSH output or workflow logs. A fresh unauthenticated request downloads the
signed artifact-storage redirect; GitHub Authorization is never forwarded.
Pin the independently confirmed SSH host key; never use StrictHostKeyChecking=no.
The dedicated SSH private key belongs only in the approved deployment secret
store and the owner's protected recovery custody; it is not a root key.

Owner-approved HD-S1 hardening: the server takes its nonblocking delivery lock
BEFORE waiting for any body byte. POSIX select/os.read enforces a fixed10-second
body deadline and8193-byte rejection boundary, handling partial reads/EOF without
unbounded buffering. Only one receiver can wait for a body; the dedicated SSH
Match block also limits MaxSessions to1 and ends with Match all. Validate the
actual target OpenSSH include context with sshd -t; text tests alone do not prove
that the host's include placement accepts all subsequent global directives.
PermitUserEnvironment is a GLOBAL directive on the target OpenSSH version;
keep it out of this Match block and verify `sshd -T` reports
`permituserenvironment no` before enabling the account. Validate supported
per-user forwarding restrictions with the actual parser as well.

## Maintenance, persistence and rollback

The root policy pins repository, branch, hostname, project, existing private
environment, two trusted Compose files, initial data and a private journal root.
No caller can select another server path or command. Existing nonroot/read-only
containers, dropped capabilities, no-new-privileges, private web8000, explicit
proxy443/loopback8080/8443 and private-file routes remain enforced by runtime
preflight. The TLS/login wrapper and root-owned Compose are retained; candidate
root scripts or Compose policies are not executed.

One exclusive host lock covers transfer and maintenance. Durable checkpoints
and immutable attempt directories retain failures, old artifacts, previous
environments, verified backups and failed data for diagnosis. No token is
persisted. Before stopping the site, the package must prove upgrade support for
the current source; Docker images are loaded from its checked archive only.
No pulls/builds or dependency/model downloads occur during installation.

Sequence:

1. Verify authority/artifact; preflight source runtime, image identities and
   actual health. Reserve disk for verified backup/new target/recovery.
2. Stop proxy and web; confirm all known writers are stopped, not restarting or
   paused. The outbound PC worker cannot write directly to server files/DB.
3. Run the existing operations_backup create/validate functions. Retain complete
   original media plus committed SQLite content, including WAL records.
4. Restore that verified backup into a NEW private candidate data target.
   Original /var/lib/isurvix-staging remains intact. Run migrations only against
   that copy, with no initialization flag. Generate static assets and run deploy
   checks. Existing read-only retained-row comparisons and evidence hashes must
   still agree; do not rewrite human decisions or discard originals.
5. Start the new web and a loopback-only proxy using the trusted original base.
   Verify actual image IDs, baked release, private port bindings and trusted TLS
   readiness. Recheck current owner/branch/CI authority before exposure.
6. Persist public-opening intent, then expose the approved proxy443 override.
   Confirm trusted public HTTPS and exact release before declaring success.

Before public-opening intent, failures quiesce the candidate and restore the
verified backup into ANOTHER NEW data target with the previous images/config.
Never overwrite the source or failed candidate database/evidence and never run
a blind reverse migration. An interrupted pre-opening attempt recovers first
and returns `recovered`; the delivery workflow must retry after that bounded
recovery rather than interpret it as a completed update.

After public-opening intent, traffic may have accepted new answers. A failure or
interruption freezes service and returns operator_recovery_required, retaining
the new DB/media. It MUST NOT automatically rewind human records to the earlier
backup. The owner must inspect/reconcile those retained records before an exact
operator-approved recovery. This is a deliberate data-preservation stop, not a
zero-downtime promise.

Owner-approved HD-R2 handling includes actual sqlite3.DatabaseError failures,
not merely ValueError. Pre-opening corruption triggers the same verified
new-target rollback; a database error after public-opening or while forming a
completed receipt freezes the target and retains its bytes/new human rows.
An unreadable frozen database reports no invented schema value. Further delivery
requests reject the operator-recovery hold without rewinding accepted records.

The active data pointer may move to a new private delivery data/recovered
directory. It retains all verified records/originals; the original data path and
failed copies remain untouched. Backup old directories only after quiescing
their writers; do not delete or truncate journals, keys or retained data to free
space. Establish owner-approved retention/off-server encrypted backups before
substantial use. Disk and the existing SQLite/concurrency limits still apply.

## Replays, receipts and restart recovery

A completed replay must match PR/head/merge/manifest/artifact/image bindings,
the actual active environment, Docker image identities, baked release and live
HTTPS. It does not rerun migration or duplicate accepted outputs. A stale or
forged completed journal is not proof of a running release.

Exit0 is reserved for completed/already_running. Recovery/rollback/manual hold
or errors exit2; failed checks must fail the GitHub delivery job. A success
receipt has format isurvix-hostinger-receipt-v1 and includes PR, source_release,
actual release/head, merge_sha, manifest/artifact digests and ID, actual image
identities and core_schema read directly from active SQLite. Replays retain the
original source_release so a retried metadata write binds the same transition.
No private paths, credentials, source evidence or human data are in the public
receipt. The public channel publisher independently validates this receipt and
its previous baseline before updating release metadata.

Do not change policy paths, images or active environment by editing a completed
journal. An operator_recovery_required state blocks further automatic work.
Preserve its backup/target and inspect the private journal plus actual Docker
state. A pre-opening interruption can be recovered by a fresh authorized
delivery request; it never trusts a cached passing stdout message.

## Checks and honest limits

Ordinary isolated tests:

```powershell
.local\venv\Scripts\python.exe scripts\run_backend_tests.py core.test_hostinger_delivery --noinput
```

They exercise controlled GitHub/command fixtures and REAL SQLite/media
backup/restore/retained-decision comparisons, malicious paths/archives/digests,
fork/approval/stale branch/check failures, duplicate delivery, revoked credential,
concurrent locks, interrupted phases and preservation of newly accepted rows
after public opening. They do not claim actual Docker/SSH/VPS deployment.

Before enabling automation, run a genuinely disposable Linux Docker rehearsal
with the trusted Host adapter, actual prebuilt source/target image identities,
saved synthetic data, failure injection and retained evidence checks. Then use
the exact reviewed/merged PR and completed workflow gates for the real beta.
Check the restricted SSH negative cases, live port policy, public HTTPS/login,
company/role isolation and actual update/rollback receipts independently.
Application release identity remains its prebuilt PR-head SHA. Root-owned host
controller changes, incompatible schema/retention changes, real native AI and
public production approval require their own reviewed work; no automatic waiver.

### Actual Docker controller rehearsal

`deploy/hostinger/verify_delivery.py` is CI-only and refuses non-root/non-Linux,
missing explicit rehearsal/CI flags, an existing work path, paths outside
RUNNER_TEMP and occupied443/127.0.0.1:8080/8443 before touching any service.
It must run after the existing `verify_updates.sh exercise` has produced its
real upgrade/recovery proof and left the prebuilt source/target packages/images.

```sh
sudo env ISURVIX_DISPOSABLE_REHEARSAL=yes GITHUB_ACTIONS=true \
  RUNNER_TEMP="$RUNNER_TEMP" /usr/bin/python3 deploy/hostinger/verify_delivery.py \
  --work "$RUNNER_TEMP/isurvix-customer/hostinger-rehearsal" \
  --source-package "$RUNNER_TEMP/isurvix-customer/update-rehearsal/source-package" \
  --target-package "$RUNNER_TEMP/isurvix-customer/package" \
  --source-release EXACT_BASELINE_SHA --target-release EXACT_TESTED_PR_HEAD
```

This calls the REAL Engine and Docker Host, with fresh synthetic Django data
seeded by the existing guarded upgrade fixture. It exercises an actual migration
failure/verified new-target recovery, actual successful migration/activation,
private and public TLS, retained original hashes/decisions, running replay and
authenticated Engineer original access plus Owner/anonymous denial. It neither
builds nor pulls application images. No native model or paid service is called.

Only that disposable runner gets a temporary app.isurvix.com loopback hosts
entry; it is restored in finally. A synthetic certificate is trusted through
SSL_CERT_FILE for this process only; the system CA store is not changed. The
unique Compose project is removed in finally. Failures and cleanup failures
return nonzero. A rejected guard never writes/chmods an existing work directory.

Export only `hostinger-rehearsal/verification.json`, which contains nonsecret
verification results. Never upload the sibling fixture password, keys, env,
databases, media, journal or backups. The public proof explicitly distinguishes
these real Docker checks from separately controlled GitHub-authority tests.
Until CI runs it successfully, the native Host rehearsal remains unverified;
ordinary passing fixtures are not a claim that this script executed on Linux.
