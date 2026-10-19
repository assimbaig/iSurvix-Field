# iSurvix Field: local Codex development brief

## Workspace and current state

Work in the existing Windows checkout, usually `C:\Users\Muhammad Assim Baig\iSurvix-Field-Local`.
The working local launcher/text-AI integration is on branch `feat/local-ollama` (PR #2).
Inspect `git status`, branches, README, docs/LOCAL_SETUP.md and applicable AGENTS.md before changes.
Do not overwrite uncommitted work or change branches until its state is understood.

Existing code: Django backend, versioned custom checklists and client logos, section approvals,
Excel export, separately hosted sample-data redesign, and local Ollama text chat.
The redesigned frontend is NOT connected to real Django records yet.
The existing 36-test baseline was checked in Linux; Windows first launch remains to verify.
The user saw `No suitable Python runtime found`: install/verify Python 3.12 before launching.
Ollama was installed earlier; `qwen3.5:4b` was the selected model. Verify installed models and
actual vision capability rather than assuming its download or image support succeeded.

Some preliminary photo-queue code was drafted in the remote chat workspace but is NOT part
of this branch. Do not assume it exists locally or is finished. Implement/test against the
actual checkout, using this brief as requirements.

## User's requested working model

Use Codex in PowerShell to design, develop, test and maintain the app.
Use Ollama on the PC for operational AI inference on project photos and checklist evidence.
Use existing agent instructions if they can be found and verified. Codex subagents and
Ollama application agents are separate mechanisms; do not claim a connection without wiring it.
No paid/cloud AI API is requested for the application's photo processing.

Start with design/navigation refinement, then implement one end-to-end photo pilot before
scaling it to large batches. Preserve the admin builder and existing survey review workflow.

## Approved layout

- Logo/name top left; centered full-width module navigation below with room for more modules.
- Compact left catalog: Project > Subproject (when modeled) > Site ID; grouped/ungrouped sections.
- Large photo viewer, thumbnails, fullscreen, and source-evidence links.
- Two compact review rows; Full Approve, multi-section Partial Approve, Full Reject.
- Approved sections remain locked; unapproved sections can be corrected.
- Do not replace or discard the full 172-row FDED checklist, inventories or client branding.

## First release: bulk photos to reviewed draft checklist

1. Make a development branch and checkpoint existing work.
2. Start the current app, fix local setup issues, check Ollama connectivity and vision support.
3. Integrate the new UI with authenticated Django data; sample records must remain labeled.
4. Add site-scoped uploads: initially 200 photos/site; browser submits batches of <=20 files,
   <=5 MB each. Preserve original bytes and filename metadata; validate real JPEG/PNG/WebP.
5. Extract available EXIF GPS/time (do not infer missing metadata). Detect exact-byte duplicates,
   flag possible blur/low detail as advisory, and keep a normalized preview for inference.
6. Use a durable database-backed queue and an independent local worker. Show progress, failures,
   retry and recovery after interruption. Avoid unlimited GPU workers and request timeouts.
7. Check the selected local model reports vision capability. Send base64 image data through
   Ollama's native local API; do not enable cloud fallback or expose Ollama to the LAN.
8. Classify visible evidence and map it to the selected published checklist's field IDs.
   Use bounded prompts/structured output with validation and no silent catalog truncation.
9. Return draft values, reasons, uncertainty and photo references. Allow insufficient evidence.
   Never invent dimensions, electrical readings, ratings, standards clauses or N/A decisions.
10. Flag suspected visible anomalies with source photos and optional normalized bounding boxes.
    No detections does not mean the asset passes inspection. No engineering certification.
11. Show drafts in a review queue. Apply a proposed answer ONLY on explicit engineer acceptance.
    Recheck project access, field types, approval locks and stale values at acceptance time.
12. Export a report with drafts, source evidence, suspected defects and missing-information requests.
    Preserve an audit trail; model output must not approve, reject or silently overwrite records.

## Sketch phase

After the photo pilot works, add annotated evidence and measured plan/elevation sketches.
For dimensioned output, require user-confirmed measurements and units. Mark unknowns instead
of guessing scale from ordinary photos. Produce editable SVG/DXF where appropriate.
Do not present an illustrative layout as an engineered/as-built drawing.

## Agents and coordination

Where available, use specialized Codex subagents for UI, local vision/backend, and independent QA.
Keep file ownership clear; do not run several agents editing the same files without coordination.
If existing Agency Agents are present, read their actual instructions and integrate only relevant
roles. Runtime photo agents should share a durable job/evidence schema and one controlled local
inference queue. Roles/prompts are not automatically connected software.

## Acceptance checks

- Real local first launch; chosen admin account; saved surveys survive restart.
- Real Ollama image test on a few user-selected site photos before bulk scaling.
- Auth/CSRF/project access on all photo operations and downloads.
- Corrupt image, duplicate, missing EXIF, missing model, offline model, malformed JSON and restart.
- Approved-section locks, stale answer conflict, missing fields and no automatic approvals.
- UI tested at desktop and phone widths; photo/source links and review decisions work.
- Existing checklist/versioning/export tests continue to pass.
- Clearly report what is implemented, what was tested with a real model, and what remains.

Keep work local by default. Preserve `.local/` (database, media, secret) and do not commit it,
credentials, logs, installed dependencies or real project photos. Do not deploy to Hostinger
or force-push/merge branches without the user's instruction.

## First action

Inspect the checkout, local agent configuration, Python 3.12 and Ollama. Then provide a short
status and begin making the app run locally. Continue through implementation and tests; ask
only when a missing input blocks actual work. Do not require a cloud API key for Ollama.
