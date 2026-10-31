# Task06: controlled company onboarding

Active scope: Company access only. Cloud staging, provider settings and pilot
tasks were deferred when the owner narrowed this request. This feature is not
an operational deployment or public registration service.

## Behavior and implementation

The platform owner's existing Administration screen links to **Company
onboarding**. The compact paginated table opens received applications. Explicit
Apply, Review, Provision and Invite steps persist through refresh. Rejection
preserves the application and requires a reason; it cannot provision a company.

- `onboarding_models.py` and additive migration0055 store application UUID,
  normalized name, email, active industry, status, company, invitation and reviewer.
- `onboarding_service.py` serializes existing governance transactions, rechecks
  current authority, validates transitions, prevents replay duplicates and refuses
  to claim existing companies/accounts. Audit failure rolls back the mutation.
- `onboarding_views.py`, forms and routes expose controlled, authenticated,
  CSRF-protected owner actions. No public applicant portal or email service is added.
- Existing hashed `ProjectInvitation` and account acceptance create the Admin with
  its saved company/industry and no global flags, project or engineering approval.
- New compact templates/CSS reuse the application shell. The mobile applications
  table scrolls inside its own keyboard-accessible region; the page does not expand.

No survey, evidence association, approval policy or source original is modified.
Original application invitation IDs remain historical. Explicit replacement uses
existing People and invitations; it does not regenerate a bearer on replay.

## TDD, independent verification and defects repaired

Implementer tests were executed RED before the feature existed. Independent
saved-record tests also failed at the missing model before implementation, then
all12 passed. The final focused unit/integration gate passed66 tests, including
existing governance, permission and audit regressions. These counts overlap the
full repository suite and are not added to its total.

Actual Edge browser verification passed39 core checks: two applications, two
distinct provisioned companies, two actual invited Admin account creations,
replayed intake/provision/invite requests, refresh persistence and customer-role
denials. Readonly SQL confirmed correct company/industry bindings, no elevated
flags or automatic projects, and one audit per successful transition.

Browser verification exposed an existing invitation-acceptance failure:
`no-referrer` made browser form Origin opaque (`null`), which CSRF correctly
rejected. A meaningful failing policy regression was recorded; the acceptance
page now uses `strict-origin`, omitting the bearer path from referrers while
retaining a legitimate same-origin form Origin. Three new regression tests cover
policy/cache behavior, successful one-time acceptance and foreign/null rejection.
No CSRF exemption or trusted-null origin was introduced. An initial test fixture
omitted the required email; that fixture was corrected before the recorded
single-failure policy RED and product repair.

Visual review found four failing checks: CTA contrast1.363:1 at both widths and
unreadable mobile columns without internal scrolling. Scoped CTA text color,
minimum table/column widths and a focusable table region fixed these issues.
All10 unchanged visual checks then passed at1366 and390px; eight safe synthetic
screenshots are included under `screenshots/company-onboarding-20261031/`.

Separate final AppSec review executed12 attack tests, all passed, zero external
connections. Concurrent local SQLite attempts returned one success and one busy
result per stage; retries retained one application/company/invitation and one audit
per transition. This is not PostgreSQL or sustained load acceptance. No new
exploitable issue was established in that scope, and no security finding was
silently fixed after review. See the independent QA and security reports.

## Data and migration preservation

Fresh checkpoint165639 on31 October contains a consistent SQLite backup,
CRC-checked source archive and verified Git bundle. All3,595 protected files still
match the trusted recovery archive; all70 operational table digests match the
fresh checkpoint. Two pre-existing untracked audit reports are retained.

On a disposable database copy,0054+0055 forward and0055 reverse passed while all66
existing business tables stayed identical. Existing content types/permissions
were preserved; Django added one model content type and four permissions. These
metadata additions remain after reversal by Django design. The first comparison
incorrectly treated expected metadata additions as business changes; the corrected
rehearsal checks preservation of old metadata and the exact expected additions.
An interrupted rehearsal copy was retained, and the successful run used a fresh
v3 target. Neither issue established an application data-loss defect.

Operational code remainsfd365f1/schema0053. Neither0054 nor0055 was applied live.
Downgrading0055 drops the new application table; the rehearsal had no onboarding
history in that table. Preserve a backup and assess new application history before
any operational rollback. Original survey and approval tables were unchanged.

## Gate and delivery

Final full-suite results, source fingerprint, commands and delivery status are
recorded in `COMPANY_ONBOARDING_ACCEPTANCE_20261031.json` and the delivery ledger.
Earlier broad runs were interrupted/superseded after the real browser/visual
repairs; they are not counted as successful final runs. The final gate runs on the
repaired, frozen source. Private cookies, raw invitation bearers, isolated fixture
databases and test logs are not published.

Existing A12/native-model, Windows fixture and approval-held findings remain
separate. No model calls, downloads, cloud operation, merge or deployment occurred.
Phone results use browser viewport emulation, not a physical-device staging test.

## Final executed repository gate

Backend: **1350 run, 1349 passed, 0 failures, 1 errors, zero skips**, 464.660 seconds. The unchanged Windows symlink fixture returns WinError1314 before its assertion; the full suite is not green. All19 frontend scripts and Django/migration/dependency/syntax/static-build checks passed. No external service attempts occurred. Application source stayed unchanged throughout the final gate.

Fingerprint: `cd52a7411350228a4754b94f3020a23d174e84e67e01ee5bde4aadda1da7972a`. Exact commands/timings are in the acceptance JSON. Final draft delivery metadata follows in the ledger; no automatic merge/deployment.

## Review delivery

Implementation `148e2cb92ae6f11c9edd1b3f69401fd2cd355fe1`; [draft PR27](https://github.com/assimbaig/iSurvix-Field/pull/27), stacked after draft PR26. The unpublished branch was aligned with PR26; a recovery ref and byte-for-byte archive retained the pre-alignment source. All tested application bytes and the recorded fingerprint are unchanged. No published history was rewritten. Operational source/data remain untouched.
