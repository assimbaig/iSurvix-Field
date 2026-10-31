# Shared draft release gate: separate component security review

31 October 2026. Independent Agency Application Security Engineer, after the
implementation lead declared this component functionally frozen. Worktree
`.local/b6`, branch `feat/customer-server-readiness-20261031`.

**No new exploitable defect was established in the bounded gate review. Ten
independent security cases passed. This is not release/deployment approval or a
claim that actual install/upgrade CI has passed.** CP2 repair and other integration
work were separately in progress; their status is not determined by this report.

## Scope and independence

Read actual `deploy/release_gate.py`, `.github/workflows/shared-release-candidate.yml`,
the exact-head checkout in `repair-validation.yml` and the customer workflow's
artifact-producing steps. Read repository/owner rules and the installed Agency
AppSec definition. No gate/application source, core tests, credentials, services
or operational data were modified by the reviewer.

The gate downloads the named package and verification artifacts from the exact
required customer run ID, fetches current required checks again before assembly,
requires unchanged run IDs/attempts, and binds release/image/manifest identity to
the install/upgrade proof. Application checkout uses the PR head SHA rather than
implicitly testing only a merge commit. Hidden-file artifact inclusion preserves
the reviewed source; credential screening remains the separate customer package
gate and must not be confused with this option proving secrets absent.

The workflow has read-only repository/Actions permissions and uploads an explicitly
unapproved draft artifact. It neither creates a release nor merges or deploys.
All existing security/licensing/target-acceptance holds remain separate.

## Executed private security checks

Process-local `PYTHONPATH=.local/customer-server-20261031/release-gate-security`:

```text
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py gate_security --verbosity 2
```

**10 passed in 0.024 seconds**, zero failures/errors/skips, zero external network
attempts and zero fixture HTTP connections. These are synthetic CI records and
controlled transport faults, not an actual GitHub Actions execution.

| Attack/countercase | Actual result |
| --- | --- |
| Foreign repository, deleted head repository, other source SHA | Cannot satisfy required same-source workflows |
| New failed attempt hidden by ordering or an old higher run number | Publication blocked regardless of input-array order |
| Missing/pending workflow versus completed failure | Missing remains blocked; failure is not treated as a retryable pending success |
| Wrong proof image/manifest/source, missing upgrade proof or same-version restart | Candidate record rejected |
| Old/future observation or changed attempt during artifact transfer | Final gate pair rejected |
| Token-bearing upstream transport exception | Controlled diagnostic excludes synthetic token and raw private path |
| Redirect or credential containing a newline | Rejected before forwarding credentials |
| Malformed API workflow payload | Fail-closed; cannot establish a verified gate |
| Draft candidate records | Remain unapproved; approval holds retained; approved-manifest substitution rejected |
| Existing output record or failed gate publication | Existing bytes preserved; failed gate creates no publication file |

Private evidence: `gate_security.py`, `checks.log`, `receipt.json`,
`source-before.json` and `source-after.json` under
`.local/customer-server-20261031/release-gate-security/`. Four reviewed gate/workflow
source hashes matched before and after the review. The private cases are separate
from existing tracked tests; do not inflate the ordinary full-suite total.

## Trust boundary and remaining gates

Gate/proof JSON is not a detached signature or independent attestation. The
documented trusted CI workflow, GitHub-hosted run/artifact provenance, exact image
identity and independently delivered digest remain the trust root. Shape checks
reject mismatched or incomplete proof; they do not authenticate arbitrary
self-consistent files supplied by a malicious local operator. Do not treat a
locally edited `release.json` or content hash alone as owner release approval.

This review did not call GitHub with a real token, download a candidate, execute
Linux Docker install/upgrade/recovery, validate target devices, scan dependencies
or perform destructive/native stress testing. Actual CI and supported-upgrade
evidence must be inspected against the exact final commit. The Update Center and
privileged updater were not yet functionally frozen and are outside this review;
their later assembled trust boundary needs a separate post-functional review.

CP1/CP2 repair status is in `CUSTOMER_SERVER_SECURITY_REVIEW_20261031.md`. Earlier
A12/BR1/D1/D2/L1/CS1/CS2/AI1 findings remain held. No unrelated repair approval is
inferred. No product/security fix, customer deployment or merge was performed.

## Final isolated-client/artifact-consumer follow-up at `6f5f40d`

The lead requested this bounded follow-up after commits `4ac435f` (Linux fixture
permissions/isolated-client topology) and `6f5f40d` (real artifact-consumer layout).
The reviewer inspected those exact diffs, actual workflow/script paths and the
installed updater `_package` consumer. No broader implementation or product edit
was performed. Six new private cases plus seven original CP controls and the
original UP1 countercase ran:

```text
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py artifact_security customer_security updater_security.IndependentHostUpdaterSecurityTests.test_UP1_terminal_journal_cannot_replay_another_requests_completion --verbosity 2
```

**14 passed in 4.094 seconds**, zero failures/errors/skips, zero external attempts
and zero fixture HTTP connections. Eight cases are repeat closure checks, not
new unique ordinary tests. No real Docker or customer records were used.

The new cases extracted the producer's actual `shared/release.json` relative path,
created a valid synthetic package/record using the real gate, reproduced the
workflow's actual hard-link copy into `<exact-SHA>/package` and
`<exact-SHA>/shared/release.json`, then invoked the actual installed updater
consumer. Matching package/images passed. Different record source/images or
owner-approval label, a missing record, altered image archive and a traversal
target at the signed-request boundary were rejected without execution.

The separate client now reaches an added isolated proxy NIC/DNS alias instead
of pretending to traverse the host-published port. A distinct host-side probe
still checks the real published listener using `--cacert`, `--resolve` and
`--noproxy`, then confirms the exact release. The isolated client retains CA/
hostname verification and explicitly reports `client_used_host_published_port`
false. No unverified SSL context, `verify=False`, `CERT_NONE` or insecure curl
flag was introduced in the reviewed scripts. This is source/configuration and
static-consumer evidence, **not a native topology run by this reviewer**.

The shared workflow still has read-only permissions, downloads the required
same-source customer-run artifacts and uploads only the explicitly unapproved
shared candidate. No fixture password, host journal, runtime database or Docker
socket was added to that artifact path. This inspection does not certify that a
conservative artifact screen detects every encoded/opaque secret.

CP1/CP2 closures remain intact: nine relevant package guard function ASTs match
their reviewed `e37b280` source, and the original private assertions passed.
The whole customer helper has later inventory/configuration changes, so the
reviewer does **not** claim its old whole-file hash is unchanged. UP1's updater
hash still exactly matches its approved closure, and its original countercase
passed again. The eight earlier approval-held findings remain unchanged.

Six follow-up source/script/workflow hashes matched before/after this review.
Private evidence: `.local/customer-server-20261031/final-artifact-security/`
contains `artifact_security.py`, `checks.log`, `closure-guards.json`, source
inventories and `receipt.json`.

**No new exploitable finding was established in this bounded follow-up.** At
the request, the lead reported prior customer CI `41228058279` successful and
current `41228944635` still running; this reviewer did not replace those actual
run receipts with local assertions or claim the current run had passed. Final
same-source CI/artifact digests, physical target devices, licensing and owner
release approval remain separate delivery evidence/gates.
