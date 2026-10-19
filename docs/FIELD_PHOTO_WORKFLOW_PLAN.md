# Field photo workflow plan

Approved 17 October 2026. This extends the existing governed local app; no live site data, photos or approvals will be invented for testing.

Status: implemented, tested and applied locally. Final core suite passed all 186 tests
in 163.371 seconds. Native local vision tagged only the matching synthetic subject
after an over-tagging issue was detected and corrected. Live authenticated field and
bulk access checks passed. Additive migrations preserved old values in 29 existing
tables and all four media files. See the handoff for the runtime/checkpoint details.

## Intended user journey

1. Team Lead prepares site assignments in bulk. CSV rows contain the project, Engineer, site identifier, coordinates, task description and valid checklist general-information fields. A validated preview precedes an atomic commit. The assigned survey freezes its template and the supplied starting values.
2. Engineer opens a photo-first activity, confirms the preloaded site details and corrects permitted site-derived information. Existing system identifiers and approved sections remain protected.
3. Engineer chooses Civil, Electrical or Tower and selects the complete photo set for that group. The browser handles bounded upload batches. Original files and source metadata remain unchanged. Group labels guide the AI but do not prove what an image shows.
4. Local vision proposes the appropriate checklist section and field locations. Proposals retain source photo, model/job, explanation and uncertainty. No field answer, measurement or approval is silently overwritten.
5. Engineer reviews the proposed placements, confirms reviewed mappings together, or manually selects a better destination/photo for misleading evidence. Confirmed placements appear beside the checklist questions and in Excel exports without copying or discarding original evidence.
6. Coverage highlights required photos still missing and proposed or uncertain mappings needing review. Engineer can open a missing location, choose an existing photo manually or add another photo. A photo assigned to a field does not certify inspection completeness.
7. Engineer and Team Lead receive the current critical AI review of answers and recorded evidence. Corrections invalidate older reviews. Only Team Lead decides whether a current report is shared with Client. Submission and approval signatures remain unchanged.

## Implementation responsibilities

- Assignment backend: durable CSV preview, validation, commit and prefill provenance; site-information read/edit endpoint; single assignment prefill.
- Evidence backend: group metadata, durable vision placement proposals, manual/batch confirmation, coverage, and Engineer access to current AI review.
- Interface: mobile group upload, clear progress, source thumbnails, placement correction, missing-photo actions and final review; bulk assignment preview for Team Lead.
- Integration: checklist and Excel rendering, required-photo validation, combined regression, local migration/data-preservation checks and documentation.

## Acceptance and safeguards

Validate company/project/assignment permissions at each mutation; CSRF and approval locks remain. Reject malformed CSV, unknown checklist identifiers, stale previews and duplicate sites before creating assignments. Keep uncertain/unmatched photos visible. Verify installed model vision before image inference, use the existing durable worker and shared inference lease, and retain retry/interruption recovery. Tests use synthetic images and isolated records. Real-site accuracy and sustained bulk performance require field acceptance; no absence of findings is an inspection pass.

## Scope of this delivery

Bulk intake uses CSV rather than adding another spreadsheet dependency. Photo limits are now 400 per site, 20 per request, 5 MiB per file and 24 megapixels. The browser makes repeated bounded requests for a group. Required-photo coverage is based on the published checklist snapshot, not invented AI requirements. General photo suggestions remain distinguishable from confirmed evidence.

## Metadata-first performance revision

The approved performance target is a complete checklist with up to400 photos in at
most30minutes of background processing. The necessary average is4.5seconds/photo.
Extract a compact visual observation once per photo using the verified local vision
model and a reduced inference copy; keep the original unchanged. Persist observations
separately from original EXIF/technical metadata. A hash/model/prompt-version signature
invalidates stale caches. Never cache malformed or truncated output or results after
loss of the inference lease. A checklist revision reuses valid observations and rematches
all frozen field definitions without another image call. Matching is conservative lexical
retrieval, with explicit negative/generic evidence excluded; subtle detail and synonyms
can require manual assignment. Every resulting location remains unconfirmed, all answer
values null, and uncertainty high. Human approvals and Client-sharing gates remain.

Expose metadata extraction, checklist matching, saved completion and cache reuse in the
queue. Checkpoint each completed photo and resume remaining photos after interruption.
Final critical review consumes cached observations, with heavily photographed fields
split into bounded evidence chunks rather than dropping photos or exceeding a field limit.

First five actual-photo benchmark on this PC (RTX3060Ti/Ryzen7): cold12.890seconds,
then3.016/3.344/3.015/3.219seconds. Warm mean3.149seconds; cached rematching0-16ms.
This projects about21.2minutes for400 similar photos including one cold model load.
It is a projection for metadata and matching, not a measured400-photo maximum or a
guarantee covering final critical review, hardware contention and every image type.
Keep the30-minute end-to-end acceptance target open until a representative full run
including final review is measured; do not label a mock transport test as throughput.


## 19 October 2026 Compact metadata-first confirmation

The visible journey is now **Upload -> reusable image metadata -> suggested checklist links -> explicit human confirmation**. Upload continues through durable20-photo batches, preserving originals. Metadata is validated and cached by original hash, configured local vision model and metadata version. Checklist matching uses saved observations without another image call: field labels/descriptions provide subject anchors; section/type/upload group provide context only. Broad context, group names, unknown measurements and absent defects cannot establish image evidence. A strong unique candidate may carry medium advisory lexical strength; multiple candidates stay low/uncertain. These are suggestions, not calibrated confidence probabilities or approvals.

The compact page presents stage counts and a bounded20-photo review table beside the source viewer on wide screens. Each photo has one combined section/checklist-point dropdown. Engineers deliberately mark reviewed choices, then confirm them together in one action; the browser chunks at most100 mapping decisions per atomic request and reports any completed/remaining batches truthfully. Active processing pauses confirmation, and refreshed proposal fingerprints clear stale reviewed choices. Low-confidence and multiple-candidate locations require a deliberate choice. Other alternatives and all existing human links remain unchanged when a chosen location is confirmed; use Advanced links for explicit correction/removal. A photo can legitimately support multiple checklist points.

**Match saved metadata** queues existing metadata-ready photos for cheap checklist rematching through the same durable worker. It does not automatically reprocess the real site library. Job progress records matcher version and successfully matched photo IDs so older completed jobs are not falsely described as having used the new matcher. Cached metadata is retained; earlier human confirmation, manual placement, rejection, saved answers and approval signatures win over reruns. Missing/uncertain evidence and final AI review remain separate from the Engineer -> QE -> Team Lead -> optional Client workflow.


## 19 October 2026 AI Analysis review and survey details

The current visible flow is Upload -> AI Analysis -> suggested checklist links -> explicit confirmation. This supersedes the earlier table presentation: Needs matching shows two source tiles per page; Mismatched opens separate searchable checklist/photo tables with independent scrolling. Progress is actual current-batch worker progress; matched/mismatched/pending/human-confirmed source counts are distinct. No suggested link approves an answer.

Survey details draw unsaved defaults from the assigned account, actual project company and available photo capture facts. Existing answers, explicit clears, locks and frozen revisions win. Conflicts remain for manual review. During development all permitted details remain manually editable and profile completion does not block work. Before a future production release, require a complete professional identity and company assignment through the normal account workflow; this future gate is not enabled now. Site identity is assigned task context: an explicit photo label can be suggested/flagged but cannot silently move an existing record to a different site.


## 19 October 2026 Stronger evidence matching research (not yet activated)

Current confirmed/manual photo links and saved findings are retained. The existing matcher merges subject labels and procedural descriptions into a single overlap denominator. This excluded the sign candidate (1/11 terms) and weakened tower/ladder (2/11) even though the tower matches both label subjects. Current literal visible-text observations are not part of positive matching anchors. Research receipt: development/STRONGER_EVIDENCE_MATCHING_RESEARCH.json. Private preserved source/observation/link/answer snapshot: .local/research/confirmed-findings-20261019.json.

Recommended sequence: (1) reviewed per-checkpoint evidence requirements and subject-first rules; (2) literal OCR/QR support for authoritative identity matching; (3) cached semantic retrieval and shortlist reranking; (4) targeted existing local vision verification for ambiguous cases only; (5) evidence-quality/context checks and explicit engineering acceptance requirements. Optional later object grounding can show relevant component regions but does not establish physical acceptance. No new service, package, model, rule or template change was activated during this research.

Photo relevance, evidence sufficiency and inspection pass/fail are three distinct judgments. A sign with a readable Site ID supports the identification checkpoint; a tower and ladder support that subject. Neither establishes a passed condition. GPS/time support context only; missing facts remain unknown and synthetic development coordinates cannot validate site location. A photo may legitimately support multiple points. Exact IDs require the authoritative namespace/alias mapping; do not arbitrarily select between the sign's numeric ID and alphanumeric code or replace assigned site identity. QR content is untrusted data, never instructions or an automatic external URL request. Measurements need actual units/readings/approved criteria; no image-only guessed value. Human decisions remain authoritative and retained.

An in-memory illustration requiring sign+explicit Site ID label, or tower+ladder, found the two intended candidates without cross-links; three synthetic context/negative/instruction-like examples abstained. This is only a2-positive/3-negative feasibility probe, not a domain accuracy validation. No inference, live mapping writes or reanalysis occurred. Evaluation must compare methods on the same independently labelled holdout sites/photos, report false/missed links and abstentions, preserve all human links/rejections/answers/approvals and measure actual400-photo end-to-end throughput. The30-minute target remains unqualified.

Primary references: [OpenCV QR detector](https://docs.opencv.org/4.13.0/de/dc3/classcv_1_1QRCodeDetector.html), [PaddleOCR](https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html), [semantic retrieve/rerank](https://sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html), [Ollama vision](https://docs.ollama.com/capabilities/vision), [Ollama structured output](https://docs.ollama.com/capabilities/structured-outputs), [Grounding DINO](https://huggingface.co/docs/transformers/model_doc/grounding-dino). These sources establish available methods, not accuracy/speed on this application's field photographs.


## 19 October 2026 Shared, versioned evidence analysis and controlled learning

Implemented the researched operational rules: subject-first checkpoint retrieval with contradiction/negation guards; strict optional evidence requirements per published template field; local RapidOCR text extraction with region/confidence provenance; local OpenCV QR decoding without following payload URLs; original capture-time/GPS context and blur/resolution indicators; local BGE semantic retrieval; bounded verification of ambiguous candidates using the existing vision-capable Ollama model. Numeric answers, measurements, N/A, inspection pass/fail and workflow approvals remain human-controlled. The optional later object-grounding model was not introduced.

New immutable evidence records are scoped to company/project/activity/site/source hash/frozen schema, actual model-file digest, tool/source/model-weight fingerprints, prompt/rule versions and explicitly adopted correction release. Source bytes and saved payload integrity are checked. Observations are reused across rule updates; unchanged complete assessments are reused without more inference. All authorized operational users receive the same saved findings. Historical observations are archived, not represented as digest-verified new results. The saved-analysis panel distinguishes historical versions; the evidence JSON report carries provenance. Independent submission snapshots bind saved evidence provenance.

Human photo confirmation, manual reassignment and rejection now capture pending correction examples. A different assigned QA Engineer or Team Lead must review an example. Publication creates an immutable project release, and applying it is explicit. Exact-source corrections affect suggestions only; similar-photo examples are retrieval hints for another visual check. Intrinsic evidence/contradiction guards remain enforced. This is controlled reference learning, not model-weight fine-tuning. Previously saved answers, confirmed/manual/rejected links, approvals and original photos are preserved. Active photo processing blocks submission/review gates.

The final critical-review layer reuses canonical findings across users for the same source snapshot and model/prompt version. Retry-only duplicate drafts do not change engineering inputs. Client visibility still requires Team Lead sharing of a current completed review. Immutable review bindings expose canonical provenance.

Runtime: Python3.12 local environment; RapidOCR1.4.4, OpenCV5.0.0.93 and FastEmbed0.9.0 installed in the F-drive venv. Semantic weights are under .local/models/embeddings, runtime downloads disabled. Reprovision using scripts/setup_evidence_models.py after installing backend/requirements.txt. Migrations0035 and0036 are additive. No cloud photo service or new Ollama service was introduced. Native Ollama remains external and unchanged.

Native two-photo validation: OCR succeeded on both sources; QR decoded on photo1. First complete versioned job2 processed2/2 in approximately141seconds on the currently CPU-only Ollama runtime. Both intended checkpoint matches were supported and both cross-matches remained insufficient. This is a functional probe, not an accuracy or400-photo timing benchmark. The400-photos/30-minute target is not demonstrated on this runtime. Final verification and preservation results are recorded in docs/development/VERSIONED_EVIDENCE_RECEIPT.json.

Final acceptance:382 core tests passed28.556s;12 desktop/mobile browser checks passed. Live final-version2/2photo run and four-role identical saved-record comparison passed. Cached replay of both photos completed0.015s with native inference/tool entrypoints instrumented to fail if called. Exact human-data preservation comparison passed; no pending jobs, no automatic approvals or changed links/answers. Final hidden launcher8788 serves127.0.0.1:8000. Receipt docs/development/VERSIONED_EVIDENCE_RECEIPT.json.


## 19 October 2026 Standard checklist library and construction room instances

Added the shared standard catalog at /devadmin/checklist-templates/standards/ with actual previews and four versioned sources: Telecom Survey Default from the previously uploaded FDED master; Telecom Inspection Built to Suit; Telecom Inspection Colocation and Modernization; Construction Inspection all stages. The FDED source remains byte-for-byte equivalent in its sections/field definitions: 16sections,172fixed spreadsheet rows and9equipment inventories,181fields total. Inspection baselines have56BTS fields,48Colocation/Modernization fields and55Construction base fields.

Construction stages are Preconstruction,Design,Grey Structure,MEP,Finishing,External works,Testing and handover. The room inventory supports24types and up to40named instances with optional floor/level. Repeated bedrooms/bathrooms keep separate section IDs, field IDs, answers and photo evidence. Room-specific points include wet-area,stairs,external-room and plant/garage topics. Stages and room instances are validated again on the server and in edited template configuration. Generated room fields include structured room context; a generic interior photo cannot establish room/floor identity for automatic suggestions. Explicit manual photo assignment remains available. Large room catalogs use semantic batches of at most500fields without dropping fields.

Super Admin can inspect the shared administrative catalog and source previews. Scoped Project Admins can create separate drafts only within their permitted industry, then use existing publish/assignment controls. Source templates are not engineering certification: approved project criteria, technical applicability and the existing independent review workflow are retained. Standard templates cannot be assigned to the wrong project industry or task workflow, including direct model/service callers. Existing custom templates without standard metadata retain their behavior. No SQL schema migration was introduced.

The three Telecom drafts were created for the existing scoped Admin through normal CSRF-protected invitation-era administration routes; they are not published or assigned automatically. Construction is available globally in the standard library for a Construction Admin; no synthetic live Construction project/account was created. The current two-checkpoint project, its published template, answers, approvals, photos and links were compared before/after and remain unchanged. Existing operational templates and project defaults were not reassigned. Frontend form errors preserve entered name, stages and room JSON; previews use actual selected stages/rooms, with no-JavaScript stage submission supported. Final acceptance evidence: docs/development/STANDARD_CHECKLISTS_RECEIPT.json.

Standard library final acceptance:403core tests passed29.378s;21desktop/mobile browser cases passed with zero writes. Actual server credential login/library/source-preview checks passed for Super Admin and Project Admin. Live3Telecom drafts created without publication or project reassignment; Construction shared standard available under its industry controls. Runtime hidden launcher36544. Receipt docs/development/STANDARD_CHECKLISTS_RECEIPT.json.
## 19 October 2026: five photos per second research and implementation

The requested target is 5 photos/second, or 100 seconds for 500 photos. The former
generative workflow averaged about 10.5 seconds/photo, roughly 0.095 photos/second.
Increasing an Ollama output limit or adding a few concurrent requests cannot be
reported as achieving a roughly 50-fold end-to-end improvement without measurement.

| Option | Assessment for this application |
| --- | --- |
| Tune the existing Qwen/Ollama worker | Retains detailed interpretation. Parallel requests require more context memory; the 8 GB GPU requires measurement before increasing concurrency. This remains the verification stage. |
| Batch CLIP image/text embeddings with FastEmbed ONNX | Selected for rapid visual retrieval. Both encoders are already supported by the installed library, use local CPU inference, fit beside the existing GPU model, and were benchmarked against the actual checklist and photos. |
| SigLIP2 or another modern image/text encoder | Relevant retrieval alternative, but this checkout lacks a matching text adapter for the installed SigLIP image adapter. Quality and speed would need separate evaluation; no superiority is claimed from an untested model. |
| A larger GPU or externally hosted batch inference | A possible route to faster full generative verification, requiring hardware-specific benchmarks and authorization before evidence is transferred to another service. Not introduced by this change. |

Primary references: [Ollama concurrency and memory](https://docs.ollama.com/faq#how-does-ollama-handle-concurrent-requests),
[CLIP vision ONNX model and intended similarity-search use](https://huggingface.co/Qdrant/clip-ViT-B-32-vision),
[paired text encoder](https://huggingface.co/Qdrant/clip-ViT-B-32-text),
[CLIP implementation](https://github.com/openai/CLIP), and
[SigLIP2 model documentation](https://huggingface.co/google/siglip2-base-patch16-224).

Implemented two independent stages. Fast AI Analysis reads and hashes each original,
creates a batched image embedding, compares it with the site's actual checklist, and
saves up to three similar checklist subjects. Profile/contact fields, measurements,
dates and system fields are excluded from visual matching. These are explicitly unverified;
similarity is not a calibrated confidence, sufficiency finding or approval. Detailed
AI verification continues through the existing rules/OCR/QR/vision worker. It remains
required by the existing submission/final-review gates. No automatic confirmations,
engineering answers or signatures are created by retrieval. A permitted engineer
can inspect a photo and manually choose its checklist point through the existing
CSRF/schema/permission-checked mapping endpoint; human decisions survive later runs.

Both model repositories are MIT-licensed ONNX ports, pinned to exact revisions and
official model SHA256 values. Runtime inference is local-only with downloads disabled.
Weights, tokenizers, runtime logs and result state stay under F:/iSurvix/iSurvix-Field/.local.
The vision model architecture and actual weight digest are verified before images
are processed. Cache identity includes model weights, tokenizer/preprocessing file
hashes, installed runtimes, retrieval source code and the checklist schema. New
immutable PhotoSearchVector/PhotoSearchResult tables are additive in migration0044;
they do not alter existing evidence, users, decisions or historical AI records.

Measured 64-photo image-encoding samples: 14.3-14.5 photos/second with two CPU threads,
19 photos/second with four threads, including verified original reads. Production
uses two threads to leave CPU capacity for the app and detailed verification.
The final cold-process 400-unique-photo retrieval run completed in 50.846 seconds,
7.867 photos/second, while detailed GPU verification continued. This includes model verification/load, encoding of 150 eligible evidence points from the 181-field checklist,
original SHA256 reads, image decoding/preprocessing, inference, checklist ranking,
permission/schema rechecks and durable SQLite commits. All 400 vectors in that
version were newly computed; retained rehearsal-version rows were not reused.
At that rate 500 photos are projected to take roughly 60-75 seconds for initial
suggestions. A timed 500-unique-photo test and equivalent retrieval quality across
industries have not been established. The result does not measure completed OCR,
detailed reasoning, human review or approval at five photos/second.

The live batch exposed a separate native observation truncation at photo67 after
64 completions. Increased the still-bounded native response ceiling from256to768
tokens; ordinary short responses do not consume the ceiling. Strict schema checks
and refusal to cache truncated output remain. The actual failing photo produced a
complete valid observation under the new settings. Historical Job7 and its error
are preserved; a normal Engineer enqueue explicitly adopted current tools only for
the336remainingphotos. Completed64results were not reset or requeued.

The workspace now displays Fast AI Analysis and Detailed AI verification separately,
pages two photo tiles at a time, and expands saved analysis history only on demand.
The per-site and enqueue capacity is500; batches remain20files and5MiBperphoto.
Boundary tests cover acceptance at500, denial at501 and duplicate intake at capacity.
Detailed verification must finish before the existing final AI review or submission
gates open. Read the current implementation receipt and handoff for live status.
