# Separate post-functional company-boundary security review

28 October 2026. This phase started after the final15-test independent HTTP suite
and64-check actual saved-data browser journey passed. The reviewer read the
installed Agency Application Security Engineer definition, re-read task04 and
attacked the implemented boundaries using fresh isolated records. No product
implementation or permission-policy change was made during this phase.

## Executed attempts

`audit_company_attacks.CompanyBoundaryAttackTests`: **5/5 passed in0.750s**,
zero external network attempts. Private command/receipt is
`.local/company-boundaries-20261028/qa/separate-security.log`.

1. Real authenticated companyA roles obtained valid CSRF cookies through the
   application. Foreign retry/upload-session/document mutations still received
   authorization denials, not CSRF-only errors. Foreign events, job status,
   original bytes and source analyses remained unchanged.
2. Forged company/project headers, query values and a company cookie did not
   switch the tenant. The same sessions could still read own-company evidence.
3. Revoked membership, a changed stored company and an inactive account each
   removed file access from an already authenticated session. A stale primary
   pointer did not restore a revoked grant.
4. An unbound legacy machine credential returned403, remained unbound and did
   not claim work. Current user affiliation was not used to guess its historic
   tenant or rewrite the credential.
5. Authorized parent IDs combined with another company's photo/document/output
   IDs returned404 without exposing the foreign bytes.

Independent functional evidence also covers a valid released companyB Client
control and reverse companyB-to-A denials for all five operational roles. Source
hashes are retained with the functional receipt; the lead owns the final complete
integration gate.

## Findings, severity and recommendations

**No new exploitable company-boundary issue was established within the executed
scenarios.** No new security remediation was applied after this review.

**Informational — routing dependency:** legacy Django ModelAdmin registrations
are not evidence of a live global admin surface: both actual URL configurations
retire those URLs. Staff users with model permissions were tested against the
real routes and could not use them to read foreign records or mutate data.
Keep the regression and do not re-enable `admin.site.urls` without an explicit
tenant-aware administration design/review. No hypothetical route was mounted to
claim an existing vulnerability.

**Verification limits:** this was not exhaustive concurrency/fuzzing, hostile
upload-content review, database-admin compromise, production DAST, deployed
Nginx/TLS or real-device testing. Only current supported profile text fields were
tested; nonexistent avatar/certificate-upload endpoints were not invented.
Current Nginx source denies direct media but its actual server behavior was not
executed on this Windows PC. Server deployment and network/storage policy remain
their own operational checks.

Older approval-held findings, including BR1 and unrelated dependency/ACL items,
were neither fixed nor implicitly approved by this task. All synthetic data and
private tokens stayed isolated; no live customer record, worker or model was
used for an attack or approval test.
