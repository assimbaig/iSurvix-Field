# Independent platform/customer administration QA

28 October 2026. Task05 acceptance: role tests reject privilege escalation and
privileged changes are audited. Review used the installed Agency Reality Checker,
UX Architect and Application Security Engineer definitions. Implementation was
owned by separate agents; this reviewer edited no product code.

## Current result

- **13/13 independent unit/HTTP tests passed** after functional source freeze.
- **2/2 supplemental HTTP positive-control tests passed**: platform-owner industry
  binding and customer-admin invitations for Engineer, QA, Team Lead and Client.
- **35/35 real-browser checks passed** across platform owner, company Admin,
  Engineer, QA, Team Lead and Client at1366x768 and390x844. No JavaScript errors,
  failed local requests or page-wide mobile overflow were observed.
- The actual company-Admin form changed a synthetic Engineer to QA, reloaded to
  verify persistence, then restored Engineer through the same UI. A separate
  database read verified the last two events' actor, target, company/project
  scope and before/after role snapshots. The final account retained no global
  staff/superuser flags.
- **9/9 separate post-functional adversarial tests passed**. See the separate
  security review for findings and limits. These overlapping checks are not a
  count of unique requirements or a whole-application certification.

All automated runs used isolated database/media/model-cache locations and
reported zero external network attempts. Browser fixtures used a separate SQLite
database and media under `.local/platform-customer-admin-20261028/qa/`, loopback
port8941, and blocked outbound socket connections. No operator database,
customer survey, evidence, worker or Ollama request was used.

## Acceptance evidence

| Contract | Actual behavior checked | Result |
| --- | --- | --- |
| Platform actions remain owner-only | Company Admin and operational roles denied industry binding, company/owner assignment and reset routes; target state unchanged | Verified |
| Customer authority stays scoped | Self, foreign Admin, owner and foreign membership targets denied; Admin/Super promotions and invitations denied | Verified |
| Privilege fields cannot be smuggled | Valid-CSRF member/invite/acceptance requests with protected global flags rejected without partial writes | Verified |
| Existing invitation compatibility | Customer operational invite may include legacy ignored `admin_industry`; saved role, company/project and issuer industry remain server-controlled | Verified |
| Valid administration still works | Company Admin role change, four operational invitation roles; owner project Admin assignment, industry binding and Admin invitation acceptance succeed | Verified |
| Owner remains administration-only | Owner denied engineering evidence/workspace, Client decision, Client creation and project creation; existing answers preserved | Verified |
| Privileged audit | Actual successful routes save versioned actor/target/scope/before/after while retaining legacy event keys; audit-insert failure rolls back role change | Verified |
| Saved audit is historical | Renaming/rebinding an actor does not rewrite existing snapshots; application ORM update/delete attempts denied | Verified |
| Audit visibility | Customer Admin sees own-project event, not foreign-project event; owner sees global events | Verified |
| Legacy bypasses | Retired `/admin/` and `/devadmin/`, bootstrap setup and forged session flags do not grant platform authority | Verified |
| Browser and persistence | Six actual role views, allowed role mutation, refresh, restoration and database audit readback | Verified |

## Reproductions and repairs verified

The initial independent RED run executed12 tests and produced10 failing
assertions/subtests. Missing audit envelopes and fail-closed handling of extra
privilege fields were reproduced. Existing authorization already prevented
global flag escalation; ignored unknown fields were not reported as a proven
superuser leak. The final contract preserves the established safe-ignore
operational invitation industry field, verified against saved state rather than
requiring an incompatible new400 response.

The Admin-invitation path separately verifies a previously unowned project has
`before.administrator_id=null` and the accepted Admin in `after`; this catches
automatic ownership side effects before a snapshot is taken. Its initial local
fixture omitted the required invitation email; that fixture was corrected and
is not presented as an application defect.

Browser harness corrections used the form's actual `action` attribute (a hidden
input named `action` shadows the DOM property) and navigated back to
Administration after the application's normal post-save redirect. These were
test-harness repairs, not product UI defects or mocked navigation.

## Commands and receipts

From the feature worktree with the existing environment:

```powershell
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' scripts/run_backend_tests.py core.test_platform_customer_independent --verbosity 1
$env:PYTHONPATH=(Resolve-Path .local/platform-customer-admin-20261028/qa).Path
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' scripts/run_backend_tests.py positive_controls.AdditionalAuthorityControls --verbosity 1
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' scripts/run_backend_tests.py security_assault.PlatformSecurityAttacks --verbosity 1
node .local/platform-customer-admin-20261028/qa/browser.cjs
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' .local/platform-customer-admin-20261028/qa/verify_saved.py
```

Private receipts: `independent-red.log`, `independent-functional-final.log`,
`additional-positive.log`, `browser-results.json`, `browser-persistence.json`,
`separate-security.log`; all under the private QA directory above. Screenshots:
`owner`, `admin`, `engineer`, `qa`, `lead`, `customer`, each with `-1366.png` and
`-390.png` suffixes. Synthetic accounts only; session-cookie fixture is private
and must not be committed.

Frozen source SHA256:

- `backend/core/governance_views.py`: `95dd10ce871080fd613c5e9f25963dd7ae53511ec1178a85241a364ff2f874bd`
- `backend/core/privileged_audit.py`: `caafcaf7ef2a29f87d26a186abed34aeb9f5e96ba46030ca9ec7f563ff002625`
- `backend/core/test_platform_customer_independent.py`: `f87a46c8d0ed9f02f5d4e38ab534e8e4abe2ee611c9654b8f196dcc312000cf8`

The lead owns the full backend/frontend/migration gates and final delivery
ledger. This focused result does not assert those broader checks passed.

## Limits

No production deployment, deployed Nginx/TLS behavior, native model processing,
hostile upload-content audit, exhaustive concurrency/fuzzing or real-device
testing was performed here. The test server is independent of the operational
application. Existing approval-held findings, including A12/BR1/D1/D2/L1, remain
outside this task and were not implicitly approved or repaired.
