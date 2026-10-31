# Separate AppSec review: company onboarding

31 October 2026. Reviewer used the installed Agency AppSec Engineer profile,
repository development rules and original Task06 acceptance. Review executed
after independent functional browser completion:39 checks, two companies and
two actual Admin invitation acceptances. This reviewer made no product edits.

## Boundary and executed evidence

Controlled platform-owner intake -> human review -> company provisioning ->
existing company/industry-bound Admin invitation and acceptance. Existing
customer roles, project access and engineering approval policy remain controlling.
The public applicant portal, automated mail delivery and staging deployment are
not part of this implementation.

**12 separate adversarial tests passed**, zero failures/errors/skips,
0.612 seconds on the final source; zero external connections or native AI calls. Ordinary runner used
isolated database/media/model cache. Tests covered:

- Customer Admin, Engineer, QA, Team Lead and Client route/mutation denial.
- Forged role/company/status/invitation/global flags and mutation rebinding.
- CSRF and GET mutation rejection; foreign/null Origin rejection.
- Persisted name/review-note escaping and invalid UUID input.
- Fresh locked/inactive owner authority, even with cached actor objects.
- Existing account email conflicts; no silent attachment or rebinding.
- Invitation audit outage rolls back both invitation and application transition.
- Bearer response is private/no-store, absent from sessions/audits and not repeated
  by a retried invitation request.
- Invitation acceptance uses `Referrer-Policy: strict-origin`, which removes the
  URL path and bearer from both same-origin and cross-origin referrers. Same-origin
  browser completion was independently verified; foreign/null Origin is not allowed.
- Two concurrent attempts at each of intake, provisioning and invitation issuance.
  SQLite returned one successful writer and one busy writer for each stage.
  Serial retry then preserved one application, company, invitation and transition
  audit each. Busy errors are not counted as successful processing; the existing
  guarded HTTP write path provides retry rather than false success.

Command, from `.local/b3` with `PYTHONPATH` set to the private security directory:

```powershell
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' scripts/run_backend_tests.py security_assault.OnboardingSecurityAttacks security_assault.ConcurrentOnboardingAttacks --verbosity 2
```

Private evidence: `.local/company-onboarding-20261031/security/separate-security-final.log`
and `receipt.json`. The receipt records exact product hashes. The initial12-test
run passed before the final functional mobile-table/contrast repairs; the entire
12-test attack phase was repeated after those repairs and the independent visual
10/10 gate. Twelve of14 original onboarding hashes remained identical; the reviewed
CSS and list template changed as intended. The functional invitation Origin repair
in the existing governance view was separately included in the reviewed source
receipt. Private attack fixtures are not operational accounts or evidence.

## Findings and recommendations

**No new exploitable authorization, bearer-handling or duplicate-provisioning
vulnerability was established in the executed scope.** This is not universal
security certification. No finding was silently repaired after this review.

**Informational — invitation lifecycle handoff.** Application history retains the
original invitation ID. Expired/revoked/lost-link replacement uses existing
People and invitations management and does not silently regenerate the original
bearer on replay. This preserves replay safety, but an explicitly reissued invite
is managed through that existing workflow rather than automatically replacing
the application's recorded original invitation. Consider linking replacement
events for operational convenience in a separately approved change.

**Informational — controlled intake.** Only the platform owner records a received
application. There is no verified email ownership/public registration/rate-limited
public intake service added here. Share one-time invitations only through the
approved private channel. A future public intake flow needs its own authorization,
abuse-prevention and identity-verification design and review.

**Limits.** This is not deployed proxy/TLS validation, exhaustive fuzzing, database
administrator tamper resistance, PostgreSQL concurrency/load proof, cloud disaster
recovery or native AI accuracy/throughput testing. Concurrent tests exercised the
actual local SQLite service/transactions and retry invariants; they do not prove
unlimited sustained throughput. Root owns the full repository gate and preservation
checks. Existing A12/BR1/D1/D2/L1 and other approval-held findings remain under their
prior status; this review does not approve their repair. Any subsequent repair of
a security finding requires explicit owner approval under repository instructions.
