# Task05 platform-owner and customer-administrator separation

Owner: Dot. Phase1 Company access. Original acceptance:
**Role tests reject privilege escalation. Audit privileged changes.**

Feature branch `feat/platform-customer-admin-20261028`, worktree `.local/b2`,
parent `d7f63ad` (Task04). Use existing Super Admin and Admin roles; no new role,
product module, audit database, approval policy or operational rollout is added.

| Check | Expected behavior | Implementation/owner | Verification | Status |
| --- | --- | --- | --- | --- |
| 05.1 Authority definition | Platform owner is current valid Super Admin; customer Admin remains company/industry/project scoped. Document existing administrative exceptions. | Backend permission owner; policy definition | Actual route/role matrix, authorized positive controls | In progress |
| 05.2 Escalation rejection | Customer Admin cannot promote/invite Admin or Super Admin, set global flags/permissions, rebind administrative scope or control protected accounts. | Governance guards and existing forms | Executed unit/valid-CSRF HTTP RED/GREEN with stored-state checks | In progress |
| 05.3 Operational separation | Platform owner cannot create operational projects/Clients or record engineering approvals; existing allowed non-Client account administration remains. | Existing role guards retained | Platform positive administration and negative operations | In progress |
| 05.4 Invitation safety | Accepted roles/flags/company come from valid stored invitation and current issuer authority; protected overrides cannot create elevated accounts. | Governance invitation lifecycle | Invalid fields, valid acceptance and Admin owner-assignment before-state tests | In progress |
| 05.5 Scope/revocation | Self/peer Admin/foreign-company changes and stale authority cannot bypass current account/project restrictions. | Existing Task04 guards plus scoped administrative checks | Independent role/session/forged-input cases | In progress |
| 05.6 Durable audit | Existing events gain persisted actor, target, scope and allowlisted before/after states; legacy actions/details/history remain readable. | Audit helper and governance integration | Unit/HTTP snapshots, actual browser and SQLite readback | In progress |
| 05.7 Safe snapshots | No passwords, hashes, tokens, sessions or raw requests in the new envelope; snapshots are detached, typed and alias-aware. | Audit helper owner | Sensitive-field rejection, fresh identity, immutable-data and alias tests | In progress |
| 05.8 Atomicity | Privileged mutations roll back if audit persistence fails; no false success or unaudited privilege change. | Existing transactions plus integration | Forced audit failure with unchanged stored state | In progress |
| 05.9 Existing audit controls | Append-only audit content, actor attribution and scoped audit visibility remain intact. | Existing audit model/routes reused | Existing integrity suite and foreign-log denial | In progress |
| 05.10 Independent review | Review original acceptance, verify six-role desktop/mobile behavior, then separate adversarial security review. | Independent Agency Reality Checker/AppSec | Saved-data browser/HTTP attacks, findings report | In progress |
| 05.11 Delivery/preservation | Full checks on frozen source; update ledger; preserve data, source history and review-only delivery. | Lead | Final receipts and checkpoint comparison | In progress |

## Policy and compatibility

The existing safe compatibility behavior for a customer operational invitation's
posted `admin_industry` remains: that unsupported value is ignored and cannot
change the server-bound issuer/project industry. This is not permission to rebind
industry; the actual administrative industry endpoint remains platform-only.
Global privilege/company override fields are rejected on covered administrative
actions. Do not claim the earlier ignored global flags were actually applied.

Earlier global industry updates already have richer before-state audit data;
those events remain intact. Engineering review/approval histories are not replaced
by the new administrative envelope. The helper captures state and does not itself
authorize changes or create duplicate events.

The role/account owner alone edits shared governance endpoints. The audit owner
edits the new helper and its own tests. Independent QA edits only its test module
and isolated fixtures/reports. Lead owns the acceptance ledger and integration.

Recovery checkpoint:
`.local/backups/project-checkpoint-20261028-230610-platform-customer-admin`.
It has fresh SQLite/source/Git proof and all3595 protected files rehashed against
the complete task02-verified archive215901. Operational source/schema remain
`fd365f1`/core0053; feature parent includes Task04 migration0054, still unapplied
to operational data. This task adds no further schema migration. Existing A12,
BR1/D1/D2/L1 findings retain their approval status; do not repair them by inference.
