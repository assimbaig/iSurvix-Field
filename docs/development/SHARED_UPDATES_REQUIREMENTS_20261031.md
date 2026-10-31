# Shared release and customer updates: tasks19-21

Owner authorised these tasks on31 October2026 during the approved CP1/CP2
repair. Continue existing application and package work; do not deploy, merge or
publish an owner-approved release automatically. The existing security and
licence holds remain explicit.

| ID | Expected behavior | Implementation location | Verification method | Actual result | Status |
| --- | --- | --- | --- | --- | --- |
| 19.1 | One exact source and immutable image identity for both editions | deploy/release_gate.py; shared-release-candidate.yml | Real manifest/image/proof binding and actual consumer | Actual final41228944697 succeeded; sharedartifact13052619886 and real consumer verified;12gate tests passed | Verified |
| 19.2 | Failed, missing, stale or foreign checks block draft candidate | Shared gate and exact-head CI | Unit/HTTP plus actual failed/positive CI | 12gate and separate10security checks passed; earlier failed Linux jobs blocked gated output; actual final all4workflows and positive shared gate passed | Verified |
| 19.3 | Traceable provenance; integrity distinct from authenticity | Shared record and customer manifest | Exact SHA/run/attempt/artifact checks; real updater consumer | Producer path regression RED then12GREEN;14bounded final security checks passed(overlap); final hosted sharedartifact13052619886 passed real consumer | Verified |
| 20.1 | Authenticated persistent owner-only Update Center | update_models/service/views/urls.py;0057;update_center.html | Unit/HTTP and actual saved browser | 22developer;47independent saved-browser assertions at1920/1366/390; role/CSRF/stale/replay checks passed | Verified |
| 20.2 | Validate package/support and fresh authorised maintenance | customer.py;updater.py;update_bridge | Invalid packages and revoked/withdrawn/stale requests | 26updater tests;50independent checks(overlap); actual latest6f5 Linux update and full/shared gates passed | Verified |
| 20.3 | Verified backup and safe failed/interrupted updates | Host updater; existing backup/restore | Actual Docker failure/interruption/recovery/success/replay | Linux41228944635 at6f5 passed374rows/73tables and original hashes; full/shared gates passed | Verified |
| 20.4 | Web never receives host Docker socket or private journal | compose.updates.yaml; host-only CLI | Configuration and separate AppSec review | Only catalog/receipts mounted readonly; separate12Update Center+14final security checks passed(overlap); no new finding established | Verified |
| 21.1 | Only explicit exact tested version pair supported | supported-upgrades.json; release record | Actual clean/migration matrix and incompatible-pair tests | e37b280(schema0057) to6f5 actual CI passed; earlier0056 unsupported | Verified |
| 21.2 | Recover failed/interrupted updates with source retained | updater.py;verify_updates.sh | Actual caught migration failure and hard interruption | Both rolled_back at6f5 with verified old-release TLS health; candidate/backup kept | Verified |
| 21.3 | Retain originals, answers, revisions and decisions | upgrade_fixture.py readonly retention proof | Source/target table digests and source-file hashes | 6f5 actual CI retained374rows/73tables/digest; main3595files/70tables unchanged | Verified |
| QA | TDD, unit/integration, independent QA and separate AppSec | Tracked tests; Agency QA/AppSec reports | Frozen source full regression; desktop/mobile; Linux | All4exact6f5 workflows passed; Windows1611pass/Linux1609pass+2existingWindows-onlyskips;19frontendpass; local WinError1314 disclosed | Verified |
| Target | Customer target and exact release acceptance | Owner/operator | Approved real target/physical LAN and release decision | No approved target/second physical LAN device, licensing or exact release approval supplied | Blocked |

First package target remains Linux/amd64 Docker/Compose. Offline application
updates require pre-transferred trusted package/images and preinstalled platform
prerequisites. No model downloads, public Ollama, paid service, production update,
automatic engineering approval or deletion of historical records is authorised.
A checks-passed candidate is not a licence grant or production release approval.

Final verification source6f5f40d2b7e296e626636c700b85547f95bcd6be. All four workflows passed; shared artifact13052619886 was produced only after the same-source gates and actual customer-consumer validation. Later documentation commits are separate from this immutable tested candidate. Earlier8security holds and owner licensing/target approval remain; a Verified code row is not deployment approval.
