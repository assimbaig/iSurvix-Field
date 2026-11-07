# Account, email, release and Excel export delivery ledger

Candidate: V1.3 Beta, branch feat/account-email-exports-20261107. Baseline7414975 (mergedPR40), live17a699a. Root dirty branch preserved in place. No website source/PR43 changes belong to this work.

| ID | Expected behavior | Implementation | Verification | Status / actual result |
|---|---|---|---|---|
| B1 | Recoverable source/data checkpoint, isolated data | Established .local/save_project_checkpoint.py; short worktree .local/w44 | ZIP CRC, SQLite integrity, source/media hashes | In progress: checkpoint running; operational data not migrated |
| A1 | Registered account can self-reset without mailing a password | account_recovery* + existing mail worker | Real HTTP request/token/confirm, old password/session invalidation | In progress; independent failing baseline reproduced |
| A2 | Expiry, single use, stale tokens and rate limits | Persistent reset request/throttle | Unit/integration concurrent/replay/locked/inactive/missing account/CSRF | In progress |
| A3 | No account enumeration or uncontrolled redirect | Generic request result; fixed HTTPS origin | Existing vs missing/ambiguous account, malicious host/next | In progress |
| M1 | Actual invitation hooks queue once for onboarding/users | Existing invitation outbox | Real saved onboarding/invitation + duplicate/retry tests | In progress; live outboxes empty, no provider failure inferred |
| M2 | Specific role/company invitation with logo/signature/disclaimer | email_presentation + optional branded Graph rendering | Escaping/headers/delivery payload/private link preservation | In progress |
| M3 | Honest errors and background delivery, no duplicate uncertain sends | Existing durable email worker + reset queue | Unavailable/auth reject/invalid/busy/restart; no real recipient send | In progress |
| R1 | User popup contains version and bullet changes, no visible source/PR | release_notice + release_note_content | Real Django HTML and dismissal regression | In progress; original hash display reproduced |
| R2 | All future installed versions retained for platform owner only | InstalledRelease, login signal, registration command, /governance/releases/ | Persistence/replay/roles/no writes on GET | In progress; old releases are not fabricated |
| X1 | Standard XLSX for permitted operational sections | Explicit export catalog using existing access scopes | Real workbook contents, headers, date/time names | In progress |
| X2 | Durable background job and personal export history | DataExportJob, independent worker, My exports | Queued/running/completed/failed/retry/restart/concurrent | In progress |
| X3 | Company/project/role boundaries at request, generation and download | Actor-owned files + fresh scope checks | Foreign users/role change/revocation/approved output visibility | In progress |
| X4 | Safe bounded workbooks and retained file records | openpyxl safe cell strings, limits/TTL/private downloads | Formula injection, corruption/missing/expiry, no credentials/blobs | In progress |
| X5 | Useful export actions on existing screens and unified navigation | Existing tasks/projects/people/reports; My exports | Desktop/mobile actual saved data browser tests | Not started |
| D1 | Backward-compatible migrations and guarded upgrade preservation | Additive0065/0066/0067, reviewed upgrade helper | Actual upgrade/retained rows and evidence hashes/drift checks | Not started |
| Q1 | Full tests, UI and independent security attempt | Isolated backend runner + Agency QA/AppSec | Exact commands/counts/findings; new findings held for approval | In progress; red acceptance baseline recorded |

No feature is Verified until actual checks pass. No live deployment or merge is authorized by this implementation request. Do not claim delivery while external email or hosted checks are unexecuted. Customer exports are scoped spreadsheets, never the operational database backup. Limitations and unsupported sections must be explicit.

## Current executed evidence (7 November 2026)

- Recoverable checkpoint completed: .local/backups/project-checkpoint-20261107-120345. ZIP CRC verified. All82existingdatabase tables/rows match the checkpoint;3537mediafiles SHA256 matched; zero mismatches.
- Agency account/email focused193tests:191passed,2platformskips. Actual local HTTP OAuth+Graph fixtures exercised image-logo HTMLpayload and fresh source/recipient checks; no real email sent.
- Independent QA:10backendtests and90actualDjango browserchecks across7roles/2companies passed.25additionalnegative/securitychecks passed.
- Export32tests and41relatedupgrade/retentionchecks passed, including actual0064?0067 migration and rejection of unexpected schema/index/metadata changes.13catalogsections include reported inventories.
- Django checks, migration-driftcheck, staticcollection, Pythoncompile and pipcheck passed.24/24existingfrontend scripts passed with installed Edge (defaultChromiumbinaryabsent; no download performed).
- Fresh live Microsoft authentication passed withoutsending. Live outboxes contained no queued/failed records; this does not establish inboxdelivery or reproduce a current transport failure.
- Full backend regression is running; do not claim final complete-suite success until actual results are recorded.

## Approved AR-Q1 repair

AR-Q1 Medium was reproduced in disposable data: per-IP-denied recovery requests consumed the shared hourly request budget, temporarily denying recovery to unrelated users. The owner explicitly approved the fix on 7 November2026. Existing IP/account windows are now checked under the existing serialized transaction before the shared debit. No new local keys are allocated before shared admission, preserving bounded allocation (at most201 keys per global window; local windows can overlap). This repair does not authorize deployment or resolve the separate R01 recovery finding.

## Coverage boundaries

These are curated permission-scoped Excel exports, not raw operational database backups. No passwords/tokens/provider configuration/private support-repair data or original evidence blobs are included. Platform-owner exports remain administrative; Client exports respect sharing/release restrictions and exclude raw mutable inventories/internal review history. Older releases are not invented to populate history.

## Final review status before approval hold

- Full backend run2196tests:6skips; only2subcheck failures in the one AR-Q1 regression. No other failures in that run. It preceded the final AR-Q2 logging changes;50affectedchecks passed afterward.
- AR-Q2Medium was separately approved, fixed and independently verified using real configured file/console handlers and tracebacks. HTTP400/403/404, valid-link lifetime and useful errors remain intact.
- AR-Q1Medium subsequently received explicit owner approval and a targeted repair. The original failing regression is unchanged; admission regressions also cover rotating IPs, global exhaustion, expiry, generic responses and concurrent callers. Repeat the final complete suite and independent review against the repaired code before promotion; the historical failing result above is not a current green result.
- Existing navigation preserved; MyExports is in the account menu, with89additionaldesktop/mobile navigation/history checks passing across7roles.
- DraftPR44, no merge/deployment. PR42 documents separate recovery findingR01; this feature does not resolve it.
