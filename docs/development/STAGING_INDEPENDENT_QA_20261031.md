# Independent cloud-staging verification

**Public-launch acceptance remains Blocked.** The environment has no installed
Docker/WSL runtime, approved staging host/credentials or deployed Linux service.
The checks below establish local behavior, not a clean VPS install, WAN capacity,
physical-phone acceptance or production TLS. No operational data was used.

The reviewer read the installed Agency Reality Checker and AppSec definitions,
repository handoff and owner development rules. Deployment, operations and QA
had separate file ownership. A different AppSec agent performs the post-functional
attack review; that report must be read separately before release consideration.

## Unit and integration evidence

Thirteen independent tests are in `backend/core/test_staging_independent.py`:

- Staging configuration uses persistent database/media, secure cookies and disabled
  native inference; invalid release/hosts/debug/inference settings fail closed.
- Minimal public liveness/readiness responses and current platform-owner-only
  operational diagnostics preserve privacy and truthful failure states.
- Real SQLite plus original/output files survive backup/restore. Corrupt or
  incomplete backup data and existing destinations are rejected.
- Actual category upload reaches QA while processing is queued; synthetic AI
  failure still permits manual QA, Team Lead and Client completion through existing
  routes. Uploaded bytes remain unchanged.
- Private originals require authentication and company/project access; a direct
  `/media/` path cannot bypass Django protection.

Meaningful RED was executed before the new settings, routes and backup module
existed. The initial Windows fixture omitted an explicit SQLite connection close;
that harness issue was corrected before the preserved clean RED. Staging's later
baked-release-file and missing-database contracts were supplied in the positive
fixture rather than weakening configuration validation.

Independent testing caught an actual pre-security functional defect: owner
diagnostics iterated `status.choices` when that value was `None`. The implementing
agent repaired the fallback and reran its regressions. An initial independent GREEN
passed13/13 in3.978 seconds; the final-source rerun passed **13/13**, zero external
connections, in5.187 seconds. No product changes
were made by QA. The tracked test SHA256 is
`6f71a910b5d0d14c96fd67c3913914993f072b16253ce82b8b56c818aa01e390`.

```powershell
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' scripts/run_backend_tests.py core.test_staging_independent --verbosity 1
```

## Actual local Nginx/TLS browser flow

The lead supplied the official portable Windows Nginx build and verified its
signature. A rendered production template was adapted only for loopback ports,
test certificate and local upstream/static paths. Real Django used the new staging
settings, isolated SQLite/media and disabled outbound networking. The test
certificate was self-signed; browser TLS validation was bypassed only for this
loopback fixture. This is not approved public TLS or a Linux deployment.

Edge used the test hostname `staging.example.test` mapped to loopback, HTTPS8952
and a Django upstream on8951. **39/39 browser checks passed**:

- Real HTTPS liveness/readiness and a bounded release identifier.
- Direct private-media paths denied across originals, outputs, documents and
  branding; owner-only status access remained protected.
- Engineer edited General Info, uploaded200 distinct synthetic PNGs under Civil,
  Electrical and Tower using the real category UI, then submitted through the
  actual HTTPS form.
- Uploads used11 bounded UI requests. Two additional concurrent requests and one
  exact replay produced202 unique photos, not203. Both concurrent first responses
  were201; the replay returned `duplicate=true` with the existing source.
- Refresh retained category assignments. An authorized download matched the exact
  original SHA256; anonymous and foreign-company requests did not return its bytes.
- QA saw the submission with the local worker offline and its job still queued.
  Manual synthetic answers, QA completion, Team Lead and Client decisions, and the
  permitted report export used real authenticated Django endpoints and records.
- Desktop1366×768 and phone390×844 had no page-wide overflow. A separate readonly
  capture used the actual QA drawer controls to select Civil evidence on mobile.
- No JavaScript exceptions or unexpected failed requests occurred.

The initial terminal network assertion incorrectly included the fixture's explicit
CDN aborts and its manual anonymous-redirect probe. That harness classification was
repaired, the first run retained, and the full scenario rerun with a fresh isolated
database. The final classifier registers each intended URL/action before its abort
or redirect probe. It does not blanket-ignore `ERR_ABORTED`, failed saves or local
request failures. All request failures and their reasons remain in the receipt.

The final browser recorded66 explicitly aborted external asset requests and one
manual anonymous redirect abort. Console evidence includes66 corresponding resource
errors and7 HTTP404 messages during negative probes. Bootstrap, Leaflet, icon and
Google Font CDN availability was deliberately not tested. **Do not claim offline
asset completeness or a fully loaded external-asset production interface.**

## Upload measurement and persistence

The local UI phase saved200 small640×480 synthetic PNGs in6.699 seconds. The202
unique sources total735,364 bytes. The two-concurrent-request/completion/replay phase
took831.2ms. Fourteen upload requests is the whole-scenario count; eleven belongs
to the200-photo UI phase. The receipt's UI counter was corrected from the already
recorded bounded-batch assertion snapshot; the original raw evidence is retained.

This is an **upload-capacity fixture**, not native AI throughput, a representative
full-resolution workload, sustained concurrency or a cloud cost/capacity benchmark.
All photo content is visibly synthetic. No measurements, extraction accuracy or
engineering compliance are established by these test inputs and synthetic decisions.

An independent readonly SQLite/file check confirmed:

-202 photos with202 distinct hashes; every original still matches SHA256.
- Civil71, Electrical71, Tower60.
- One submission revision, one queued processing job, no replay duplicates.
- Closed synthetic route and exactly the existing submit/validate/approve/
  customer-approve human decision sequence.

After the separate security agent completed its actual-HTTP window, QA captured
all71 isolated SQLite tables and406 media-file SHA256 values, stopped only its
owned Django process, and ran the actual new backup and restore APIs. The stopped
fixture had no other writer or inference worker. A new private backup artifact and
a new restored destination matched every captured table and media hash. This
includes202 uploaded originals, previews, all four human decisions, one submission
and one still-queued processing job. The source database/media stayed unchanged.

QA then restarted the app against the **same** original database, media and private
test key. All71 table digests and406 media hashes remained identical. On the final
rendered production proxy template, **14/14 additional checks passed**: live/ready,
request correlation header, actual collected static CSS, raw-private404 responses,
retained202 sources, approved-record edit lock, Engineer and released-Client exact
original downloads, denial of an unreleased draft source to Client, foreign-company
denial, and saved reviewed report export.

Private receipts are `restart-before.json`, `restart-backup-restore.json`,
`restart-after.json` and `final-proxy-results.json`. This is a local stopped-app
recovery drill, not a Linux service/container restart, off-device recovery or
remote PC-worker connectivity test. The lead owns the full repository gate,
deployment/upgrade receipts and final ledger. The separate AppSec agent's actual
HTTPS window reported36 passing attack checks; read its final report for scope,
remaining tests and any findings. No local check alone verifies the original
staging acceptance criteria or authorizes public launch.

## Evidence locations and limits

Private evidence lives under `.local/cloud-staging-20261031/qa/`:
`independent-red-corrected.log`, `independent-final.log`, `browser-results.json`,
`browser-progress.json`, `browser-persistence.json`, browser scripts and retained
partial/successful isolated fixtures. Cookies, synthetic bearer material, TLS keys,
raw fixture databases and logs must not be committed. An accidentally previewed
synthetic owner session was invalidated/replaced before the final browser run;
no operational credentials were read or changed.

Eight safe synthetic screenshots are under
`docs/development/screenshots/cloud-staging-20261031/`.

After final verification, QA stopped only its owned app process and confirmed
port8951 closed. The lead owns the separate proxy shutdown. The private
`server-stopped.json` receipt records process ownership; all fixture databases,
uploads, backup/restore artifacts and original operational services were preserved.

Outstanding external gates include a clean approved Linux staging install,
container build/pull, real service restart/upgrade, approved DNS/TLS/firewall,
outbound PC-worker connectivity, native vision correctness, off-device restore,
physical phones and representative WAN/concurrent workloads. Existing approval-held
findings retain their status. No new security finding is fixed without owner approval.
