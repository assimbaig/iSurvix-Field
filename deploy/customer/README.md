# Customer server candidate package

This installs the **existing iSurvix Field application**, using its shared Django
settings, authentication, project permissions, private-media routes, SQLite/media
storage, worker protocol and approval workflow. It is a draft review candidate,
not an owner-approved customer release. Recorded security and licensing holds
remain. Neither the helper nor `--acknowledge-draft` grants deployment approval.

The first supported candidate target is **Linux, x86-64, local Docker Engine with
Compose v2 and Python 3**. A rootless or rootful local Unix-socket Docker context
is required. Remote Docker contexts, Windows-native server execution and ARM
images are not claimed as verified. Docker/OS installation and prerequisites
must be supplied separately through an approved connected preparation process or
installation media; the runtime helper does not install them.

## Build a transferable candidate

The build operator prepares the shared exact tracked source and builds the
application using `deploy/Dockerfile` and the existing pinned-image process. The
application image must contain `/app/RELEASE` equal to the exact source commit.
Use already-inspected immutable application and official proxy image identities:

```text
python scripts/build_customer_package.py --repository /reviewed/source --release-id EXACT_40_CHARACTER_COMMIT --app-image sha256:APP_IMAGE_ID --nginx-image sha256:NGINX_IMAGE_ID --output /private/output/NEW_candidate
```

The source checkout must be clean. The helper does **not** build or pull an image.
It inspects existing Linux/amd64 images, verifies the baked release, exports only
tracked source, saves both images into `images/server-images.tar`, records actual
image dependency/OS inventories and available Python license metadata, then
writes an exact SHA256 file inventory. Runtime data, uploaded originals, `.local`,
private folders, database files and non-example `.env` files are refused if found
in the tracked export. No operator TLS keys, application secret, API credentials,
separately collected Ollama models or downloaded model caches are added by the
builder. The saved application image still contains weights shipped inside its
dependencies, including RapidOCR's three bundled ONNX files and OCR resources in
retained MuPDF dependencies. Those files require dependency/license inventory and
review; this is not a model-free image or licensing clearance. No runtime model
download is performed.

Provided images must also be reviewed: a claimed baked release and checksum do
not prove a malicious image contains no extra files. Upstream license files
remain inside their images; metadata with missing/uncertain licensing is recorded
as `NOASSERTION`, never legal clearance. In particular, the current PyMuPDF
AGPL/commercial licensing route requires an explicit owner decision. See
[PyMuPDF licensing](https://pymupdf.io/licensing). Do not redistribute or release
this candidate until the owner has reviewed the actual dependency inventory,
security holds and commercial/license policy.

Transfer the entire candidate directory over a trusted medium. Record its
`manifest.json` SHA256 through an independent trusted channel. Hashes detect
corruption; an attacker replacing both manifest and contents is a separate trust
boundary. No signature or owner approval is fabricated by this tool.

## Prepare a fresh authorized test server

All examples below are operator commands, not actions already performed on a
customer machine. Replace example paths/hostname/LAN IP with the approved target.
Use a new runtime outside the candidate. The package refuses an existing runtime
or existing/partial database rather than overwriting customer records.

1. Supply an explicit DNS hostname resolving to the server's **RFC1918 IPv4**
   address from authorized client devices. Wildcard, public, loopback, link-local
   and reserved listener addresses are refused by the helper. Restrict the host
   firewall to authorized LAN clients; no automatic firewall changes are made.
2. Supply a trusted TLS certificate and private key as `fullchain.pem` and
   `privkey.pem` in an external private directory. Establish browser trust through
   the owner's approved certificate process. The tool never obtains certificates,
   changes a system trust store or disables TLS verification.
3. Supply a separate strong Django secret file with at least 50 characters.
   Never place secrets inside the candidate, its source, media or static tree.
4. On the Linux host, the Django secret must be readable by container UID10001
   (normally owner10001, mode0400); TLS private key by UID101 (normally owner101,
   mode0400), with the public chain readable as appropriate. Preserve secret/key
   bytes. The helper does not change ownership or content of these external
   private inputs. Run preparation with the necessary local operator privileges
   so **new destination data** can be owned by UID10001. New data/media/upload
   directories use0700; static files use the shared readable-static policy.

```text
python3 /candidate/release/deploy/customer/customer.py verify --package /candidate --manifest-sha256 TRUSTED_MANIFEST_SHA256
python3 /candidate/release/deploy/customer/customer.py load --package /candidate --acknowledge-draft
python3 /candidate/release/deploy/customer/customer.py prepare --package /candidate --runtime /srv/NEW_isurvix_runtime --host customer.example.test --lan-ip 192.168.10.5 --secret-file /srv/isurvix-private/django-secret --tls-directory /srv/isurvix-private/tls --acknowledge-draft
python3 /candidate/release/deploy/customer/customer.py initialize --package /candidate --runtime /srv/NEW_isurvix_runtime --acknowledge-draft
python3 /candidate/release/deploy/customer/customer.py create-owner --package /candidate --runtime /srv/NEW_isurvix_runtime --acknowledge-draft
python3 /candidate/release/deploy/customer/customer.py start --package /candidate --runtime /srv/NEW_isurvix_runtime --acknowledge-draft
python3 /candidate/release/deploy/customer/customer.py status --package /candidate --runtime /srv/NEW_isurvix_runtime --acknowledge-draft
```

`load` loads the supplied image archive locally and verifies resulting image IDs.
Compose has `pull_policy: never`; initialize/start also explicitly use `--pull
never`. There is no pip, registry, model or certificate download at runtime.
`initialize` executes existing migrations and static collection against a **new**
database only. It does not create a user, sample company, engineering decision or
approval. Interrupted initialization is retained with a marker and cannot be
blindly repeated. Recover into another new target after diagnosis.

`create-owner` runs Django's existing interactive `createsuperuser` command in the
terminal. The operator enters credentials directly; no password is generated,
passed as an argument, recorded in this helper's output or shipped in the package.
The owner then uses existing company/admin/invitation controls in the application.
There is no separate customer user store or seventh role.

The proxy publishes HTTPS8443 and HTTP8080 **only on the selected private LAN
address**. Django's8000 is internal. `/media` and `/media/` are denied at the
proxy; evidence/output access remains authenticated and project/release scoped
through Django. The proxy mounts static files and TLS inputs, never the media
tree or database. Ollama11434 is never published. Native AI is not started or
downloaded by this installer. Existing independent PC workers require their own
approved matching release, scoped credentials and installed vision model.

## Second-device acceptance

From a second authorized LAN browser, resolve the approved hostname and open
`https://customer.example.test:8443/`. Verify the trusted TLS chain, invited login,
company/project isolation, task/site data, category upload, submission/review,
report access and anonymous/private-file denials. Test restart persistence and
the agreed operating mode. A loopback browser or second disposable container is
useful integration evidence, **not** proof that a physical customer LAN browser,
DNS, firewall, certificate trust or device policy works. Record that acceptance
separately before marking task16 complete.

## Restart, backup, restored upgrade and rollback

`stop` stops containers without deleting data or volumes. `start` reuses the
same initialized database, media, secret references and exact image identities.
Neither action switches releases or silently initializes missing storage.

Before maintenance, stop **every** web/worker writer. Use the existing
`staging_backup` management command with `--quiesced`, an external private backup
mount and a **new** destination. The shared operations guide documents the exact
SQLite/media manifest, checks and access requirements. Backups contain private
customer records and credential hashes; never put them in distributable packages.
Validate and restore through `staging_restore` or the package's explicit new-target
flow below. A same-drive restore is not an off-device recovery acceptance test.

```text
python3 /NEW_candidate/release/deploy/customer/customer.py load --package /NEW_candidate --acknowledge-draft
python3 /NEW_candidate/release/deploy/customer/customer.py prepare --package /NEW_candidate --runtime /srv/NEW_restored_runtime --host customer.example.test --lan-ip 192.168.10.5 --secret-file /srv/isurvix-private/django-secret --tls-directory /srv/isurvix-private/tls --restore-backup /private/VERIFIED_backup --acknowledge-draft
python3 /NEW_candidate/release/deploy/customer/customer.py migrate-restored --package /NEW_candidate --runtime /srv/NEW_restored_runtime --acknowledge-draft
```

Preparation runs the shared strict backup validator/restorer into the **new copied
data target**. It preserves the backup artifact/live source. `migrate-restored`
explicitly applies the candidate's migrations/static collection to that restored
copy; startup is refused until this step succeeds. A failed/previous attempt is
retained for diagnosis and cannot be silently reinitialized. Keep original
installation stopped/preserved; compare logical records, evidence SHA256 hashes,
reviews/approvals and existing evidence/report links before authorized cutover.

Absolute paths from a different operating system may require a separately
verified migration procedure. Copying a Windows backup to Linux and preserving
file bytes does not prove every saved report/output path is portable. This
candidate does not automatically rewrite historical paths or decisions.

Rollback uses a separately verified backup and the matching previously approved
image/source, restored to **another new target** with its original secrets.
Preserve the failed candidate and its diagnostics. Do not downgrade a live schema,
reuse an incomplete snapshot, delete originals or use a blind `down -v` command.

## Operating modes and limitations

The package supplies server images, tracked local assets and any dependency-bundled
OCR weights. Separately installed Ollama weights/caches and private credentials
remain external; the builder does not collect or automatically fetch them. The
default hosted settings disable local Ollama inference. Business/offline-browser
claims and connected/local AI claims
are defined in the task17 evidence, not inferred from package creation.
Website availability is independent of the PC worker. Unsupported or offline AI
stays visibly queued/failed through the existing processing mechanism; it must
not be reported as analyzed or approved. An approved HTTPS-provider worker needs
explicit external connectivity and credentials; this base offline compose does
not silently add an egress-capable worker.

Known D1/D2 dependency, CS1/CS2 operations and AI1 audit findings remain held as
recorded, alongside earlier unresolved native/private-helper/ACL findings. This
candidate neither remediates them nor bypasses owner review. Windows-native
installation, real customer/second-device tests, native model accuracy, live
commercial-provider access and customer release/commercial approval remain
outside the ordinary controlled package tests.
