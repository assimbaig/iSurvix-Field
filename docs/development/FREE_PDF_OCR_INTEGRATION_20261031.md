# Local PDF conversion and OCR

31 October 2026. This change integrates local tools into the existing survey
document intake, protected document preview, hand-sketch extraction and evidence
worker. It does not create a second application, change review permissions, or
approve engineering work.

## Tools and scope

| Tool | Installed version | Use | Upstream licence |
| --- | --- | --- | --- |
| [pypdf](https://github.com/py-pdf/pypdf) | 6.21.4 | Read-only structure and encryption preflight | BSD-3-Clause |
| [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) | 5.14.0 | Local PDF text extraction and bounded PNG rendering | BSD-3-Clause / Apache-2.0 wrapper; PDFium dependency notices also required |
| [RapidOCR](https://github.com/RapidAI/RapidOCR) (`rapidocr-onnxruntime`) | 1.4.4 | Local transcription of image-only PDF pages during worker analysis | Apache-2.0; preserve bundled engine/model notices |

No paid PDF/OCR service, API key, hosted converter, runtime download or OCR
fallback is used. The installed RapidOCR wheel supplies the three ONNX files;
missing files produce an explicit unavailable result rather than a download.
Existing vision analysis and company AI routing remain separate features.

**Remaining licence dependency:** `survey_drawings.py` still uses local PyMuPDF
for Unicode drawing text and drawing previews. That library is not a paid API,
but its AGPL/commercial distribution requirements remain an explicit release
gate. This work does not claim complete removal or redistribution clearance for
PyMuPDF or every transitive dependency.

## Data flow

1. Uploaded originals and saved SHA-256 values remain unchanged. PDF intake
   validates bytes, encryption and page count locally.
2. PDF pages retain existing document/page/part IDs. Digital text is extracted
   locally. Separate bounded images are used for previews, sketches and vision.
3. Preview requests and source extraction never start OCR. The durable evidence
   worker invokes OCR only for a PDF page without readable native text.
4. The worker sends actual normalized page-image content, the bounded transcript
   and the existing approved field catalog to the existing vision path.
5. OCR status, engine/version, source-text verification state, bounded readings,
   confidence and boxes are retained with that source result. Local and remote
   workers retain the same canonical report. Invalid or approval-shaped OCR
   reports are rejected. OCR confidence is never engineering acceptance.
6. Empty, unavailable, failed or truncated transcription is explicitly recorded.
   Original images remain available for human inspection. Long OCR readings are
   retained within the report bound even when prompt text is truncated.

PDF rendering is serialized because PDFium is not thread-safe. Bounds apply
before text or bitmap materialization: 30 MiB, 80 pages, 100 million square PDF
units per page, 240,000 extracted characters per page, and 24 million raster
pixels. Encrypted/corrupt/oversized files fail clearly. No forms environment,
PDF JavaScript execution or URL retrieval is enabled.

Protected preview authorization, source-hash verification, signed preview cache,
revision scopes and original download controls are preserved. Cache version 3
records the new renderer identity; existing originals are not rewritten. Worker
compatibility fingerprints include the converter and OCR helper implementations.

## Verification

Ordinary deterministic checks use isolated databases, media and model caches;
they must not launch native OCR inference or contact Ollama. The new tests create
real synthetic PDFs with ReportLab, actually convert those bytes, and exercise
the authenticated saved-document preview endpoint. Only the OCR/vision inference
boundary is controlled in ordinary worker tests. Separate native OCR checks use
synthetic evidence and the already installed bundled weights.

Run from the project root:

```powershell
& .local\venv\Scripts\python.exe scripts\run_backend_tests.py core.test_pdf_tools core.test_remote_survey_worker core.test_measurement_unit_worker_pin core.test_survey_evidence core.test_survey_processing core.test_engineer_documents core.test_document_repair_regressions core.test_qa_document_preview core.test_survey_sketches core.test_survey_sketch_integration --verbosity 1
```

When using the isolated B6 worktree, substitute the absolute shared virtualenv
path `F:\iSurvix\iSurvix-Field\.local\venv\Scripts\python.exe`.

TDD receipts are under private `.local/free-pdf-tools-20261031/`: initial missing
converter failures; preview/sketch legacy-import failures; worker OCR integration
failures; remote retention/version failures; and honest missing-engine/status
failures. Passing runs and a source fingerprint are recorded there. The final
150-test integration run passed in 29.670 seconds, with zero external connections
and 30 requests to controlled in-process HTTP fixtures. Independent review is
recorded separately by the delivery lead. Do not interpret this
subset as the full release gate or a real customer/engineering benchmark.

## Limitations

- OCR is uncertain transcription. Handwriting, unusual fonts, skew, spacing and
  low-resolution scans can require manual correction. It does not infer hidden
  geometry, compliance or precise dimensions from photographs.
- The new worker OCR hook targets image-only PDF pages. Existing digital PDF,
  photo, workbook and drawing behavior is otherwise preserved.
- OCR source details are retained after successful source analysis; a failed
  vision request remains a failed/retryable job, not a successful OCR completion.
- The isolated integration and native synthetic OCR checks do not establish a
  sustained throughput claim or customer-site accuracy.
- No operational records, original evidence, approvals or production jobs were
  edited by the verification runs. No service was deployed or merged.
