# Customer server and shared updates delivery

Review candidate on `feat/customer-server-readiness-20261031`, draft
[PR30](https://github.com/assimbaig/iSurvix-Field/pull/30), stacked afterPR29.
Nothing is merged, owner-released or deployed to a customer. Operational checkout
fd365f1/schema0053 and original evidence remain separate from this candidate.

## Implemented behavior

- Exact-source Linux/amd64 customer bundle with immutable app/proxy image IDs,
  local image archives, dependency/licence inventories and SHA256 verification.
  External TLS/secrets, fresh initialization and verified new-target restoration
  preserve existing data. Runtime installation never pulls images or models.
- Existing operational UI dependencies are local. Connected maps require explicit
  activation; core login, upload, submission and manual review work in controlled
  offline browser tests. No physical disconnected-NIC claim is made.
- Local PDF text/raster conversion uses pinned pypdf6.21.4/pypdfium2 5.14.0;
  worker-only scanned-PDF OCR uses existing RapidOCR1.4.4 and its bundled weights.
  Original files, protected previews, source references and human acceptance stay.
  No paid PDF/OCR API was found in the scanned code or introduced.
- Owner Update Center at `/ops/updates/`: trusted-catalog choices, real persisted
  requests/history, idempotency, one-active-request and recovery locks, CSRF and
  pending withdrawal. Saving a request waits for the host operator.
- Host-only apply/recover: fresh signed authority checks and ACKs, local image
  loading, quiesced backup, restored new runtime, migration/retention validation,
  internal web health then proxy/TLS activation. Postactivation uncertainty never
  silently reverts possible new writes. Independent journals stay outside DBs.
- Terminal history has a purpose-scoped authenticated seal, signed request and
  receipt validation, exact bindings and retained static/immutable proof checks.
  Replay preserves later human edits/uploads and requires no old service uptime.
- Shared candidate workflow requires successful same-source application, staging
  and customer checks, rechecks run identity after artifact transfer and binds the
  verified package/images to both editions. It emits only a gated draft artifact.

## Current verification

Verification source is `6f5f40d2b7e296e626636c700b85547f95bcd6be`.
All four required workflows succeeded on that exact source:

| Check | Actual result |
| --- | --- |
| [Application](https://github.com/assimbaig/iSurvix-Field/actions/runs/41228944646) | Windows: 1,611 passed, no failures/errors/skips, 465.613s. Linux: 1,609 passed, no failures/errors, 2 existing Windows-only skips, 472.415s. |
| Frontend in the same run | 19/19 frontend scripts and Chromium geometry passed. |
| Django/dependencies | System check, migration drift and pip check passed; zero external test requests, 107 controlled HTTP fixture connections. |
| [Staging](https://github.com/assimbaig/iSurvix-Field/actions/runs/41228944652) | Actual clean install, schema upgrade, TLS/private files, recovery and restart passed. |
| [Customer](https://github.com/assimbaig/iSurvix-Field/actions/runs/41228944635) | Actual Linux install, offline archives, restart, update/failure/interruption/recovery and original-data checks passed. |
| [Shared](https://github.com/assimbaig/iSurvix-Field/actions/runs/41228944697) | Gates rechecked; same package/images bound to both editions; generated artifact passed the actual updater consumer. |

Shared artifact 13052619886 is 475,897,661 bytes, SHA256
`afb9e7c4de6c9550a08aa0b077b1e9dea482613c76560ccdbdb57b77de50fec5`.
Its source is 6f5f40d; it remains a draft candidate, not an owner-approved release.
Later documentation commits are not substituted for this exact tested source.
GitHub artifact retention is 7 days; retain the complete verified package separately.

Exact commands included `python scripts/run_backend_tests.py --verbosity 1`,
`python -m pip check`, `python backend/manage.py makemigrations --check --dry-run --settings=checklist.settings_local`,
`npm test` infrontend, and the disposable `deploy/verify_staging.sh` /
`deploy/verify_customer.sh` rehearsals. Private controlled logs/receipts and
GitHub run/job IDs preserve the evidence; independent counts overlap the full
suite and must not be added as unique tests.


Component evidence includes26 developer updater tests,50 independent updater
checks (overlap),47 actual saved-data browser assertions,3 native loopback TLS
checks, and60 independent build-export/staging checks (overlap). Separate reviews
closed owner-approved CP1/CP2 and UP1 in their tested boundaries. Earlier8 holds
remain. Read the detailed reports for original REDs, exact commands and limits.

The latest release gate has12 passing tests, including the actual workflow
artifact layout consumed by the real customer updater validator. This test
first failed because the producer wrote `release.json` at the artifact root
while the consumer required `shared/release.json`; the producer now supplies the
documented layout. CI also validates the generated artifact with the real
consumer before uploading it. Cloud and customer edition records reference the
same immutable application and proxy images; they are not separately rebuilt.

Actual Linux run41228058279 at `4ac435f` verified fresh initialization, rejected
repeat initialization, offline archive loading with zero runtime image pulls,
restart integrity, strict TLS and raw-media denial. It then injected a caught
migration failure and a hard process interruption, recovered the old source,
completed a new update and replayed that request idempotently. All374 checked
rows across73 retained tables and the original evidence hashes survived.
The isolated client used a proxy NIC with no internet; the host-published TLS
listener was checked separately. This was not a physical second LAN device.
The18-file evidence ZIP was downloaded and checked against GitHub's SHA256
`3fa898e36934b309bd13722a01e59f7ec4c758a713f334f67b8b60af5b45857d`.

The final-source customer run41228944635 at6f5f40d also passed the same actual
Linux matrix. Root and independent Agency QA separately checked its18-file ZIP
artifact13053286662 against SHA256
`858339416a0e72231441a09cd08520eeefd447a414719c94a9e113d2b0fc4913`.
Its actual manifest hash is
`e95e269a57af0e3a4557c900e109755019f9926bbed41a137943d5223a1f1f1f`;
source/target374rows across73tables and evidence hashes agree. Source, immutable
image identities and installed-host-verifier references match the retained proof.

The first broad local run1605tests returned1604passed and1existing Windows
WinError1314 symlink-privilege fixture error,0failures/0skips.19frontend and11other
checks passed. Six source/config files changed during that run, so it was not a
frozen-source final gate. The unchanged error is not silently skipped or repaired.

A second local run had1610 tests:1608passed,0failures,2errors,0skips. One was the
same Windows symlink privilege; one was an old in-memory URL fixture parser while
its source changed. The corrected parser's focused rerun passed. Five source
files changed during that run, so it also is not frozen-source acceptance.
Its19frontend and11system/build checks passed. Hosted exact-source results are
the final regression gate; no local all-green claim is made.

The supported automatic-upgrade rehearsal is only baseline
`e37b28088a80de11e56f95a7989ad90f41fd9f48` (schema0057) to the exact tested candidate
(schema0057). Earlier0056 automatic upgrades are unsupported. The installed
baseline verifier checks target package bytes before reviewed host-tool use.
Do not generalize this pair to untested historical migrations or customer data.
The operational schema0053 is outside that automatic-update pair. Do not run
this updater against it; a separately reviewed migration/acceptance procedure is
required before an operational transition.

The complete gated candidate is saved under
`F:\iSurvix\iSurvix-Field\.local\c6\6f5f40d2b7e296e626636c700b85547f95bcd6be`.
The ZIP hash, CRC, safe extraction paths, complete package inventory and actual
trusted customer-consumer validation passed locally. Immutable image IDs match
the Linux proof. Docker was not run locally; real Docker execution was in the
disposable Linux CI. `shared/release.json` remains alongside `package/`.

## Owner procedure

1. Open the user menu and choose **Update Center** as the platform owner.
2. Select a trusted-catalog target and confirm the maintenance/recovery plan.
3. Save the request and pass its ID to the authorized local host operator.
4. Pending requests can be withdrawn. Verified/applying work requires the host
   recovery procedure; ordinary company administrators cannot perform updates.
5. Use **Check host receipts** to reconcile actual host phases. A missing or
   invalid receipt never implies completion. Preserve stopped/partial targets.

Operator configuration and exact Linux apply/recover commands are in
[deploy/customer/UPDATES.md](../../deploy/customer/UPDATES.md). A trusted catalog
and external read-only mounts are prerequisites; the web service has no Docker
socket and does not pretend an updater service is installed automatically.

## Windows development startup

These are startup instructions, not commands executed against operational data.
Use a separate candidate database/media and reviewed migrations for testing.
From the candidate checkout, the existing shared environment starts Django:

For a new disposable candidate only, first run
`backend\manage.py migrate --settings=checklist.settings_local` with the same
interpreter. These settings put the database/media in this worktree's `.local`;
do not substitute operational paths or interpret this as live migration approval.

```powershell
Set-Location 'F:\iSurvix\iSurvix-Field\.local\b6'
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' backend\manage.py runserver 127.0.0.1:8002 --noreload --settings=checklist.settings_local
```

The existing local processing worker command is:

```powershell
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' backend\manage.py survey_processing_worker --settings=checklist.settings_local
```

For a hosted server, use the existing outbound scoped worker instead of direct
server-database/filesystem access. Preserve its private configuration and use the
matching reviewed worker release:

```powershell
.\scripts\Start-RemoteSurveyWorker.ps1 -PythonPath 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' -PhotoOllamaUrl 'http://127.0.0.1:11434' -Model 'qwen3.5:4b' -ConfigPath 'PRIVATE_ISSUED_CONFIG_PATH'
```

The current source was not deployed to the operational checkout. Native Ollama
accuracy/runtime acceptance remains separate; no native model call was made by
this update work. The PC needs Docker/WSL installation separately to host Linux
containers locally; neither is installed by this development task.

## Remaining release gates

Actual customer server/second physical LAN browser, trusted target DNS/TLS,
off-device recovery, native vision/site accuracy, measured capacity/cost and
exact owner release approval remain separate. The service/maintenance offer is a
draft awaiting owner responsibilities/licence/commercial decisions.

Local MuPDF remains for drawing Unicode/HTML/rendering. It is a local library,
not a paid PDF API, but its AGPL/commercial redistribution route requires owner
review. No licence grant or paid licence purchase is fabricated here.

The eight earlier holds are A12(native runtime/accuracy), BR1(recovery helper),
D1(Pillow), D2(Gunicorn), L1(Windows filesystem/ACL), CS1(staging CI path filter),
CS2(proxy log retention) and AI1(nonsecret audit detail). They remain reported,
unfixed and unapproved; CP1/CP2/UP1 approval does not cover them. The recorded
High dependency findings D1/D2 remain release blockers. See the security reports
for severity, reproduction and recommendations. No new paid OCR/PDF API or model
download was introduced.

Final preservation verification rehashed3595 protected files and compared all70
operational tables to the checkpoint: unchanged. The two original untracked
audit reports remain. Operational migrations0054-0057 were not applied.

OCR limitations remain visible: the printed three-line native benchmark matched
1/3 exact strings and3/3 alphanumeric content; a separate one-line raster-PDF-to-
OCR test passed. Neither establishes handwriting/Arabic/site accuracy, engineering
compliance or sustained AI throughput.
