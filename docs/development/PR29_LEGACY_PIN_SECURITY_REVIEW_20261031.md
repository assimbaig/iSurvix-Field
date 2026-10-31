# Separate security review: PR29 first-durable-pin repair

31 October 2026. Independent Agency Application Security Engineer. Scope:
`feat/ai-settings-routing-20261031` in `.local/b5`, delivery `40fe6d4` plus the
functional legacy-native-pin preservation repair. This review began after the
lead's explicit post-functional review instruction, following implementing-agent
235-test GREEN and independent QA 11+4 checks. Those counts are predecessor
evidence, not tests performed by this reviewer.

Read `AGENTS.md`, development rules, latest handoff, installed Agency AppSec
profile, `PR29_LEGACY_PIN_REVIEW_20261031.md`, and the actual changed service,
claim predicates, old/new tests and guide. The reviewer authored only private
countercase tests, receipts and this report. No product code or operational
records were changed, and no finding was repaired.

## Result

**No new exploitable defect was established in this bounded repair review.**
The first saved provider policy continues to take precedence over a digest that
resembles a native pin. With no provider policy, a persisted native pin prevents
later company settings from rebinding that revision. Model, credential and
project guards remain on the underlying worker paths. A malformed/mismatched
native digest fails the existing worker identity check; it does not gain API
quota bypass or permission to change saved evidence.

## Independently executed countercases

Six new private cases challenged:

1. Existing provider policy plus a forged native-looking digest and stale caller
   object cannot select the remote-native path or bypass a zero provider quota.
2. An empty stale object cannot hide a native pin now persisted in the database,
   create a company policy over it, or let mismatching worker identity claim it.
3. Native classification after company configuration does not relax the required
   worker model name.
4. A retained native pin does not allow a revoked scoped worker credential to
   retrieve another source.
5. A continuing native worker cannot return a source analysis from a different
   model after company configuration is enabled.
6. A saved provider-policy integrity mismatch is rejected rather than being
   reclassified as native processing.

The reviewer reran those six cases together with the previous eleven independent
AI-settings security regressions, including current-authority/company denials,
private credential/error handling, consent, pinned-registry changes, stale result
publication, quotas, immutability and the already-reported audit gap.

```text
# Process-local PYTHONPATH includes both private review directories.
F:/iSurvix/iSurvix-Field/.local/venv/Scripts/python.exe scripts/run_backend_tests.py pin_security security_review_tests --verbosity 2
```

**17 passed in 0.629 seconds**, zero failures/errors/skips, zero external network
attempts and zero fixture HTTP connections. These are isolated synthetic
database tests and controlled transport faults, not native inference or a real
commercial provider. Eleven cases overlap the previous private security suite;
they must not inflate the unique automated full-suite total.

The first six-case harness run had one test-assumption error: it expected a
zero-valued quota row after a rejected reservation, while the transaction correctly
rolled that row back entirely. The assertion was corrected to require no quota
row or charge; no application code or security assertion was weakened. The first
receipt is retained as `harness-first.log`.

Private evidence:

- `.local/ai-settings-20261031/pr29-legacy-security/pin_security.py`
- `focused.log`, `harness-first.log`, `receipt.json`
- `source-before.json` and `source-after.json`: five changed-file SHA256 values
  matched before and after review.

## Disposition and limits

Existing AI1 Low audit-detail gap remains confirmed and unfixed; the earlier
A12/BR1/D1/D2/L1/CS1/CS2 approval holds remain unchanged. No new finding requires
repair from this bounded review. This is not merge, deployment or public-release
approval and does not close existing security findings.

The reviewer did not run a full suite, live Ollama/API requests, paid inference,
external network probes, hostile multi-process database races, target VPS or
physical-device recovery. The lead must record the final integrated regression
and source identity separately. No customer evidence, credentials, engineering
decisions, original uploads or application services were modified.
