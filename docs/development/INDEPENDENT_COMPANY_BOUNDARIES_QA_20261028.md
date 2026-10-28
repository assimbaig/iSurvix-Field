# Independent company-boundary QA - 28 October 2026

Scope: task04, “Prove company A cannot access company B records, files or jobs.”
The reviewer read the installed Agency Reality Checker and Application Security
Engineer definitions, repository rules and current handoff. Product implementation
was owned by separate agents; this reviewer owns tests, private fixtures and these
reports only.

## Executed result

- **15 independent unit/HTTP tests passed in5.342s** after final implementation
  freeze. The six changed product/migration file hashes remained unchanged.
- **64 actual Django/browser checks passed** across companyA's Admin, Team Lead,
  QA Engineer, Engineer and Client; additional **3 released-client controls** and
  **20 reverse companyB-to-A controls passed**. These checks overlap the HTTP
  coverage; they are not unique requirements or a production certification.
- Separate post-functional AppSec then ran **5 adversarial tests, all passed
  in0.750s**. Its findings and limits are in the separate security report.
- Ordinary tests used the established isolated backend runner: no external
  network attempts, no operational database/media, and no native inference.

Private receipts: `.local/company-boundaries-20261028/qa/independent-final-functional.json`
and log, `browser-results.json`, `client-release-control.json`,
`reverse-controls.json`, `separate-security.log` and `teardown.json`.

## Actual coverage

| Surface | Positive control | Company-boundary negative control |
| --- | --- | --- |
| Task records, search, counts and CSV | Own task present and exported | Foreign site/project absent; foreign search yields0 result rows; selected foreign IDs cannot enter exports |
| Surveys and saved processing progress | Authorized own-company records remain usable | All five companyA roles denied foreign checklist, activity, photo state and saved-job progress |
| Photo originals/previews | Authorized roles receive exact stored bytes; reverse companyB controls also checked | Foreign parent IDs and nested foreign photo IDs denied; direct `/media/` paths denied |
| Documents and draft PDF/DXF/preview/ZIP | Engineer/Admin/Team Lead receive own stored bytes | CompanyB document/output IDs denied, including IDs paired with an authorized companyA parent |
| Client evidence | CompanyB Client receives its own final legacy photo bytes200; companyA Client gets404 for that same photo | Both source records are final, so a pending-release denial does not mask the company check |
| Checklist drafts and branding | Owning Admin edits/exports its private draft and reads its logo | Other company Admin receives404; intentionally shared published standard stays accessible |
| Project reclassification | Existing initial/legacy setup is covered by implementation tests | A project-bound private published checklist cannot become companyB-visible through reclassification, even before activity history |
| Professional profiles and qualifications | Eligible same-company Client/Admin/QA reads published Engineer experience | Other company's published profile returns404 and is absent from the directory |
| Machine jobs and evidence inputs | Explicitly scoped credentials claim their own job and download its actual normalized input | Other company's lease/input/result actions denied; an old companyA token cannot follow a reassigned issuer/project into future companyB work |
| Retired Django administration | Platform administration remains governed | Giving an ordinary company user staff/model permissions does not mount the retired admin site; actual mutation routes return410 |
| Super Admin | Global platform company metadata remains available | Operational checklist, processing state and evidence still denied, preserving administration-only policy |

Both synthetic employer companies use the same industry and approved template;
industry/template identity therefore cannot substitute for a tenant boundary.
The fixtures preserve other legitimate links, saved source bytes and workflow
state during denied requests. Current WorkProfile/ProfessionalExperience models
contain text qualifications, not avatar/certificate-upload FileFields; no such
file capability or test was invented.

## Independent RED evidence and corrections

Before the relevant fixes, an actual HTTP request with an old companyA machine
token claimed a new companyB job after trusted issuer/project reclassification.
The regression does not assert a particular field implementation; it asserts that
foreign work stays queued and unavailable. `stale-worker-red.log` preserves the
failure. The final test passes with the immutable issuing-company boundary.

The private-template reclassification case separately reproduced302 where409
was required. `bound-template-classification-red.log` preserves it; the final
test proves the original company and private-template visibility remain intact.
These are pre-acceptance functional reproductions, not findings silently fixed
after the separate security review.

Initial test-fixture corrections used a real PDF instead of invalid fake PDF
bytes, checked search result rows rather than the user's reflected search text,
sent a valid worker version handshake before testing authorization, and used a
workbook-compatible private-draft schema. Product code was not changed to make
those fixture mistakes pass. Original source-backed byte/hash assertions remain.

## Actual browser evidence and limits

The reviewer used a real isolated Django server on loopback8940, a fresh fixture
SQLite database/media and valid Django-generated test sessions. This tests saved
data, AuthenticationMiddleware and permissions, not frontend demonstration
storage. It does not claim a new password-login or engineering-approval journey.
Controlled legacy-final fixture state establishes the released Client control.

The browser exercised task navigation, project choices, search, CSV, authorized
file bytes, foreign records/files/job progress and direct-media denial. Admin/QA
were checked at1366px and390px. No JavaScript errors, failed local requests or
whole-page phone overflow occurred. External CDN font/bootstrap/leaflet requests
were deliberately blocked and logged separately. Screenshots:

- `company-a-admin-1366.png`, `company-a-admin-390.png`
- `company-a-quality_engineer-1366.png`, `company-a-quality_engineer-390.png`

These synthetic images are published in
`screenshots/company-boundaries-20261028/` beside this report; private originals
and browser receipts are retained for review. This is not actual-device, VPS, TLS or proxy acceptance.
The existing Nginx example denies all `/media` routes; no native nginx executable
was available here, so no deployed Nginx result is claimed.

After verification only owned server PIDs30188/17764 and port8940 were stopped.
The original loopback model14996/11434 and other services were untouched. No
runtime/model download, operational approval, original evidence rewrite or
operational migration was performed. The lead's final full-suite receipt is
separate; this report does not turn the older Windows symlink-fixture limitation
into a passing assertion or close native A12.
