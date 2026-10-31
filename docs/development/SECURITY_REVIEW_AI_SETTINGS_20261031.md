# Separate security review: AI settings and routing

31 October 2026. Reviewer: independent Agency Application Security Engineer.
Result: no new exploitable authorization, secret-disclosure or stale-result
overwrite defect was established in this bounded review. **AI1 Low: configuration
audit detail gap** is confirmed and remains **unfixed, pending owner approval**.
This is not security clearance for public release or a claim of universal safety.

## Independence and authority

Read `AGENTS.md`, `docs/development/DEVELOPMENT_RULES.md`, the latest handoff and
installed `C:/Users/Muhammad Assim Baig/.agency-agents/security/security-appsec-engineer.md`.
Testing started only after the implementation lead's explicit **FUNCTIONAL
FREEZE**. The reviewer did not implement the feature, edit product code, change
dependencies, alter operational data or repair findings. The owner's instruction
"Do not fix that security review's findings until the owner approves those fixes"
takes precedence over profile recommendations to remediate immediately.

Worktree: `.local/b5`, branch `feat/ai-settings-routing-20261031`, parent delivery
`2dd7343c0b0619f404beabff72f1dac9fc625fa2` plus frozen implementation working changes.
The frozen implementation was subsequently committed as
`98092c2cc025bea0e5978d9678df22b70e1cc17b`. The lead normalized trailing EOF
whitespace only in two test modules and `ai_settings.html`; the eight application
source files inventoried for this review remained byte-identical. No security
finding was remediated by that normalization.
Eight reviewed application source files were SHA256-checked before and after;
all remained unchanged. Private inventories are under
`.local/ai-settings-20261031/security/source-before.json` and `source-after.json`.

## Scope and executed evidence

Read the actual company-settings HTTP/service checks, provider registry/parser,
transport, persistent policies/requests/attempts/quotas, survey-pipeline integration
and remote-worker deferral. Used synthetic companies, users, evidence and token
canaries in isolated test databases/media. No real credentials were read.

The following **11 independent post-freeze tests passed in 0.185 seconds**:

| Boundary challenged | Actual result |
| --- | --- |
| Foreign-company Admin writes through HTTP and direct settings service | Denied; no configuration created |
| Previously cached Admin principal subsequently locked or deactivated | Current persisted authority denied settings write |
| Unrecognized `api_key` POST field | Rejected without echoing/persisting synthetic credential value |
| HTTPS route without explicit evidence consent | Rejected before transport |
| Provider exception containing synthetic credential and endpoint | Public error and persisted request/attempt/audit receipts contained neither secret nor endpoint |
| Unsupported provider operation | Rejected before sending credentials |
| Operator alias retargeted after immutable policy pin | Evidence delivery rejected before network access |
| Old source attempt returns after another worker's successful retry | Old result rejected; exactly one successful receipt; no engineering approval or answer modification |
| Exhausted company quota | Second provider call prevented; foreign company quota untouched |
| Policy mutation and changed input under an already-completed source key | ORM mutation/input substitution rejected; successful result preserved |
| Configuration audit completeness | Reproduced AI1 below; assertion records the gap rather than treating it as a complete audit control |

Command, from the feature worktree using the existing project interpreter:

```text
PYTHONPATH=.local/ai-settings-20261031/security
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py security_review_tests --verbosity 2
```

The command exited 0, with zero external network attempts and zero fixture HTTP
connections. The tests use controlled transport faults rather than a real API.
Private receipt: `.local/ai-settings-20261031/security/tests.log`.

The reviewer also independently reran the existing private HTTPS fixture module:

```text
PYTHONPATH=.local/ai-settings-20261031/qa
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py tls_fixture_tests --verbosity 1
```

**11 tests passed in 10.748 seconds**: five explicit TLS/full-survey tests plus
six imported existing routing regressions discovered by Django. These six are
overlap, not new unique tests. Zero external attempts; 25 connections to in-process
fixtures. The five TLS checks exercise actual normalized image/Bearer delivery,
replay without duplicate inference, rejection of an untrusted certificate,
credential redirect rejection, disabled-local fallback over HTTPS, and a saved
survey through real draft PDF/DXF generation without human acceptance. Only the
fixture certificate is trusted in that process; production certificate verification
and the system trust store remain unchanged. Private receipt: `security/tls-rerun.log`.

## AI1 — Low: insufficient configuration audit values

**Evidence:** `backend/core/ai_processing_service.py:58` writes
`ai_settings_updated` with company ID, version, changed field names, `enabled`
and `primary_provider`. It omits the nonsecret previous/new values for external
evidence consent, daily quota, timeout, model and provider alias. The independent
test saved external processing with quota 23 and inspected the actual persisted
audit: consent was listed as changed, but its value, the limit and alias were
absent. The mutable settings row retains only the latest configuration. Immutable
job policy snapshots help only after a job has actually pinned that version.

**Impact:** an owner investigating a changed evidence destination or processing
limit cannot reliably reconstruct the exact configuration change from this audit
alone when no corresponding job snapshot exists. Actor/action/company/version
and field names are recorded, so this is a limited accountability gap; the test
does not establish unauthorized access or secret disclosure.

**Recommendation:** add a strictly allowlisted nonsecret before/after snapshot
for policy settings to the privileged-change event, retaining actor, company,
version and timestamp. Exclude tokens, credential environment values, raw provider
responses, uploaded evidence and connection URLs. Test reconstruction and redaction
together. Do not weaken immutable source results or human review to implement it.

**Disposition:** reported only. No fix performed. Owner approval is required.

## Limits and operational recommendations

- Previous A12/BR1/D1/D2/L1/CS1/CS2 approval holds remain unchanged. In particular,
  existing dependency and deployment findings are not closed by these tests.
- Native Ollama accuracy, live paid/vendor availability, actual target VPS access,
  off-device restore and production load were not tested. No native, external or
  paid inference request was made by this reviewer.
- The alternative API protocol is an operator-registered HTTPS Ollama-compatible
  service. Registry connections are intentionally shared platform-operated
  connections; the feature is not a per-company credential vault or universal
  commercial-provider integration.
- Quotas govern configured attempts, not a hard owner-controlled currency budget.
  Disabled configuration retains the existing local path. Pinned jobs retain
  their policy revision; changing current settings is not an emergency revocation
  mechanism for prior policy snapshots. Operators should revoke a compromised
  provider token at its source and use existing pause controls as appropriate.
- Secrets remain operator-managed environment references. A managed secret store
  or private file-backed integration is a future hardening opportunity; the
  reviewer did not inspect production secret storage or claim it was verified.
- No comprehensive dependency scan, multi-process hostile database race analysis,
  external penetration test or broad production security certification occurred.

Existing human approval controls were preserved in the tested boundaries. No
finding was fixed, no merge/deployment was performed, and no project service was
started or stopped by the reviewer outside the temporary test processes.
