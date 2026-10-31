# Independent AI Settings and processing QA — 31 October 2026

## Result and boundaries

The independently exercised settings, bounded routing and saved-survey fixture
flows passed the checks below. This is **not production, native-model accuracy or
paid-provider acceptance**. Real customer databases, uploads and approvals were
not used or modified. No model download, native Ollama call or paid API request
was made. Existing approval-held security findings were not repaired by QA.

Worktree: `.local/b5`, branch `feat/ai-settings-routing-20261031`. Read `AGENTS.md`,
`docs/LOCAL_CODEX_HANDOFF.md`, `docs/development/DEVELOPMENT_RULES.md` and installed
Agency profiles `testing/testing-reality-checker.md` and `testing/testing-api-tester.md`.
The independent reviewer owned only `core/test_ai_settings_independent.py`, private
QA harnesses and this evidence report/screenshots. Backend/UI implementation was
performed by other agents. This functional QA precedes the separate security review.

## Exact executed commands and results

Commands ran from the feature worktree using the existing interpreter:

```text
F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe scripts\run_backend_tests.py core.test_survey_evidence core.test_remote_survey_worker --verbosity 1
F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe scripts\run_backend_tests.py core.test_ai_settings_independent --verbosity 2
node .local\ai-settings-20261031\qa\browser.cjs
```

| Check | Actual result | Scope |
| --- | --- | --- |
| Existing extraction/remote-worker baseline | 54 passed, 35.552 seconds; zero external network attempts; 30 in-process HTTP fixture connections | Reproduction baseline, overlaps affected/full suite |
| First independent settings RED | 11 errors because new routes were unavailable | Executed before interface integration; raw receipt retained |
| Meaningful timeout RED | 1 failed in 7.356 seconds: configured local timeout of 5 seconds still accepted the response after 7 seconds | Revealed an actual transport setting defect |
| Final independent unit/HTTP/provider checks | 18 passed, 7.048 seconds; zero failures/errors/skips; zero external network attempts; 9 in-process fixture connections | Includes timeout repair and saved-record assertions |
| Actual Edge/Chromium browser | 30 checks passed at 1920×1080, 1366×768 and 390×844 | Real Django records, session cookies, CSRF and rendered forms |
| Explicit private HTTPS integration | 5 passed, 4.267 seconds; zero external network attempts; 16 fixture connections | Includes saved survey and actual PDF/DXF rendering |

The explicit HTTPS tests were run separately, with process-local `PYTHONPATH`
pointing to `.local/ai-settings-20261031/qa`:

```text
F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe scripts\run_backend_tests.py tls_fixture_tests.TLSProviderIntegrationTests tls_fixture_tests.TLSFullSavedSurveyTests --verbosity 2
```

This private integration module deliberately requires a generated synthetic
certificate/key beside it and is **not an ordinary automated-test dependency**.
Ordinary tracked tests do not depend on that untracked certificate, a user model,
the operational database, external network access or a previous test execution.
The five private HTTPS checks are separate from the ordinary suite; do not add
overlapping baseline/focused counts to present a larger unique test total.

## Behaviors independently checked

- Reading an unconfigured company does not create settings; response is no-store.
- Save/reload uses the correct company and persists configured values. Replaying
  an old version returns 409 and cannot overwrite a confirmed newer save.
- Unchecked enabled/consent/fallback values remain false. Invalid numeric/model
  fields, unknown ownership POST fields and missing external consent are rejected
  without partially creating a settings record.
- Current company Admin scope, all operational reviewer roles, inactive accounts,
  missing Admin industry eligibility, foreign companies and real-session CSRF are
  checked against actual persisted users. Owner company chooser is functional.
- The page and audits do not disclose server connection URLs or credential
  environment names. Only configured alias names are visible. No real key exists
  in the fixture.
- A synthetic image is normalized to actual JPEG content, received by the local
  HTTP `/api/chat` fixture and parsed/validated through the real extraction code.
  Source ID/hash remain correct, verification remains `needs_review` and the
  checklist's human answers remain unchanged.
- Completed execution replay does not call the provider or charge quota twice.
  An active same-source execution cannot reserve a second attempt. Changed input
  cannot reuse a completed receipt. Malformed model JSON does not become a result.
  An expired lease cannot publish a late result.
- The configured local timeout actually interrupts a deliberately delayed HTTP
  response. The completed source/result is not falsely reported after timeout.

## Real HTTPS and full saved-survey check

The explicit HTTPS fixture ran a real loopback TLS server and used the production
HTTPS transport. A process-local verified SSL context trusted **only the generated
fixture CA**; hostname checking and `CERT_REQUIRED` remained enabled. No machine
trust store, production TLS verification or provider code was relaxed.

1. Actual image bytes and a synthetic Bearer credential reached the HTTPS server.
   Completed replay caused one chat request and one quota unit.
2. The same fixture certificate without the deliberate test trust was rejected
   before any HTTP request/result. A 307 redirect was not followed with credentials.
3. Disabled local inference fell back to the explicitly consented HTTPS route:
   receipts recorded local/failed then https_ollama/succeeded, quota was two and
   replay did not repeat the chat request.
4. A real saved checklist-required survey containing two synthetic originals was
   submitted, queued and processed by `process_next(configured_providers=True)`
   with host local inference disabled and the project's remote-worker flag enabled.
   Two actual HTTPS image requests produced two persisted source analyses and one
   checklist proposal package. The job reached `ready_for_review`. Repeated submit
   reused the revision; a second worker pass found no duplicate work.
5. The real drawing renderer produced a readable PDF, auditable DXF and PNG preview.
   No rendering/inference result function was mocked in this flow. Original human
   answers were unchanged and the drawing edition remained unreleased.

The fixture intentionally returned no verified equipment dimensions. The resulting
sheet is a **Draft—For Review, Not to Scale drawing register** listing missing
supported geometry, rather than fabricated installation drawings. PDF text and
DXF audit were checked, and the PNG was visually inspected for readable layout.

Safe sample artifacts:

- [Synthetic PDF](samples/ai-settings-20261031/synthetic-https-survey.pdf)
- [Synthetic DXF](samples/ai-settings-20261031/sv-001.dxf)
- [Rendered preview](samples/ai-settings-20261031/sv-001.png)
- [Sample provenance summary](samples/ai-settings-20261031/manifest-summary.json)

## Browser evidence and repairs

Screenshots were captured from the real application and visually inspected:

- [1920 desktop](screenshots/ai-settings-20261031/ai-settings-1920.png)
- [1366 desktop](screenshots/ai-settings-20261031/ai-settings-1366.png)
- [390 mobile](screenshots/ai-settings-20261031/ai-settings-390.png)
- [Platform-owner chooser](screenshots/ai-settings-20261031/ai-settings-owner.png)
- [Consent validation](screenshots/ai-settings-20261031/ai-settings-consent-error.png)

Browser checks covered actual CSRF-protected save/refresh, two-tab stale conflicts,
input preservation, invalid limits, evidence consent, checkbox clearing, labels,
viewport overflow, foreign-company denial and the owner chooser. There were zero
JavaScript exceptions and zero unexpected failed requests. **90 external asset
requests were deliberately aborted** for the offline fixture and remain recorded;
94 console error messages comprised those resource failures plus four expected
negative HTTP responses. This is not proof of complete external-asset availability.
The existing narrow-screen app navigation remains horizontally scrollable.

Read-only SQL verification of the disposable browser DB confirmed exactly one
configuration (company A, enabled false, daily limit 84, version 3), exactly three
successful settings audits and no configuration created for company B.

The first browser harness run accidentally reloaded a failed POST and therefore
resubmitted its invalid fields. The harness was corrected to use the real
**Reload saved settings** link, and rerun on a fresh isolated database. Its failed
receipt and earlier fixture DB were preserved. Initial fixture construction also
needed an explicit Django `Client`; this was a QA harness correction, not an app
defect. Delayed HTTP fixtures narrowly ignore only expected client disconnects
after a timeout; unexpected response-write failures still raise.

The independently found product defect was the local timeout not being passed to
transport. Backend repaired it before freeze, and the same meaningful test passed.
No tests were weakened or skipped to obtain the result.

## Limits and next gates

- No native Ollama generation/vision accuracy or commercial API was tested. The
  configured HTTPS implementation is an Ollama-compatible protocol adapter, not
  proof of OpenAI/Anthropic or arbitrary provider compatibility.
- Real provider credentials, approved external evidence transfer, network
  availability, target-VPS/PC routing and service capacity remain operational gates.
- No customer records, engineering approvals or operational migrations were changed.
- This report does not replace the final full regression receipt or separate
  security review. Earlier security findings remain subject to owner approval.
- Private detailed receipts, synthetic cookies, fixture keys and databases remain
  under `.local/ai-settings-20261031/qa` and are not published with this report.
