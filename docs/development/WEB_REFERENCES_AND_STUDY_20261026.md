# Public references and compact completed AI studies

26 October 2026. This extends the compact QA/sketch checkpoint in
`QA_COMPACT_TAGGING_SKETCH_20261026.md`, on the same feature branch and draft PR20.

## Behaviour and boundaries

QA photo preview → AI details now includes compact site/photo context above a
semantic finding table. Real site ID, capture date/time, numeric coordinates,
uploaded category and photo ID precede product/type, manufacturer, model,
defects, recorded value/unit, description, quote, matching reason, uncertainty
and source confidence. Missing values remain explicit; numeric zero is retained.
Multiple findings remain selectable. Uploaded names and source bytes are unchanged.

Three compact indicators distinguish source analysis, finding extraction and
checklist tagging. Findings are extracted during image/document analysis; the
application does not invent a separate extraction job. The UI says so. Matching
shows durable saved-batch counts, not photo totals or an invented percentage:
the worker does not persist the planned number of mapping batches. Raw source
completion is not reported as completed checklist tagging. Category source
assignments are not moved by a progress display.

Within AI details, expand **Web references**, type public equipment keywords,
choose a provider, then **Look up references**. No automatic photo, GPS, site ID,
review answer or local-model-context transmission occurs. Only the explicit
keywords go to a fixed provider endpoint. The visible warning tells users not to
enter confidential data. Returned titles, excerpts, source links and retrieval
time are labelled external, unverified references. They never become survey
findings, answers, dimensions, links or approvals automatically.

Default **Wikipedia encyclopedia references** works anonymously and is not
labelled general internet search. Full web search has a Brave adapter but requires
an owner-provided `BRAVE_SEARCH_API_KEY` in the server environment. No key was
found; no account, payment, paid request or signup was performed. Missing keys
produce an explicit configuration error. No additional AI service is introduced.

Provider requests have TLS verification, fixed hosts, redirects disabled,
connect/read timeouts, a 256 KiB response bound and five-result limit. Requests
use the existing installed `requests` dependency, now declared directly.
The authenticated POST checks assigned QA, project access, CSRF and current
submission identity. Query/body limits apply; HTML snippets become plain text.
Per-user cache and limits use Django's configured cache; with local-memory cache
they are per process, not a distributed spend cap. Duplicate calls are guarded.
Browser errors retain the explicit query and offer retry; changing photos
discards late responses. Reviewer drafts are not overwritten.

## Completed-study presentation

**Completed AI study** is reachable from Engineer task information, QA More tools
and evidence navigation. It uses the same site/context/finding table format
beside a protected source image, with one photo and one finding per page.
No mutation, matching-confirmation or approval form appears there. Incomplete
studies have an honest pending message. Stored analysis digests are verified.

Engineer, assigned QA, Team Lead and company Admin use existing project/site
access restrictions. Client access additionally retains current-revision,
QA-completion and matching released-output requirements; it displays only
accepted, linked information in the same table format. **Raw private QA AI
proposals are not shared with clients by this presentation change.** Super Admin
remains administrative and receives no operational-record bypass. The existing
QA review endpoint still refuses Engineer AI-editing access.

## Reproductions and initial verification

TDD first failed on missing keyword lookup, then missing table/phase behaviour.
The completed-study HTTP tests first failed on the missing route; a subsequent
corrupt-analysis test reproduced an unhandled exception, repaired with the
existing guarded-response mechanism. No frozen record was edited to implement
the feature. Fixtures use isolated database/media and explicit synthetic outputs.

Focused combined backend command:

```powershell
& 'F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe' scripts/run_backend_tests.py core.test_completed_ai_study core.test_web_references core.test_qa_review_progress core.test_qa_review_progress_routes core.test_qa_matching_backend core.test_survey_checklist_mapping --verbosity 1
```

82 tests passed in15.814s, zero external attempts. Frontend scripts add11 web
lookup checks and10 finding/stage checks, alongside existing47 workspace and58
guided checks. These are deterministic behaviour checks, not native inference.

Native Wikipedia verification succeeded using actual TLS-verified requests and
synthetic public keywords. Independent QA also used the actual saved-fixture
Django endpoint in a browser: `microwave antenna`, HTTP200,1776 bytes,946ms,
real source citations and no operational mutation. Brave live verification is
blocked by the missing key. No Ollama call was made in this follow-up.

Final checks after the last functional and approved security repair:
**1,110 backend tests passed in396.350s**, no failures/errors/skips; isolated
database/media/model cache, zero external attempts and33 in-process HTTP-fixture
connections. All ten frontend scripts, Django check, migration-drift check,
dependency check and JS syntax passed. The static build copied215 files.
Product source stayed unchanged throughout the final checks; fingerprint:
`6cf48c3883c704aaea316604cbc4ccc74d5e22c886a6e80aa054f76079eae58c`.
Exact commands/results: `QA_FOLLOWUP_ACCEPTANCE_20261026.json` and private
`.local/qa-followup-20261026/final-acceptance/` logs.

Independent new-feature QA passed155 browser assertions,9 HTTP guards and29
focused backend tests. This is additional to the earlier52 compact/sketch
browser checks. Cases include actual native Wikipedia, deliberately controlled
provider failures, saved-data role/refresh/pagination, desktop/mobile, WS1
service/rendered-anchor/click retests and actual-schema defect observations.
All460 fixture originals, source rows and immutable revision remained unchanged.
See `INDEPENDENT_QA_WEB_STUDY_20261026.md` for evidence and limits. Both earlier
full runs are retained privately; one intentionally overlapped new RED tests and
another preceded the last schema-display fix, so neither is labelled final.

Implementation commit: `b1e49a1`. The final documentation receipt is committed
separately. Recovery archive and consistent SQLite backup are under
`F:\iSurvix\iSurvix-Field\.local\backups\project-checkpoint-20261026-145256`;
the final Git bundle supplements its pre-remediation source archive. Local
review8001 serves the verified source; original8000 and workers are untouched.

Functional schema review additionally reproduced a display defect: current
validated AI observations identify defects with `category: defect` and recorded
notes, rather than a separate `defects` property. Both compact viewers now show
those recorded details in the defect row. A valid Pydantic observation failed
before the repair and passed after; ordinary equipment notes do not become
defects. Optional manufacturer/model properties from legacy records remain
supported, while absent properties stay unrecorded. No new extraction schema or
model inference was introduced for the table.

## Owner-approved WS1 repair

The separate security review reproduced five obfuscated local-address web-link
bypasses. The owner explicitly approved fixing WS1. Backend and frontend were
repaired with executed failing tests first. Links now require ordinary ASCII
DNS authorities, HTTP(S), default ports, no user credentials, no local suffixes,
no ambiguous encoded host or IP literal. This deliberately rejects public IP
literal links too; normal manufacturer domain links remain supported. Cached
pre-fix results use a different namespace and cannot bypass the repaired filter.

Independent security re-attack blocked all five original cases plus26 additional
unsafe forms and retained five valid public links. Actual renderer tests create
no unsafe anchors. Final private security probes13/13 passed after also checking
the valid-schema defect fallback and hostile text. This is syntactic URL
validation, not a certification of external websites, DNS or remote redirects.
The review did not establish server-side SSRF; server search endpoints remain
fixed and do not fetch result URLs. See `SECURITY_REVIEW_WEB_STUDY_20261026.md`.
Older C1/M1/W1/S1/S2/S3/R1/R2 findings remain outside this WS1 approval and unmodified.

## Provider documentation

- [MediaWiki anonymous page-search example](https://www.mediawiki.org/wiki/API:REST_API/Reference/Sample_code:Search_pages/en).
- [Brave API setup and credential requirements](https://api-dashboard.search.brave.com/documentation/quickstart).

## Starting and reviewing locally

The already-running review candidate is `http://127.0.0.1:8001/login/`, with the
existing local credentials, shared local records/media and separate cookies.
Only this web preview was restarted to load the new code. Original8000 and its
in-flight workers were left running. No production deployment occurred.

For a normal Windows checkout, after reviewing/merging the feature yourself:

```powershell
Set-Location -LiteralPath 'F:\iSurvix\iSurvix-Field'
.\Start-iSurvix.ps1
```

The launcher manages the established workers. If manually operating an already
configured installation instead, use separate terminals and do not create a
duplicate worker accidentally:

```powershell
Set-Location -LiteralPath 'F:\iSurvix\iSurvix-Field\backend'
$env:DJANGO_SETTINGS_MODULE='checklist.settings_local'
& '..\.local\venv\Scripts\python.exe' manage.py runserver 127.0.0.1:8000 --noreload
# Separate terminal, same directory/settings:
& '..\.local\venv\Scripts\python.exe' manage.py survey_processing_worker
```

The current machine's standard Ollama11434 had native HTTP500 failures in the
preceding batch; the already-configured signed project runtime11435 succeeded.
Do not override a working runtime or restart in-flight processing merely to
review these UI changes. No model downloads are needed for web references.
