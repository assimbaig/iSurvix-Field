# Tasks 10–12: AI processing settings and routing

Owner: Dot. Branch `feat/ai-settings-routing-20261031`, based on cloud-preparation
delivery `2dd7343`. Work is isolated in `.local/b5`. No operational migration,
native model request, paid request, merge or deployment is authorized by a test.

## Acceptance evidence ledger

| Requirement | Expected behavior | Implementation | Verification | Actual result | Status |
| --- | --- | --- | --- | --- | --- |
| 10.1 Provider boundary | Reuse real normalized evidence and validated observations; existing local behavior remains | Provider adapter + survey processing | Unit and HTTP fixture integration | Actual JPEG bytes via HTTP/HTTPS; saved API-primary survey generated proposals and draft PDF/DXF | Verified |
| 10.2 Invalid output and timeout | Reject malformed/unsupported results, bound transport, retain evidence and retry state | Provider adapter | Negative fixture tests | Malformed JSON rejected; real5second timeout repaired; TLS/redirect failures rejected | Verified |
| 10.3 Idempotency | One retained source result for the same revision/input; no duplicate acceptance | Persistent request/attempt records | Retry/restart/concurrency tests | Successful replay consumes no second quota; changed inputs and stale results rejected | Verified |
| 10.4 Private credentials | Operator-owned aliases; no keys in browser, database config, audit or errors | Registry + adapters | Canary-key negative tests | Canary secrets absent from browser/DB config/audit/errors; actual HTTPS credential redirects rejected | Verified |
| 11.1 Integrated settings | Real company settings available through existing administration shell | Settings views/form/template | Authenticated browser save/reload | 30 real authenticated browser checks passed at1920/1366/390; settings save/reload persisted | Verified |
| 11.2 Company/role boundary | Own-company Admin or platform configuration owner; current authority rechecked | Settings service/views | Cross-company, inactive/revoked and CSRF tests | Foreign/inactive/locked/current-role/CSRF checks denied writes | Verified |
| 11.3 Persistence and conflict | Explicit settings version; stale save rejected; useful errors | Settings service | HTTP unit/integration/browser | Stale version returns409 with input preserved; omitted checkboxes persist asFalse | Verified |
| 11.4 Redacted audit | Record allowlisted configuration changes without secret values | Governance audit | Saved audit inspection | Audit redaction passed; AI1Low before/after detail gap remains unfixed pending approval | Verified |
| 12.1 Routing and consent | Local default preserved; configured API requires explicit evidence consent | Router/policy | Local/API fixture tests | API-primary works with local disabled; external evidence consent required; unconfigured local path preserved | Verified |
| 12.2 Quotas | Durable company/day reservations; bounded attempts and retry accounting | Router/request records | Exhaustion/isolation/retry/concurrency | Zero/exhausted quota prevents transport; company isolation and failed/replayed attempt accounting checked | Verified |
| 12.3 Recorded fallback | Explicit opt-in; retain outcome, reason and provider identity | Router/attempt records | Primary failure + fallback fixture | Real disabled-local to HTTPS fallback recorded2attempts/quota2; replay did not repeat chat | Verified |
| 12.4 Actual workflow | Saved survey jobs use settings without losing source/template/revision or human approvals | Pipeline integration | Saved Django records and output regression | Saved survey processed actual HTTPS images into source findings/proposals and real draft PDF/DXF; human answers unchanged | Verified |
| 12.5 Outbound-worker policy | Do not silently bypass configured routing through a legacy PC worker | Remote-worker integration | Claim/lease policy tests | Legacy PC policy bypass prevented; configured API worker claims remote-enabled projects. PC-mediated fallback unsupported and disclosed | Verified |
| Regression | Existing jobs, inspection and approval controls remain | Existing stack | Full backend + frontend/system checks | Hosted Windows1465passed;Linux1463passed+2Windows-onlyskips;local1464passed+1existingWinError1314;19frontend+8checks passed on frozen bytes | Verified |
| Independent QA | Test actual behavior and failure cases separately | Agency QA | Independent tests + real browser | 18 ordinary independent,30browser,5explicit HTTPS cases passed; see independent QA report | Verified |
| Separate AppSec | Attempt to break completed feature; report severity, evidence and recommendations | Agency security review | Post-functional isolated review | 11new isolated security tests passed; separate TLS rerun passed; AI1Low remains approval-held | Verified |
| Native/provider acceptance | Real configured service and credentials, vision accuracy and target hardware | External environment | Explicit permitted benchmark | No external service or credentials selected for this phase | Blocked |

The alternative API protocol is an operator-registered HTTPS Ollama-compatible
service, not a promise of universal vendor API compatibility. No OpenAI-specific
adapter, key provisioning, paid fallback or public Ollama exposure is implied.
Ordinary tests use isolated databases/media and controlled providers. They must
not be described as native AI or live commercial-provider verification.

Existing A12/BR1/D1/D2/L1/CS1/CS2 findings retain their recorded approval status.
New post-completion security findings must be reported before any repair.
