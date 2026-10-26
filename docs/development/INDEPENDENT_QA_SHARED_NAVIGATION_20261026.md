# Independent authenticated browser review: shared header

26 October 2026. Executed by the separate Agency AppSec reviewer after the header
worker reported its files stable. This is actual authenticated browser evidence,
separate from the implementation worker's synthetic CSS geometry checks.

Source: shared `workspace_navigation.css`, `_primary_navigation.html`, the base
stylesheet token, and their integration with the final QA workspace. No product
file was changed by this reviewer. The G1 closure is separately documented in
`SECURITY_REVIEW_QA_GENERAL_GALLERY_20261026.md`.

## Executed matrix

The previously used8921 service was not listening at inspection time. A consistent
read-only SQLite backup of its explicitly synthetic fixture and a private media
copy were created under `.local/security-qa-general-gallery-20261026`. An owned
loopback8924 server served only those copied records/media; original8000/8001
apps and the11435 model worker were untouched. Existing synthetic role sessions
were copied without printing credentials. Native model calls were explicitly
blocked in the copied server and none was attempted.

Playwright/Edge visited **36 authenticated pages and passed144/144 assertions**:

- QA: My reviews, Projects & sites, Overview, Review activity, Reports, a saved
  site and Profile at1366px and390px:14 page visits.
- Engineer, Team Lead, Client, Admin and Super Admin: Home and Profile at1366px
  and390px:20 page visits.
- Representative QA My reviews and Admin Home at1024px:two page visits.

Each visit checked HTTP200 and the exact permitted role link set; one visible
header with all navigation links contained and no page-level horizontal
overflow; correct single/current QA location and no active Profile link; and
same-origin generated link destinations. QA had five direct links without the
old hidden More menu. **Zero browser console errors** occurred. External
resources, native-AI endpoints and all non-GET/HEAD requests were blocked;216
resource requests were blocked by this deliberate browser policy. No task,
link, answer, rejection or approval action was performed.

Receipts: `header-browser.cjs`, `header-browser.json`,
`header-browser-summary.json` and synthetic header screenshots in the private
directory. The copied fixture/server setup is `header_server.py`. The owned
test server was stopped after execution; `header-server-cleanup.json` records
that no model-call attempt log exists.

Three new independent template-security tests plus six existing shared-header
tests passed **9/9 in0.867 seconds**, native exit0. They compare all six roles'
link text/destinations with the committed baseline, inject hostile industry and
project query values to check tag/attribute/external-origin escape, and ensure
unknown/Profile locations do not claim an active review/admin section. Receipt:
`header-template-tests.log`; isolated databases/media and zero external attempts.

## Functional issue found by manual screenshot inspection

The144 assertions test navigation containment and page overflow, not collision
between individual header controls. Manual inspection of
`header-admin-1024.png` found the project dropdown overlapping the Reviews/Help
area at1024px. The QA390px screenshot was contained. This functional observation
was sent to the owner and header worker; it is **not an established AppSec
authorization bypass**, and no product fix was made by the reviewer.

Until the header worker's repair is independently retested, do not describe
144/144 as proof that every header control is visually correct. This limitation
is material despite the existing matrix being green. Final hashes at initial
execution are in the private `final-source-hashes.json`; follow-up results, if
any, must identify the later source and preserve this initial observation.

No new security finding was established in the stable header source. Promoting
existing links changes their visibility rather than their role/project access
checks. Existing held findings remain unchanged, and this focused review does
not authorize deployment.

## Functional collision repair and independent final recheck

The header worker repaired the authorized functional layout issue, without any
security-policy change: selects now fit their labels, tablet headers wrap into
two rows at981–1240px, and the stylesheet token is `shared-header-3`. Original
screenshots/receipts remain retained as evidence of the issue the first automated
matrix missed.

Restarted only the owned copied-fixture server on8924 and independently executed
**ten final authenticated page visits with60/60 assertions, zero console errors**:

- All six roles' Home/My reviews headers at1024px.
- The actual compact QA saved-site header at1024px.
- QA My reviews, saved-site and Profile at390px.

These final assertions include pairwise rectangle intersections between visible
module/project selects, Reviews links, Help summaries and user summaries, plus
select-within-label bounds. **No control collisions remain in the tested pages.**
Exact role links, current/Profile state, same-origin destinations, direct QA
navigation, visible contained links and no page overflow also passed. This is a
targeted post-repair matrix; the original36-page matrix and its144 assertions
remain identified separately rather than being presented as one immutable
post-repair run.

Final evidence: `header-final-browser.cjs`, `header-final-browser.json`,
`header-final-browser-summary.json`, `final-header-*.png`. Manual inspection of
the final actual Admin1024 and QA saved-site390 screenshots confirms the formerly
overlapping controls now have separate rows/space. The initial connection-refused
attempt occurred before the owned server finished starting; the final matrix was
run after its loopback listener was verified ready.

The final server was stopped; `header-final-cleanup.json` records owned PIDs and
no model-call attempts.8000/8001/11435 listeners remained running and untouched.
Final hashes are in `final-source-hashes.json`; the earlier hash set is preserved
as `pre-header-collision-fix-hashes.json`.

**Functional overlap status: resolved for the tested responsive cases. No new
AppSec finding was established.** The independently owner-approved G1 closure
and earlier finding holds remain exactly as documented in the security report.
