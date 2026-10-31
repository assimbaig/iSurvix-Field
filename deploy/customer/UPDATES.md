# Controlled customer updates and recovery

This is an **unapproved review candidate**, first supported on Linux/amd64 with
local Docker/Compose. The website cannot invoke Docker. Package integrity,
functional checks, licence clearance and owner release approval are separate.
Use only an explicitly tested source-to-target commit pair from the trusted
catalog. Earlier servers without the signed Update Center bridge are unsupported
by this automatic procedure; do not improvise a live schema downgrade or bootstrap.

## Operator preparation

Keep these separate, nonsymlink paths on the server:

- Existing immutable source package and initialized source runtime.
- `/srv/isurvix-updates/catalog.json` and `receipts/`, managed by the operator.
- `/srv/isurvix-approved/<exact-target-SHA>/package/`, the transferred bundle.
- Optional `shared/release.json` alongside that package, if its independent
  SHA256 is specified in the catalog. The record must bind the same package,
  images, tested source path and edition.
- `/srv/isurvix-maintenance/`, private operator-owned journal storage outside
  all databases, runtimes, packages and mounted update inputs. Do not expose it
  to the application or publish its backups.
- A **new**, absent target runtime path. Partial attempts are retained; a later
  request uses another new target rather than overwriting an old directory.

Prepare new installations with the existing installer `prepare` option
`--update-directory /srv/isurvix-updates`. This persists read-only catalog and
receipt mounts during normal starts. Only the catalog file and receipt folder
are mounted; no host journal, credentials or Docker socket enters the website.
Receipt files contain version/digest/status data and HMAC signatures, not keys.
The external Django secret stays in the existing private secret file.

The root-managed catalog uses `isurvix-update-catalog-v1`, exact `release_id` and
`manifest_sha256`, explicit `supported_from` commit list, and permitted `editions`.
An optional `release_record_sha256` binds the shared release record. Transfer
artifacts/digests by an independently trusted channel; matching hashes alone do
not authenticate an attacker who can replace both catalog and package.

Agree a maintenance window and stop every external writer/worker accessing the
installation before confirming maintenance. This helper stops and checks the
managed Compose services. It cannot discover an unrelated process holding the
same files. Never run against operational data as a destructive rehearsal.

## Request and apply

The current platform owner creates an exact catalog request in Update Center,
confirming the maintenance plan. Customer administrators cannot make that request.
An operator then runs the **installed/reviewed host helper**, not an unverified
candidate helper:

```text
sudo python3 /INSTALLED/release/deploy/customer/updater.py apply --installed-package /INSTALLED --installed-runtime /srv/isurvix-current --update-directory /srv/isurvix-updates --packages-root /srv/isurvix-approved --target-runtime /srv/isurvix-candidate-NEW --journal-root /srv/isurvix-maintenance --request-id SAVED-REQUEST-UUID --acknowledge-draft --maintenance-confirmed
```

No password or secret value is passed on the command line. Docker must use an
explicitly local Linux Unix-socket context. Images load only from the verified
local archive; every run/up uses no-pull and no-build controls. No runtime pip,
model-cache collection, automatic model download or paid API is introduced.

The helper validates current request HMAC, nonce, short TTL, current source,
catalog and immutable package inventory. After loading images, it freshly
rechecks application authority. The existing application must acknowledge signed
`verified` and `applying` receipts before writers are stopped; withdrawal racing
with those acknowledgements aborts the operation.

It creates a verified quiesced SQLite/media snapshot, restores into the new
runtime, migrates only that copy, checks retained human/application rows and
evidence digests, starts only internal candidate web, then checks readiness and
baked release identity. It durably records `activation_started` **before** opening
the candidate proxy. Only a server-confirmed completion receipt yields
`completed`. The same completed request returns its durable result without
rerunning Docker or creating another target.

The operator must retain the returned target runtime/package and use those paths
for future normal starts and subsequent updates. No old package/data directory
is deleted. A source package may be a previous target under the approved package
root. A different request cannot bypass an unrecovered host transaction.

## Failure and interrupted-process recovery

A pre-activation migration, integrity or health failure preserves the candidate
and backup, restarts the old source, verifies its health and records failed then
rolled-back receipts. `apply` returns a JSON result; its exit code is zero only
for `completed`, otherwise two. Consult the safe error code and private journal.
Do not publish raw DBs, backups, account hashes or Docker logs.

A process interruption leaves a durable journal independent of the application
database. Repeating `apply` requires explicit recovery rather than silently
resuming destructive steps. For a transaction that never began activation:

```text
sudo python3 /INSTALLED/release/deploy/customer/updater.py recover --installed-package /INSTALLED --installed-runtime /srv/isurvix-current --update-directory /srv/isurvix-updates --packages-root /srv/isurvix-approved --target-runtime /srv/isurvix-candidate-NEW --journal-root /srv/isurvix-maintenance --request-id SAVED-REQUEST-UUID --acknowledge-draft --maintenance-confirmed
```

Recovery rechecks the original signed binding without granting a new update,
preserves the partial target, stops its managed services, restarts/health-checks
the source and reconciles the signed receipt chain before recording
`failed/interrupted` then `rolled_back`. Repeating a finished recovery is
idempotent. This version returns two for the rolled-back result, including an
intentional successful recovery; inspect JSON `status` rather than calling it
a completed upgrade.

`activation_started` or `activation_uncertain` requires operator data
reconciliation. **Do not restart the old proxy or discard either runtime**:
the target may already contain new writes. Automatic rollback is refused.
Preserve both data trees, backup, exact images and root journal; identify the
authoritative current dataset, make a new verified backup and obtain a reviewed
recovery plan. Receipt/authority conflicts before the first acknowledged applying
phase also require operator reconciliation rather than bypassing withdrawal.

## Verification limits

Ordinary tests use controlled Docker and real disposable SQLite/media; they are
not proof of an actual customer installation. Real Linux container upgrade,
restart and recovery CI is separate. A physical second authorized LAN browser,
customer DNS/firewall/certificate trust and licence/commercial approval remain
external acceptance gates. Windows-to-Linux backup byte preservation does not
prove every historical absolute output path is portable.

Only a disposable rehearsal may use
`ISURVIX_DISPOSABLE_REHEARSAL=yes` with
`ISURVIX_UPDATER_TEST_FAILPOINT=after-migrate` (caught pre-activation failure), or
`interrupt-after-migrate` (process interruption before candidate startup). These
are test-only environment guards, not normal update steps. Never enable them on
customer or operational data.
