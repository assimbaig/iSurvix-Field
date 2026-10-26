# Engineer and QA resume, 26 October 2026

Feature branch: `feat/qa-photo-candidate-ranking-20261024`. Saved checkpoints `6cef00c` and `206733b` remain retained; Engineer changes were integrated as `db1803a`. GitHub base `042e8de` is the owner's PR19 merge and has the same application tree as `42cf64b`. Fetching did not overwrite local files. No schema or dependency change is required.

## Behavior

- Engineer home shows Total assigned scope, Pending for submission and Rejected pending for response. Linked assignment/checklist pairs count once. Each card opens the existing project-filtered tasks. The local assistant remains under Help when available.
- Ordinary QA point remarks are optional. Explicit evidence-policy attestations and final rejection/reopening requirements remain. Evidence links, accepted answers and workflow approval remain separate.
- AI retains ranked approved-checklist candidates, chosen matches, alternatives, reasons and explicit unmatched outcomes. The model-selected supported target precedes retrieval alternatives. Similarity is relative support, never calibrated probability.
- Supported image facts propose checklist answers with source references and uncertainty. An inspection remains unanswered until human review. Photo relevance can suggest a location without generating pass/fail.
- The viewer shows a large image on the left and extracted observations, original-file details, ranked locations and current links on the right. Mobile stacks these areas. Existing zoom, pan, navigation, focus, selection and approved locks remain.
- Immutable results retain QA display aliases such as `SITEID_000001_short_title.png`. Original upload/download names, storage paths, hashes and bytes remain retained. Physical originals are not renamed. GPS alone cannot establish equipment azimuth, height or dish size; unsupported measurements remain missing.
- Compatible unchanged resubmissions reuse completed image observations and checklist mappings in a new retained revision. Exact source/template/model/context guards remain; human acceptance is not copied.

## Verification

Final isolated backend suite: **1,063 passed in324.758s**, zero failures/errors/skips, zero external network attempts;33 connections were to in-process fixtures. Source fingerprint: `57da3d20b8254aa285288f3278e6808051f172f00d9d1e203c4a99478a409b03`.

All eight frontend scripts passed. Behavior suites include40 QA workspace,58 guided-state,21 Engineer document and6 pause assertions. The four retained preview/routing scripts are static checks, not browser proof. Django check, migration-drift check, dependency check, JavaScript syntax and the214-file static build passed. Python3.12.10; Django6.1.2; Pillow10.4.0; openpyxl3.1.5; PyMuPDF2.0; ezdxf1.4.5; ReportLab5.0.1; Pydantic2.14.1.

Independent saved-data QA passed63 distinct browser checks using166 points and460 photos at1920x1080,1366x768 and390x844. Final18 Engineer-home and14 viewport assertions were also repeated. Independent56 focused backend tests passed. All460 disposable originals, hashes and source revisions were preserved. See [independent QA](INDEPENDENT_RESUME_QA_20261026.md).

The first full run had1063 tests and one failure: simplification hid the existing Engineer assistant link. Restoring it inside Help resolved the original capability assertion;10 focused assistant/home/role-boundary tests passed. The final full run follows this repair.

## Real local model evidence

Installed/configured `qwen3.5:4b` reports vision support. Standard loopback11434 returnedHTTP500 for a real image request. The existing signed project runtime was started with `scripts/Start-PhotoAI.ps1` on loopback11435. No model download occurred.

A real application-service image request extracted TestCo, RRU-X100 and48VDC from a synthetic label in41.162s. A separate isolated Engineer upload/submission was visible to QA while queued. Its native worker reached review in95.768s, proposed TestCo without acceptance, and generated draft outputs. QA saved ordinary remarks empty, returned the synthetic task, and Engineer resubmitted unchanged evidence. The next pass finished in0.998s with zero image and zero matching calls. Old source-analysis digests, original bytes/name/hash and the new revision's unaccepted state were checked.

Private receipts: `.local/resume-20261026/native-label-receipt.json` and `native-flow/receipt.json`. The native fixture retained draft PDF/DXF outputs in isolated media. These are synthetic integration checks, not real-site accuracy,500-photo speed or sustained-throughput benchmarks. No operational survey was submitted, returned or approved by these tests.

## Security gate

The separate Agency AppSec review passed9 of10 new probes and reproduced **M1 Low**: an empty high-confidence raw observation can acquire generated mapping text and appear as an AI-suggested link while its candidate outcome is unmatched. No human acceptance or approval bypass occurred. This criterion remains Failed. Owner approval is required before remediation; no fix was applied.

The reviewer also passed44 existing guard tests,4 assistant tests and16 Help role/capability combinations. Prior W1/S1/S2/S3/R1/R2 findings remain pending their approval process. See [security report](SECURITY_REVIEW_QA_MATCHING_20261026.md) and [acceptance ledger](RESUME_QA_AI_ACCEPTANCE_20261026.json). This candidate is not production security clearance.

## Windows startup

Use `Start-iSurvix.cmd` in the selected main checkout for the established GUI startup with retained local data and independent workers. Its generation check can select the existing dedicated11435 runtime. The current selected checkout must contain this candidate before using these instructions to test the changes.

Explicit application startup in PowerShell:

```powershell
Set-Location 'F:\iSurvix\iSurvix-Field\backend'
$env:DJANGO_SETTINGS_MODULE = 'checklist.settings_local'
$env:ISURVIX_AI_MODEL = 'qwen3.5:4b'
$env:ISURVIX_OLLAMA_URL = 'http://127.0.0.1:11435'
$env:ISURVIX_PHOTO_OLLAMA_URL = 'http://127.0.0.1:11435'
& '..\.local\venv\Scripts\python.exe' manage.py runserver 127.0.0.1:8000 --noreload
```

For the independent worker, use another PowerShell window with the same directory/environment:

```powershell
& '..\.local\venv\Scripts\python.exe' manage.py survey_processing_worker
```

The website remains usable when its worker is offline; jobs remain queued. A worker executes queued jobs, so destructive verification belongs only in isolated fixtures. No merge or production deployment was performed.

## Screenshots

All screenshot records are synthetic.

- [Engineer1366](screenshots/resume-20261026/engineer-home-1366.png)
- [Engineer mobile](screenshots/resume-20261026/engineer-home-mobile.png)
- [QA viewer1920](screenshots/resume-20261026/qa-viewer-1920.png)
- [QA viewer1366](screenshots/resume-20261026/qa-viewer-1366.png)
- [QA viewer mobile](screenshots/resume-20261026/qa-viewer-mobile.png)
- [Engineer Help](screenshots/resume-20261026/engineer-help-1366.png)
