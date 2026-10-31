# Separate AppSec review: cloud staging tasks07–09

**Result: public-release security acceptance remains blocked.** The scoped new
runtime attacks passed; existing High findings D1/D2 remain unresolved, actual
Linux/VPS validation is unavailable, and two new Low operational/coverage gaps are recorded.
No product file or finding was repaired by this reviewer.

## Independence and execution

The reviewer read the installed Agency AppSec profile, repository instructions,
handoff and development rules. Read-only inspection preceded testing. Separate
attack execution began only after independent QA reported the local functional
HTTPS workflow passing. Deployment source was then checked against the final
freeze, including the announced file-secret compatibility repair to `deploy.sh`.
That helper accepts a readable private key file only with staging settings and no
second plaintext key, does not print its contents, and retains the older
plaintext/check-only/backup-attestation behavior.

Executed on the final local source:

| Gate | Actual result | Scope |
| --- | --- | --- |
| Private unit/integration attacks | **12 passed**,0 failures/errors/skips,5.182 seconds | Isolated databases/media; zero external network attempts |
| Real HTTPS proxy attacks | **36 passed**,0 failed | Official PGP-verified portable Nginx with the actual rendered production template and synthetic Django records |
| Final source comparison | All13 deployment and8 operations freeze hashes match | Includes settings, Nginx, lifecycle/CI configuration and file-secret helper |
| New CI path-selection reproduction | Operations modules match **none** of the configured paths | CS1 below; not treated as a successful coverage gate |

The private unit attacks exercised path traversal, Windows reserved/short names,
case/Unicode collisions, file/directory prefixes, duplicate JSON keys, corrupt
SQLite despite a recomputed receipt, extra/missing files, unquiesced backup,
existing-target protection, interrupted copy, and an **actual Windows junction**.
They verified outside sentinels and original evidence remained unchanged. Health
attacks checked non-owner and forged-role access, safe request correlation,
redacted exceptions, truthful unavailable responses and method restrictions.
Configuration attacks rejected directive injection and unpinned image references.

The actual proxy checks exercised raw and encoded private-media paths, traversal,
Host rejection, forwarding-header spoofing, HTTP→HTTPS enforcement, no-cache
probes, six non-owner diagnostics denials, authorized originals, foreign-company
file/report denial, and Client release boundaries. A real separate draft source
was accessible to its Engineer and denied to the same-project Client; the reviewed
task's released sources/report remained available to its Client.

An initial harness assumption expected every unresolved twice-encoded path to
return4xx immediately. The observed middleware chain was301 trailing-slash
normalization followed by authentication denial. The corrected assertion follows
only that exact local chain and requires denial without evidence; it does not
accept an arbitrary redirect or a200 file response. Initial failure evidence is
retained privately. No application behavior was changed for the harness.

## Findings and approval status

| ID | Severity / classification | Evidence and impact | Recommendation | Status |
| --- | --- | --- | --- | --- |
| D1 | **High; existing approval-held upload dependency finding** | Current Pillow10.4.0 and the existing `<11.0` requirement remain; staging direct constraints preserve10.4.0. The maintainer lists the APNG allocation-order issue as affecting8.1.0–12.3.0. A potentially harmful allocation was not repeated in this review. | Obtain owner approval for a compatible fixed dependency and upload allocation-order regressions; verify normal photo/document workflows and resource limits. | **Unfixed; no new approval inferred** |
| D2 | **High; existing approval-held hosting dependency finding** | Current Gunicorn21.2.0 and `<22.0` requirement remain; staging constraints preserve21.2.0. This matches the known request-framing advisories. The local proxy fixture uses Django's development server, so it does not establish safety of Nginx paired with that Gunicorn version. | Obtain owner approval for a currently supported patched Gunicorn, compatible constraints and real proxy/parser regression tests. Do not equate a historical minimum fixed release with today's supported target. | **Unfixed; blocks public-hosting security acceptance** |
| CS1 | **Low; new verification-coverage gap** | `.github/workflows/staging-verification.yml` filters `backend/core/operational*`; actual files are `operations_backup.py`, `operations_service.py`, `operations_views.py` and `operations_urls.py`. An operations-only future PR would not trigger this disposable Docker workflow. The present PR still triggers through its deployment/workflow changes, and ordinary backend CI remains separate. | After owner approval, match the actual operations modules plus relevant route/integration changes and add a path-selection regression. | **Reported, not fixed; owner approval required** |
| CS2 | **Low; new operational log-retention gap** | The Nginx template writes access/error logs to relative `logs/` paths. Compose starts Nginx with prefix `/tmp/nginx/` and mounts `/tmp` as tmpfs, without a persistent log mount or stdout/stderr target. The configured proxy request/error history is therefore ephemeral rather than captured in the Docker log stream; it will not survive container stop/restart under documented tmpfs semantics. Actual Linux restart was not executed here. | After owner approval, send the existing privacy-preserving log format to an approved collector/stdout or a protected persistent log target with bounded rotation/retention; verify logs survive the recovery scenario. Do not introduce raw bearer URLs, cookies or sensitive request payloads while improving retention. | **Reported, not fixed; owner approval required** |

D1 is supported by the [Pillow maintainer advisory](https://github.com/python-pillow/Pillow/security/advisories/GHSA-5xm2-6676-qcp9),
which identifies13.0.0 as its fix. Current versions and constraints were checked;
the earlier isolated pre-allocation reproduction was not rerun here.
D2 is supported by the [Gunicorn maintainer's parser-security release notes](https://github.com/benoitc/gunicorn/releases/tag/22.0.0)
and the corresponding [CVE-2024-1135 record](https://github.com/advisories/GHSA-w3h3-4rj7-4ph4)
and [CVE-2024-6827 record](https://github.com/advisories/GHSA-hc5x-x2vx-497g).
The [maintainer's current support policy](https://github.com/benoitc/gunicorn/security)
must guide an approved upgrade. A dependency/version finding is not a claim that
a deployed smuggling exploit was executed successfully.

No newly exploitable runtime authorization/private-file/restore issue was
established in the executed scenarios. This bounded result does not clear D1/D2,
approve CS1/CS2, or establish universally secure operation. Prior A12/BR1/L1 and other
held findings retain their earlier status. The existing private BR1 restore helper
was not changed; the new production backup tool has its own tested boundaries.

## Trust assumptions and remaining verification

- Backup SHA256 receipts detect corruption, not an adversary replacing both
  bytes and manifest. Trusted private parents, verified provenance, restricted
  storage and separate secret/configuration backup remain operational requirements.
  Quiescence is an explicit operator attestation, not a distributed writer lock.
- CS2 concerns diagnostic history, not the database/media mount: it does not
  invalidate the executed original/result byte-preservation tests. Task08 notes
  should explicitly distinguish persistent application records from ephemeral
  proxy logs. Docker's [tmpfs documentation](https://docs.docker.com/engine/storage/tmpfs/)
  confirms that files on that mount do not persist after container stop. The
  classification is based on current configuration and documented semantics;
  it is not presented as an executed Linux restart experiment.
- POSIX modes and read-only container mounts express intended Linux controls.
  Actual target ownership/ACLs, non-owner OS access, volume persistence, off-device
  encrypted storage and restore have not been verified on a VPS. Passing a Windows
  junction test does not resolve the earlier Windows ACL finding L1.
- The fixture uses a local self-signed certificate. Private-path protection was
  tested through real TLS, but public DNS/certificate trust, Linux Gunicorn parser
  behavior, physical phones, sustained cloud concurrency and the native PC worker
  remain unverified. No Ollama request, model download, live survey approval or
  cloud/production mutation was performed.
- There was no complete dependency SCA scan. `pip check` checks dependency
  consistency; it is not a vulnerability audit. Direct build constraints are not
  a resolved Linux transitive lock. Review the actual image's package/OS inventory
  and immutable digest before any approved promotion.
- Existing external Bootstrap/Leaflet/font assets were intentionally blocked by
  the independent browser fixture and disclosed separately. These tests do not
  prove external-asset availability or fully offline application operation.

## Private evidence and commands

Private evidence is under `.local/cloud-staging-20261031/security/`:
`receipt.json`, `unit-attack-final.log`, `proxy-results.json`,
`ci-coverage-gap.json`, and the isolated attack scripts. Runtime auth fixtures,
bearers, keys and raw databases must not be published.

```powershell
$env:PYTHONPATH=(Resolve-Path .local/cloud-staging-20261031/security).Path
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' scripts/run_backend_tests.py security_assault --verbosity 1
node .local/cloud-staging-20261031/security/proxy_attacks.cjs
```

The actual-proxy command requires the designated isolated synthetic fixture and
owned loopback services, never an operational database. Full repository checks,
preservation proof, hosted CI results and final delivery are the lead's gates;
this report does not claim those unexecuted checks passed.
