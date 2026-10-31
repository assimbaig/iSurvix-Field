# Customer-server offline UI verification - 31 October 2026

Implemented and verified for the recorded isolated cases. This is not approval
for customer deployment, native-model accuracy or a claim that every module works
offline. The installed Agency Frontend Developer and Reality Checker profiles
were read with AGENTS.md, the handoff and development rules.

## Change and scope

The existing shared layout automatically loaded Google Fonts, Font Awesome,
Bootstrap and Leaflet from third parties. Retained assignment/map includes also
loaded jQuery/Select2 and map-marker files remotely. These resources now ship
locally in `backend/static/vendor`, with source/version/SHA256/license inventory.
All five prior Bootstrap/Leaflet/Font Awesome SRI values match the vendored bytes.
Inter4.1 replaces the unversioned remote font request with original local font
bytes and a font-face declaration. The red marker uses an exact upstream commit.

Operational sign-in, task, profile, Engineer submission and QA pages use the same
branding and controls without requesting third-party browser assets. Saved map
coordinates/markers remain local. A retained legacy map contacts a tile service
only after **Load online basemap**; failed tiles show an honest unavailable state.
No authorization, approval, evidence model or AI service was changed.

## TDD and commands

New six-test RED: external-resource assertions failed across sign-in/role pages,
missing vendor inventory errored and the retained map lacked its explicit online
action. The initial live-server fixture also tried an unowned IPv6 loopback
address; pinning its host to127.0.0.1 corrected the harness without weakening the
runner's network isolation. RED is retained privately in `offline/red.log`.

From the feature checkout, using the existing interpreter:

```text
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py core.test_customer_offline core.test_shared_navigation core.test_role_designs --verbosity 1
```

**18 tests passed in3.223s**: six new unit/real-HTTP tests and12existing affected
regressions, zero failures/errors/skips/external attempts,12fixture connections.
The HTTP case retrieves actual styles/scripts from Django's local static handler;
manifest checks verify file bytes, copied notices and local CSS font/image paths.
These test counts overlap a later full suite and must not be added to it.

## Actual saved-record browser evidence

Private Playwright scripts used Edge with a real disposable Django database/media,
real session/CSRF login and production templates/JavaScript. The browser aborted
any third-party destination; the server rejected and recorded every outbound
connect attempt. The final operational scenarios produced **zero third-party
browser attempts and zero server outbound attempts**, rather than tolerating
failed CDN loads. Native telemetry was explicitly disabled in this fixture.

| Scenario | Passed checks |
| --- | --- |
| Actual Engineer login, three category uploads and Submit to QA |16|
| Six role workspaces, QA manual linking while AI queued, refresh and XLSX export;1920/1366/390 geometry |29|
| Stopped-process restart: revision, three source categories/photos, manual QA link, queued job and original byte checks |14|
| Actual section expansion, point selection, linked photo, enlarged viewer/zoom/Escape and selection preservation |9|

Total68operational browser assertions across these scenarios; scenarios share
records and some checks overlap. Zero JavaScript exceptions were recorded. The
first45also recorded zero failed resources/application HTTP responses.
The saved QA link did not accept any engineering item. The actual draft XLSX was
exported successfully. No final human approval or released output was created.

The whole fixture SQLite logical dump and all three original photo SHA256 values
matched across the successful stopped-process restart. SHA256:
`bba12eeb8ed1be471ca669fd1b554b424a6aebb0eaefdf0c14ea23285300525d`.

One initial restart probe exposed a **fixture-only** media-storage caching error:
the reused TestCase changed storage before the browser server assigned a persistent
MEDIA_ROOT. The harness was corrected using Django's override_settings signal,
a fresh database/media fixture was populated and all45main browser checks reran.
Only the fresh fixture is the restart proof. No product storage code was changed.
A scope assertion initially counted all unassigned photos while Other was selected;
it was corrected to verify one visible photo in each of Civil/Electrical/Tower.
The viewer harness also opens its normal collapsed section before selecting a
point. These harness failures were not silently treated as app successes.

A separate retained-map **component** check passed6assertions: one saved marker
and no external requests before an explicit online action; after the button click,
18deliberately blocked tile requests produced the unavailable notice and retained
its local marker. This component is not evidence of a reachable legacy route or
of online tile-service availability. Retired public Tailwind and development-only
preview font resources are excluded from the operational offline claim; the real
account-home route redirects to sign-in/governance and never renders that page.

## Preparation and license evidence

The connected preparation downloaded34browser asset/notice files, about3.3MB,
with no AI model. Python's HTTPS client lacked a local issuer; the explicit build
used Windows curl/Schannel with certificate verification retained, not an insecure
TLS bypass or trust-store edit. Sources and hashes are in the vendor manifest;
component notices and official references are in its README. This is not a legal
review or vulnerability clearance. Existing dependency/security approval holds
remain unchanged and unfixed.

## Limits and next acceptance

- This was controlled browser/server network denial, not disconnecting the PC's
  NIC or testing a second physical customer LAN device.
- Manual login/task/upload/QA/draft export cases were verified. Native offline
  inference needs installed, verified model files and separate accuracy tests.
- The existing photo-search/semantic helpers specify local_files_only; no model
  was downloaded or native Ollama generation invoked by this work.
- External basemaps/web references and configured remote AI require connectivity.
  Their live-service behavior was not certified by the disconnected fixture.
- Actual customer install, private DNS/TLS, physical browsers, client-only release
  access, deployment security and owner commercial approval remain separate gates.

Five safe synthetic screenshots are under
`screenshots/customer-offline-20261031`. They were visually inspected at desktop
and mobile widths. Unit/HTTP/browser raw logs, harnesses, restart receipts and
synthetic XLSX remain private under `.local/customer-server-20261031/offline`.
