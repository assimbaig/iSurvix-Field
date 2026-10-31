# Update Center and optional installer configuration: separate security review

31 October 2026. Independent Agency Application Security Engineer review after
the implementation lead's explicit functional freeze of this component.
Worktree `.local/b6`, branch `feat/customer-server-readiness-20261031`.

**Twelve independent checks passed. No new exploitable defect was established
in these tested UI/service/receipt/configuration boundaries. This is not approval
of the privileged updater or of a production/customer deployment.**

## Scope and independence

Read the actual update models/service/views/URLs, additive migration0057 and
model/URL entry points, root-local `update_bridge` management command, Update
Center template/owner-menu access, optional customer `prepare_runtime` inputs,
`_compose_base`, and `compose.updates.yaml`. Used repository rules, latest handoff
and installed Agency AppSec instructions. No product files or core tests were
edited by the reviewer.

The privileged updater's proxy-health functional repair was still in progress
and is **excluded** from this component verdict. Whole host stop/backup/migrate/
activate/recover behavior needs separate review after that source is frozen.
Earlier gate review and CP1/CP2 repair closure are distinct reports/evidence.

## Executed private checks

Process-local `PYTHONPATH=.local/customer-server-20261031/update-center-security`:

```text
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py center_security --verbosity 2
```

**12 passed in 0.795 seconds**, zero failures/errors/skips, zero external network
attempts and zero fixture HTTP connections. Eleven cases exercise real isolated
Django records/HTTP/service decisions; one examines the actual optional Compose
mount contract. The latter is configuration evidence, not a running Linux mount.

| Challenge | Verified result |
| --- | --- |
| Previously loaded owner becomes inactive; company Admin attempts POST | Current persisted authority denies creation; no update request inserted |
| Missing CSRF or extra command/status POST fields | Denied without creating an execution request |
| Repeated request key and attempted input rebinding | Same request retained once; changed target rejected |
| Invalid host receipt HMAC | State and sequence remain pending/zero |
| Signature from request domain reused as a receipt | Rejected by domain separation |
| Correctly signed receipt with different nonce, target or manifest digest | Rejected by immutable request bindings |
| Exact receipt replay versus altered already-used sequence | Replay is idempotent; changed content at the occupied sequence is rejected |
| Withdrawal before host verification ACK and ACK before withdrawal | First ordering rejects the old ACK; second ordering prevents withdrawal of verified work |
| Uncertain activation | Active-update lock remains occupied; another request is blocked until signed rollback names the actually running original release |
| Duplicate catalog keys or injected command/private content | Catalog becomes unavailable; no executable choice or raw private value is shown |
| Attempts to mutate/delete history or add arbitrary private receipt fields | Event immutability and strict receipt field allowlist reject them |
| Optional web-container inputs | Exactly catalog and receipt paths are read-only mounts; no Docker socket, privileged host journal or privileged mode is exposed by this override |

The withdrawal/ACK cases check both legal serialized orderings on the actual
service. They are not a multi-process race stress benchmark. Signed fixtures
use a synthetic test-only Django secret and do not inspect a deployment key.

Private receipts: `center_security.py`, `checks.log`, `receipt.json`,
`source-before.json` and `source-after.json` under the private review directory.
Eight scoped source hashes matched before/after the tests.

The first harness attempt did not initialize the reused fixture's test client;
the next static assertion accidentally matched a descriptive comment rather
than a mount. The reviewer corrected only that private harness setup and scoped
the assertion to actual mount lines. Those receipts remain as `harness-first.log`
and `harness-second.log`. No application behavior, core test or security
expectation was weakened to obtain the final result.

## Trust boundaries and limits

- The browser saves pending requests, not privileged commands. The trusted host
  operator/updater performs execution separately; this review did not execute it.
- The bridge's HMAC binds request/receipt purposes and immutable input IDs using
  the configured Django secret. It is an authenticated application/host bridge,
  not independent proof against a fully compromised web application or a host
  administrator. Trusted read-only catalog and scoped privileged execution remain
  essential to the later whole-integration review.
- Reconciliation accepts durable sequenced journal receipts rather than treating
  timestamp age alone as invalid; exact request nonce/signature/sequence and
  running-release checks protect the tested replay boundaries.
- Read-only mounts and safe path guards were inspected in the actual installer
  code. Native Linux permissions, symlink-race resistance against a hostile host,
  privileged ACK execution, physical devices, Docker networking and migration/
  rollback integrity were not newly proved by these tests.
- Actual same-source CI/package/upgrade results remain external execution gates.
  Their pending status cannot be replaced by this review or by mocked host calls.
- CP1/CP2 were explicitly approved and verified repaired in their separate tested
  scope. A12/BR1/D1/D2/L1/CS1/CS2/AI1 remain unchanged. No unrelated finding repair
  or release approval is implied.

No new security repair, native Ollama/OCR inference, paid API, external request,
Docker process, customer evidence edit, engineering decision, deployment or merge
was performed by this reviewer. Request a separate post-functional review of
the final privileged updater and assembled installation before claiming that
whole workflow verified.
