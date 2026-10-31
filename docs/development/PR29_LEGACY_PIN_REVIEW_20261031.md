# Independent review: preserve legacy native processing pins

Reviewed 31 October 2026 in `.local/b5`, branch
`feat/ai-settings-routing-20261031`, against delivery `40fe6d4` plus the approved
functional preservation repair. This is a new functional defect repair, **not
the cause of an old GitHub CI failure**: the prior PR29 delivery checks passed.

The independent reviewer read `AGENTS.md`, the latest handoff and development
rules, and used the installed Agency Reality Checker/API Tester profiles. The
reviewer did not edit application code, the implementing agent's regression
tests or the policy guide. Only private countercase tests, receipts and this
report were authored during this review.

## Contract and implementation assessment

The **first durable pin** controls an existing job. An already-started native
revision must retain its native model identity, checkpoints and original local
or remote worker when a company later enables configured providers. A previously
unpinned job may select the saved company policy at its first pin. An existing
company provider policy remains pinned; enabling settings does not overwrite or
delete either kind of pin, accept findings or change an engineering decision.

The small application diff is consistent with that contract:

- `ai_processing_service.configured` reads the persisted job pin rather than
  trusting a stale caller object. A native pin without a provider policy keeps
  the legacy processing path.
- `policy_for` rejects rebinding such a native-pinned job, including through a
  stale object. Existing provider policies retain their integrity/company checks.
- Worker claim predicates exclude native-pinned remote jobs from opportunistic
  server/API-only claiming. They still allow unpinned configured work and jobs
  with a saved provider policy.
- Legacy timeout/lease budgeting remains unchanged by later company settings.
- The guide now explains first-pin behavior without claiming hosted-to-PC
  fallback or emergency policy revocation.

The changed old remote-policy test legitimately replaces its previous
contradictory expectation that enabling settings should block an already-pinned
native lease. Its new assertions require the native pin to remain unchanged and
forbid creating a provider policy. The neighboring unpinned-job deferral and
disabled-configuration tests remain. No authentication, credential scope,
version-pin, file permission or approval assertion was removed by this repair.

## Independent executed checks

Existing repair/remote-policy regressions:

```text
F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe scripts\run_backend_tests.py core.test_pr29_legacy_policy core.test_ai_remote_policy --verbosity 2
```

**11 passed in 0.709 seconds**, zero failures/errors/skips and zero network
attempts or fixture connections. This includes eight new implementing-agent
regressions and three updated/existing remote-policy tests. These are separate
independent executions of tests also included in the broader affected suite;
do not add them to the unique full-suite total.

Four additional private countercases were independently written and executed
with process-local `PYTHONPATH` pointing to
`.local/ai-settings-20261031/pr29-legacy-qa`:

```text
F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe scripts\run_backend_tests.py countercases.PolicyTransitionCountercases --verbosity 2
```

**4 passed in 0.283 seconds**, zero failures/errors/skips and zero network
attempts or fixture connections:

1. After a saved source checkpoint and interrupted native inference, enabling
   company settings does **not** permit changed native model weights to resume.
   The existing model-mismatch error remains, no additional source is inferred,
   and the original checkpoint/pin remain unchanged.
2. Disabling/changing the company's current configuration does not replace an
   existing API policy snapshot. That job remains claimable by its configured
   worker even with a remote-enabled project.
3. A queued, unpinned job chooses the latest saved company settings at its first
   provider-policy pin.
4. A stale job object with an empty digest does not hide a native pin already
   stored in the database.

The actual saved-record interrupted-job regression verifies exactly one remaining
photo inference on resume, an unchanged retained source payload/digest/ID and no
new provider policy. The remote regression verifies the existing scoped lease can
complete a source while preserving its native identity. Inference and rendering
boundaries in these tests are deliberately controlled; no actual Ollama/API
generation, visual accuracy or real-device recovery is asserted.

## Evidence and limits

Private receipts:

- `.local/ai-settings-20261031/pr29-legacy-qa/focused.log`
- `.local/ai-settings-20261031/pr29-legacy-qa/countercases.log`
- `.local/ai-settings-20261031/pr29-legacy-qa/receipt.json`

The reviewer checked the five changed-file SHA256 values against the implementing
agent's `legacy-pin-repair.json`; all matched. The implementation receipt records
an executed six-test RED run (four failures, one error, one pass) followed by an
affected 235-test GREEN run. Those are implementing-agent receipts, distinct
from the independent commands above.

No new functional defect was established in the reviewed scope. This permits
integration of the functional repair; it is **not release/deployment approval**,
native-model validation, a comprehensive concurrency proof or a separate AppSec
clearance. No operational DB, uploads, approvals, service or credential was
changed. Earlier security findings remain held; none was repaired by this review.
The final integrated branch still needs its affected/full regression and separate
security review recorded against the actual resulting source.
