# Independent Update Center and retention QA — 31 October 2026

Scope: tasks20/21's saved Django Update Center and upgrade-retention fixture in
`.local/b6`, branch `feat/customer-server-readiness-20261031`. Repository rules,
handoff, original requirements and installed Agency QA profiles were read. The
reviewer did not implement the Update Center, styles, host updater or retention
helper and made no product-source edits. This report does not equate a signed
fixture receipt with a real privileged installation or recovery.

## Current independently executed results

- `core.test_update_center core.test_upgrade_retention`: **25passed in20.698s**,
  zero failures/errors/skips, zero external attempts or HTTP fixture connections.
- Fresh saved-data browser: **38/38passed**, covering authenticated owner requests,
  actual CSRF, persistence/replay, withdrawal, late/forged receipts and recovery
  state. Zero JavaScript exceptions, third-party requests or failed requests.
  One intentional customer-Admin403 was recorded, not hidden as a successful page.
- Additional actual mobile Save/Withdraw: **6/6passed** at390×844, including actual
  saved pending/cancelled states and unobstructed button click points.
- Existing mobile account menu → Update Center discovery/navigation: **3/3passed**.

The47browser assertions share the same isolated records. They are an independent
browser execution, separate from the backend agent's earlier22checks; they do
not represent47customers or a load benchmark. Unit/focused counts overlap full
regression execution and must not inflate its unique test total.

## Real browser scenario

The reviewer started a fresh isolated Django fixture on127.0.0.1:8973, using a new
private database/media directory, synthetic owner/Admin sessions and a synthetic
trusted catalog. Python-server outbound connections and third-party browser
destinations were blocked. No operational cookie, password, evidence or database
was copied. The environment's previously reported automatic-review problem did
not recur for this fixture startup or its executed checks.

1. Customer Admin GET was denied; the actual owner could discover the screen
   through the existing account menu and open the real route.
2. Save created exactly one pending request, not a host installation. Refresh and
   replaying the same submitted form retained one request/event.
3. Desktop1920×1080,1366×768 and mobile390×844 retained receipt/withdraw actions
   within the viewport without page-wide horizontal scrolling.
4. Pending withdrawal persisted cancellation and freed the next request slot.
   A late signed host verification could not undo the withdrawal or replace its
   occupied event sequence.
5. A second explicit request accepted a correctly signed verified receipt.
   Forged applying data showed a signature error and retained the prior state.
6. A valid applying receipt persisted. A signed completion naming the target was
   rejected because the fixture was still running the original release.
7. A signed interrupted phase retained the recovery lock and prevented another
   request. A subsequent correctly sequenced recovery receipt naming the running
   original release persisted `rolled_back` and released the lock.
8. Saved history/reload retained all five accepted events for that second request.
   A third request was saved and withdrawn using actual mobile clicks.

Read-only final SQLite inspection confirmed three requests: cancelled sequence1,
recovered sequence4, cancelled sequence1; nine retained events and zero active
requests. The original synthetic evidence bytes remained unchanged. Controlled
receipt files replaced during negative-case construction were copied aside,
preserving the failed fixture inputs. No actual Docker, migration activation or
rollback command was run by this browser scenario.

There is a small existing global Appearance-widget overlap at a mobile action's
left edge for some scroll positions. Both action centres remained unobstructed;
actual mobile Save and Withdraw worked. This is a cosmetic limitation, not a
blocked essential action. The reviewer made no unrelated/global widget changes.

Screenshots captured independently from the real interface:

- [1920desktop](screenshots/shared-updates-20261031/update-center-1920.png)
- [1366desktop](screenshots/shared-updates-20261031/update-center-1366.png)
- [390mobile](screenshots/shared-updates-20261031/update-center-390.png)
- [Recovery required](screenshots/shared-updates-20261031/update-center-recovery-required.png)
- [Actual mobile actions](screenshots/shared-updates-20261031/update-center-mobile-actions.png)

Private scripts/receipts live under `.local/customer-server-20261031/qa`:
`update_independent_fixture.py`, `update_independent_settings.py`,
`update_independent_browser.cjs`, `update-independent-browser-receipt.json`,
`update-mobile-action-receipt.json`, `update-navigation-receipt.json`,
`update-browser-persistence.json`, and `update-retention-independent.log`.
Only owned launcher61652/child50592 on8973 were stopped after the checks;
`update-server-stopped.json` records the shutdown. Other services were untouched.

## Retention-proof assessment

The helper inspected is `deploy/customer/upgrade_fixture.py`. Its seed is guarded
by the explicit disposable flag and a pristine synthetic-owner database. The
executed integration test creates an actual survey/template, three originals and
three previews, one PDF document, a manual evidence link, one immutable submission
revision, a queued AI job, a human remark and a governance event. A second seed or
non-disposable context is rejected. No engineering approval or native inference
is created by seeding.

The snapshot comparator checks old stable-primary-key rows and their values,
rejecting changed human answers, source hashes or deleted rows. Existing audit
rows remain identical while new audit rows may append. Authentication last_login,
sessions, migration tracking and maintenance-request/event tables have explicit
documented exclusions. Additive new tables are allowed. This is meaningful
retained-data evidence rather than merely a zero exit from `migrate`.

However, helper unit/integration tests alone are not a real supported-version
upgrade: actual old/new image execution, quiesced backup, failure recovery,
runtime activation and retained file/hash checks still require the privileged
tool tests and disposable Linux run. The seed does not cover every historical
approval/output state or prove a real customer database can be upgraded.

## Source reviewed and remaining gates

Source SHA256 values at this verification:

- `core/update_service.py`: `c364c5bfcd4329d312ff63855eff606ae2cd4d99facbbbff269fcb69c260076c`
- `core/update_views.py`: `a1055a2fe5564522c0e70c440bff33b198f94c599ff2c7c9289a7901d0d816c3`
- `templates/core/update_center.html`: `3fc89f20ccd23a40e0ae71b4f0bface216da0fbb11fbcb03aebfdbbc3eb4c11f`
- `deploy/customer/upgrade_fixture.py`: `53778021aae8c8aeb17e205a91fc765363b032c12c59088e7eeea82dd15d668e`

The previously reported CP2 quoted-YAML header case was independently rerun
against the final97b62369package repair: **one passed in0.626seconds**, zero
external requests. Separate AppSec closure and its broader checks are recorded
in the customer security report; this single repeat is not a universal secret scan.

Shared gate functional QA is in
[its separate report](SHARED_RELEASE_GATE_INDEPENDENT_QA_20261031.md). Independent
privileged host-tool countercases, separate phase6security review, final full
regression, actual Linux supported-pair/failure-recovery evidence, physical target
access and owner exact-release/licensing approval remain distinct gates. No merge,
deployment, real customer update, paid API or native Ollama call occurred here.
