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
