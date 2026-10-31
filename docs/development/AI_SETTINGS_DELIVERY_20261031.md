# AI settings delivery — tasks 10–12

Implemented and verified in isolated tests on `feat/ai-settings-routing-20261031`,
implementation `98092c2` plus exact-navigation test update `4c40d1d`, [draft PR29](https://github.com/assimbaig/iSurvix-Field/pull/29)
stacked after PR28. Not merged or deployed. Live source remains `fd365f1`/core0053.

## What changed

- Company-scoped AI Settings in the existing navigation; current Admin/owner
  permissions, POST/CSRF, saved-version conflicts, redacted audit and clear errors.
- Persistent immutable job policies, source/mapping receipts, daily company quotas,
  bounded retry/lease handling and recorded local/approved-HTTPS fallback.
- Actual survey worker integration for image/document extraction and checklist
  mapping. Actual normalized image bytes and existing strict result validation are
  retained. Completed retries do not duplicate source results or human acceptance.
- Private operator connection aliases; credentials stay in the worker environment,
  not company records, forms, URLs or audit events. No model download/paid call.
- Hosted API-primary worker mode; legacy PC workers defer configured policies
  explicitly. Original evidence, template IDs and human approvals remain intact.
- Backward-compatible additive migration `0056_ai_processing_policy`. No dependency
  additions and no operational migration. Registry/transport/settings/model/service
  files, targeted pipeline hooks, compact template/CSS and regression tests are the
  implementation areas; the complete changed-file list is in PR29.

## Executed verification

| Check | Actual result |
| --- | --- |
| Focused affected unit/integration suite | 208 passed,55.455s; overlaps full suite |
| Independent ordinary unit/HTTP tests | 18 passed,7.048s; overlaps full suite |
| Real authenticated browser checks | 30 passed at1920/1366/390;0JS exceptions,0unexpected failed requests |
| Explicit real HTTPS fixture cases | 5 passed,4.267s; actual image/Bearer delivery, TLS/redirect rejection, saved-survey PDF/DXF and fallback |
| Separate new security tests | 11 passed,0.185s; review did not repair findings |
| Independent TLS rerun | 11 passed,10.748s =5TLS cases+6existing routing regressions, not11newTLS cases |
| Final local full suite | 1465run/1464passed/0failures/1error/0skips in632.437s |
| Frontend checks | 19 scripts passed |
| System/build checks | 8 passed: Django, migration drift, pip, JavaScript syntax, static collection, Python and2Bash syntax checks |
| Frozen source | 592 source/config/workflow files unchanged during final gate |
| Preservation | 3595 protected files,70 operational tables and2 existing untracked reports unchanged |

The local full suite is **not green**: the unchanged diagnostic symlink fixture
requires a Windows privilege unavailable in this session (`WinError1314`). No test
was skipped or weakened. Hosted Windows1465/1465 passed;Linux1463passed+2existing Windows-only skips;Chromium passed on4c40d1d. See acceptance JSON for exact commands/timings. [Hosted application run](https://github.com/assimbaig/iSurvix-Field/actions/runs/41218476239).

Browser fixtures intentionally aborted90external/CDN requests and recorded94console
messages(90network+4expected negativeHTTP). These are disclosed, not counted as a
full offline/external-asset availability check. Native Ollama, live API credentials,
manufacturer accuracy and the target VPS were not exercised.

## Bugs reproduced and fixed before separate security review

Configured local requests ignored the selected timeout; an actual delayed HTTP
regression failed, then passed after bounded transport was wired. API-primary
processing originally depended on local model verification/remote-project exclusion;
executed regressions now prove it can use the configured path with local disabled.
Worker/request leases and stale-attempt handling preserve completed receipts;
replays, zero quotas, invalid output and external-consent denials were checked.
The first incomplete final gate was stopped for three EOF blank-line corrections;
final2 exposed three stale Admin/Super Admin navigation expectations; independent QA confirmed the authorized new settings entry. Exact lists were extended with real route assertions while preserving every permission/private-data check.29focused tests passed, then final3 reran against frozen bytes. A mistaken test-label import was corrected;
it was a harness failure, not hidden as a passing application test.

## Review and remaining limits

**AI1Low remains unfixed:** audit events name changed settings but omit sufficient
nonsecret before/after values to reconstruct consent/quota/model/alias changes.
See [separate security review](SECURITY_REVIEW_AI_SETTINGS_20261031.md).
`AGENTS.md` requires owner approval before fixing this finding. Earlier
A12/BR1/D1/D2/L1/CS1/CS2 holds remain. This is not public-release security clearance.

API support is HTTPS Ollama-compatible; no commercial-vendor SDK or real-credential
acceptance is claimed. Hosted API-to-local fallback through a PC is not implemented;
local-disabled attempts record `local_worker_required`. Configured cross-revision
visual reuse is deliberately disabled; same-revision checkpoints persist. Separate
assistant/legacy-photo services keep their original settings. Operator-managed
registry aliases are shared platform connections, not tenant credential vaults.

Read [operator/team guide](AI_SETTINGS_GUIDE_20261031.md),
[independent QA](AI_SETTINGS_INDEPENDENT_QA_20261031.md), and
[requirements matrix](AI_SETTINGS_REQUIREMENTS_20261031.md).
Safe screenshots and synthetic unreleased PDF/DXF/PNG examples are under
`screenshots/ai-settings-20261031` and `samples/ai-settings-20261031`.
Owner also added tasks13-15. Concrete pilot, capacity/cost and exact-release worksheets are prepared in CLOUD_PILOT_GATE_20261031.md/.json; all three remain Blocked. No real pilot, target capacity/cost acceptance, production deployment or automatic merge was performed.

## Post-delivery first-pin regression follow-up

An independent saved-record regression reproduced interrupted native work being stranded when company AI settings were enabled. The repair preserves the first durable native/provider pin and all completed checkpoints.235affected tests,11independent repair tests+4countercases and17separate security checks passed; counts overlap as recorded in their reports. A new full CI run must verify the follow-up commit before reusing the earlier full-suite claim. This functional repair does not fix held AI1 or any older security finding.
