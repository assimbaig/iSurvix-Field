# Cloud staging delivery07–09

The existing Django application now has a reviewable staged deployment and recovery
package. **Actual target-server/public-launch acceptance remains Blocked.** No
production deployment, merge, live migration, model download or native AI request
was performed. The main operational checkout remainsfd365f1/schema0053.

## Implemented and connected

- Fail-closed staging settings: private file-backed secret, explicit DNS/origins,
  persistent data outside code, exact baked release identity and no VPS inference.
- Exact tracked-source export, immutable image promotion policy, non-root web/proxy,
  private backend network, loopback-published proxy ingress and TLS configuration.
  Proxy mounts static/TLS only; raw media is denied and Django retains file authorization.
- Public minimal health probes and platform-owner-only aggregate diagnostics with
  bounded request-ID correlation; no source evidence or exception payload disclosure.
- Quiesced consistent SQLite/media backup and verified restore into NEW targets.
  No existing database or directory is overwritten or automatically activated.
- Disposable Linux CI exercises real image build, schema upgrade, backup/restore,
  TLS readiness/static/private-file denial and restart persistence.

## Executed evidence

Implementation7e88049 is verified by [Linux deployment CI](https://github.com/assimbaig/iSurvix-Field/actions/runs/41214056349).
The downloaded artifact SHA256 matched GitHub's digest. Approved-image candidates
and observed package/OS inventories are retained under `staging-ci-20261031/`.
They are observed build inventories, not a bit-reproducible source-build promise,
complete SCA clearance, published registry image or approval to deploy publicly.

[Application CI](https://github.com/assimbaig/iSurvix-Field/actions/runs/41214056106):
Windows1407/1407 passed, zero skips; Linux1405 passed with two existing Windows-only
skips, zero failures/errors. Hosted Chromium verification passed. Local1407 run:
1406 passed, one unchanged WinError1314 diagnostic-symlink fixture error before its
assertion, zero failures/skips. Local full suite is **not green**. All19 frontend
scripts and8 system/build/syntax checks passed. Final source remained unchanged;
exact commands/timings and fingerprint are in the acceptance JSON.

Independent QA passed13 unit/HTTP tests,39 real HTTPS browser checks and14 final
restart/proxy checks. Engineer UI uploaded200 unique small PNGs in6.699seconds;
two additional concurrent uploads and exact replay left202 unique photos total,
735364bytes. This is an upload-capacity fixture, not production transfer/native-AI
throughput. QA opened while AI was queued; manual QA→Team Lead→Client/report and
approved locks passed on synthetic saved records. Seventy-one fixture tables and
406 media hashes survived backup/restore and same-data app restart.

Separate security review passed12 isolated cases and36 actual HTTPS checks in scope.
After the WAL repair, an independent reader reran24 operations and12 existing
security regressions; a separate configuration review reran20 deployment tests.
These counts overlap where noted; they are not added to full-suite totals.

The full non-destructive recovery drill restored3537 media files and70 tables from
a trusted restored COPY/fresh SQLite snapshot. All media hashes and complete
logical SQLite dump hashes matched. Operational verification separately confirms
3595 protected files,70 live tables and two prior untracked audit reports unchanged.
Owned browser/proxy services were stopped; the original loopback Ollama was untouched.

## Defects found and repaired

Meaningful executed RED/GREEN checks accompanied implementation. Actual browser
and Linux execution exposed failures that mocks/static inspection did not prove:

1. Diagnostics nullable choices/status scope: queued jobs were counted as stale,
   photo running/completed states were obscured and a None choices value caused500.
2. Existing deploy helper rejected private file secrets. It now supports the
   staging file-secret path while preserving legacy plain secrets and backup gates.
3. Linux rehearsal host validation ran as the wrong UID after private0700 chown.
   Read-only validation now runs in the intended privileged context with an explicit
   nonsecret allowlist; private file/directory modes were not relaxed.
4. A proxy attached only to an internal Docker network was healthy but inaccessible
   through its published port. Only the proxy gained a normal ingress bridge;
   web/database/media remain private, and host publication stays on127.0.0.1.
5. Real-data WAL snapshots left sidecars rejected by strict restore. Only newly
   created backup databases are normalized to DELETE journal mode; standalone
   integrity inspection is immutable/read-only. Source mode/checkpoints/bytes and
   strict inventory guards remain intact. Committed uncheckpointed WAL rows survive.

Failed artifacts and interrupted broad test runs are retained privately and not
counted as passing final gates. An overly deep Windows recovery target hit MAX_PATH;
the failed target was marked incomplete, and the successful drill used short new
private paths under this F: project. No registry/global path-setting change occurred.
Browser harness repairs scoped CSRF locators/redirect expectations and explicitly
classified intentional external-asset aborts; unexpected failures still fail tests.

## Approval-held findings and remaining blockers

| ID | Severity | Finding | Required next action |
| --- | --- | --- | --- |
| D1 | High, existing | Pillow10.4/APNG allocation risk; current cap excludes the vendor fix. | Approve a compatible patched dependency and decoder-order regression work. |
| D2 | High, existing | Gunicorn21.2 matches request-parsing advisories; current cap excludes fixes. | Approve a supported patched release and actual proxy/parser verification. |
| CS1 | Low, new | Docker CI filter uses operational* rather than operations_*.py. | Approve corrected path coverage and regression checks. |
| CS2 | Low, new | Nginx logs use tmpfs without persistent/collector retention. | Approve privacy-preserving bounded retention and restart proof. |

All four remain UNFIXED; no owner approval was inferred from this development
request. Later Linux CI restarted containers but did not inspect proxy-log history
or execute hostile Gunicorn-parser cases. See the separate security report and
primary advisory links. Earlier A12/BR1/L1 and other holds remain unchanged too.

Missing target inputs: approved staging VPS/SSH identity reference and private
access route, approved DNS/TLS, target-compatible reviewed image and deployment
approval. Do not connect to the legacy example IP as if it were an approved target.
Physical phone, real PC/native Ollama connection, representative cloud concurrency,
actual target upgrade/recovery and off-device restore remain unverified. External
Bootstrap/Leaflet/fonts were deliberately blocked in browser fixtures; full asset
availability/offline functionality is not established. No public-launch proposal.

## Use and review

Read `STAGING_DEPLOYMENT_20261031.md` for source/image/private environment/TLS and
staging commands; `STAGING_OPERATIONS_20261031.md` for health, Windows outbound-worker
startup, backup/recovery and diagnostic commands. Exact commands and source hashes
are retained in the acceptance JSON. Review draft PR28, stacked after PR27/PR26.
Do not install on the operational database or expose a public site automatically.
