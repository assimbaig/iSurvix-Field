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
