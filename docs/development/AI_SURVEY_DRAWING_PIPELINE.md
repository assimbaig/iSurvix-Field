# Integrated survey checklist and drawing implementation

This feature extends saved Django `Checklist` surveys. It does not replace the
application or its QA / Team Lead / Client approval routes. It is opt-in through
the immutable published `ChecklistTemplate.checklist_required` setting and excludes
Telecom inspection and Construction inspection regardless of that setting.

## Records and boundaries

Additive migration 0045 creates private supporting documents, upload sessions,
immutable submission revisions, leased persistent jobs, immutable per-source
analyses, immutable checklist results, append-only review events and immutable
drawing sets. Migration 0046 adds an optional project-template company logo.
Existing templates default to opting out, and existing records are not rewritten.

The input digest covers the site/project, approved template and selected field
definitions, answers, remarks, intake, coordinates, assigned branding and every
source ID/original filename/hash. Published field definitions control the generated
checklist. Uploaded evidence cannot change a template. The unique checklist/digest
and checklist/revision constraints prevent repeated submissions from duplicating
jobs. Each revision has one persistent job. Completed outputs are not overwritten.

Submission requires the assigned Engineer, an editable survey, required intake
fields, evidence, an explicit uploads-finished confirmation and no open upload
session. Photo batch sessions span the complete sequence of 20-file requests,
including the gaps between requests. Direct batch uploads are also tracked.

The worker persists source results individually. It claims a timed database lease,
checks current user/project assignment, verifies original SHA256 bytes and model
vision capability, pins the model context, and uses the existing inference lease.
Restart recovery reclaims expired jobs. Busy inference requeues without discarding
work. Offline/invalid-model/invalid-response failures retain immutable inputs and
source checkpoints for explicit retry. No model download or external AI fallback
is performed.

## Evidence and checklist preparation

The evidence adapter processes one resized image per native Ollama request, with
a 1,280-pixel long edge. Photos, PDF page rasters, workbook embedded images and
image sketches send actual base64 image content. PDF text and bounded workbook
cell chunks accompany or supplement image processing. Originals remain unchanged.
Targeted image crops are supported by the adapter; the current workspace does not
include an interactive crop-authoring tool.

Strict Pydantic schemas constrain observations, units, source references and
confidence. Evidence text is untrusted data, never instructions. Uncalibrated
photo-derived geometric values are withheld. Even transcribed recorded dimensions
remain unverified until a human confirms the measured drawing record.

Small approved catalogs can accompany image analysis. Larger catalogs are ranked
in full using the existing local BGE embeddings, then mapped in text-only batches
of at most 12 observations and 40 candidate fields within 12,000 prompt characters.
Mapping never resends images. A missing local embedding cache uses an explicitly
identified lexical fallback, without downloading a model. Model and batch identities
are checked before reusing immutable mapping results. Explicitly unassigned findings
cannot be rebound by a later heuristic. Unsupported checklist items remain visible.

Accepted corrections are append-only. Raw observations remain immutable, and their
original values remain visible. Engineer completion explicitly applies valid reviewed
answers and photo links to the source checklist. An application receipt binds the
resulting source digest to the unchanged original submission. Subsequent independent
survey edits invalidate that binding. Missing and non-applicable dispositions never
bypass the original required-field/evidence rules. Existing manual/rejected photo
decisions are preserved. Existing submission URLs are gated against premature use.

## Drawing and release controls

`survey_drawings.py` builds versioned A3 paper-mm geometry. Both PDF and DXF consume
the identical ordered entities, layers and shared source references. Native DXF
blocks, dimension styles, line weights and readable text conventions are versioned.
The stored geometry includes the final rendered title block and its digest. Assigned
company/client/partner logos are copied into the portable output bundle.

Supported facts produce applicable layouts or evidence schedules. Sourced, explicitly
confirmed coordinates and units can produce measured diagrams. Missing categories
are identified in the register rather than invented. Raw AI findings never create
exact installation geometry, hidden electrical connectivity or manufacturer profiles.
Measured records are validated separately from model findings, including strict
finite numeric coordinates and explicit source membership. Each sheet is rasterized
for preview. Draft preparation uses atomic directory publication and file hashes.

Drawing release requires the Engineer endorsement, independent assigned QA approval
of the exact review digest, a different Team Lead, current inputs and completion of
the original survey route, including Client approval where required. Original file
hashes are rechecked. Corrections and QA returns invalidate prior package signatures.
Clients can download current released outputs only. Private document/source/output
routes recheck authentication and project/record scope, set private/no-store and
nosniff, and constrain output paths to media storage. File tampering fails closed.

## Start and verify

Use the normal Windows `Start-iSurvix.cmd` launcher. For a separately managed worker,
from the repository root in PowerShell:

```powershell
$env:DJANGO_SETTINGS_MODULE = 'checklist.settings_local'
$env:ISURVIX_PHOTO_OLLAMA_URL = 'http://127.0.0.1:11435'
& .local/venv/Scripts/python.exe backend/manage.py migrate
& .local/venv/Scripts/python.exe backend/manage.py survey_processing_worker
```

The selected Ollama endpoint must already be running and locally installed with
vision support. `--once` handles one available job. A single request processes one
image; 200+ images are queued as individually persisted bounded sources, not one
large GPU request. Logs remain in `.local/survey-processing-*.log`.

Focused checks:

```powershell
& .local/venv/Scripts/python.exe backend/manage.py test core.test_survey_evidence core.test_survey_processing core.test_survey_checklist_mapping core.test_survey_drawings core.test_survey_export_integration
& .local/venv/Scripts/python.exe backend/manage.py makemigrations --check --dry-run
& .local/venv/Scripts/python.exe backend/manage.py check
```

Dependencies tested in the local Python 3.12.10 environment include Django 6.1.2,
Pillow 10.4.0, openpyxl 3.1.5, PyMuPDF 2.0, ezdxf 1.4.5, ReportLab 5.0.1 and
Pydantic 2.14.1. Compatible drawing/document dependencies are in requirements.
Official interface references: [Ollama image/chat API](https://docs.ollama.com/api/chat),
[Pydantic JSON validation](https://pydantic.dev/docs/validation/latest/concepts/json/).

## Verification and limits

Tests cover 200 individual image payloads, PDF pages, workbook cells and embedded
images, model/disconnection/busy errors, invalid output, conflicting measurements,
permissions/CSRF, duplicate submissions, retry checkpoints and restart recovery,
published template preservation, checklist mapping and unassigned sources, typed
record corrections, source application, real three/four-layer survey routes, strict
geometry validation, genuine PDF/DXF/ZIP downloads, file tampering and retained drafts.
Browser checks use an isolated synthetic database at desktop and mobile widths.

The authorised Z93004 subset pilot used three real photos, actual native Ollama
inference and the 181-field checklist: 80.862 seconds through draft readiness and
21 extracted findings. Its original workbook fully validates: two sheets, three
bounded text sources and 247 embedded-image placements. Native workbook probes
analysed one actual cell-text source and one actual embedded image successfully.
No real approvals or releases were manufactured. Full analysis of all 378 site
photos and the complete workbook, field accuracy and sustained throughput remain
outstanding. Private customer artifacts stay in `.local/survey-drawings-task`.

Synthetic shareable outputs are in `samples/drawings`. They demonstrate generic
equipment envelopes and evidence schedules, not verified manufacturer/site drawings.
There is no manufacturer reference library, engineering calculation engine, CAD
design authoring system or compliance certification. Confidence is qualitative and
uncalibrated. The renderer bounds packages to 32 sheets / 20,000 entities; overflow
is flagged, with complete findings retained in the processing record. Video, old
XLS files, macros, external workbook relationships, OLE/ActiveX and encrypted PDFs
are unsupported. A named local PC and GPU benchmark is not an online deployment
or a guarantee of five fully verified photos per second. No merge or deployment is
part of this change.
