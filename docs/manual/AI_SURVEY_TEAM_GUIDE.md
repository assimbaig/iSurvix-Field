# AI survey checklist and drawing team guide

Use **AI Checklist & Drawings** inside a saved Telecom survey to prepare a reviewed
checklist and evidence-based drawing package. The Project Admin must first enable
**Checklist required** on its template. Inspection modules and templates without
this setting continue through their existing workflow.

## Project Admin

Open **Checklist templates**, duplicate a published template to create a draft,
enable **Checklist required**, and add the company and client logos assigned to
that template. Publish and assign the revision to the project before assigning
new surveys. Published templates and the templates saved with earlier surveys
remain locked. Nokia and TAWAL artwork is used only when assigned to that template.

Mark fields that are mandatory before AI submission with `survey_input: true`
and `required: true` in the existing template definition editor. Required checklist
answers still follow their usual submission and approval validation.

## Engineer

Project Admins and Team Leads create the assigned site from **Create task** on
Overview or Tasks. Single-site entry and bulk site tables preload recorded site
details; the saved project approval route applies to every created task. Engineers
find this work in **My tasks**, with the current workflow step beside each site.

1. Open the assigned saved survey. Complete site identification and required survey
   inputs. Save the survey before submitting it for processing.
2. Upload photos in **Photos & matching**. Add PDF records, measured sketches,
   Excel workbooks or sketch images in **AI Checklist & Drawings**. Finish every
   upload before selecting **Submit for AI processing**.
3. Follow the saved stages: **Queued**, **Analysing evidence**, **Preparing checklist**,
   **Preparing drawings**, and **Ready for review**. A failed job keeps its completed
   work. Read its error, correct the cause and use **Retry failed processing**.
4. Review checklist items beside their proposed answers, confidence and source
   references. Select reliable items for grouped acceptance. Correct disagreements;
   record a reason when rejecting a value, acknowledging missing information or
   choosing **Not applicable**. A photo does not prove an inspection passed.
5. In extracted records, correct transcription errors with their units and reasons.
   Original extractions and source references remain available. An affected checklist
   item needs another review after its extracted record changes.
6. Inspect drawing previews. Add measured drawing records only after checking the
   selected source: position, width, height, units and reference must be known.
   Photographs alone cannot establish exact dimensions or concealed connections.
7. Confirm **Apply checklist & complete Engineer review**. This explicit action
   copies accepted, valid answers and confirmed photo links to the saved checklist,
   preserves unrelated answers and existing human photo rejections, and prepares
   a new draft drawing edition. Missing items remain visible. Required-field and
   evidence rules must still be satisfied before ordinary survey submission.
8. Submit the saved survey through its existing QA / Team Lead / optional Client
   approval route. Editing survey inputs later requires a new processing revision.

An interrupted upload can leave an open upload session. After confirming that its
upload has stopped, close your own session using the explicit recovery control.
Do not close an upload that is still running in another window.

## QA Engineer, Team Lead and Client

| Role | Responsibility |
|---|---|
| Assigned QA Engineer | Check the Engineer-reviewed package and source evidence. Complete technical review, or return it with a correction reason. A return invalidates the earlier package endorsement. |
| Team Lead | Complete the ordinary survey approval route, then use **Release approved outputs** for the exact package independently checked by QA. |
| Client | Complete the Client stage when required. In this area, view and download current released outputs; internal AI suggestions and review notes are not shared. |
| Super Admin | Administration only; no engineering approval or output release. |

Engineer preparation, QA checking and Team Lead release require different users.
Changing a reviewed answer or drawing record invalidates the earlier package review.
Previous input revisions, draft editions and decisions remain in history.

## Downloads and drawing meaning

The vector PDF and editable DXF sheets come from the same geometry record. Download
the **drawing bundle** when sharing DXF files: it contains the associated logo assets,
PDF, drawings, previews and geometry record. Keep these files together.

Drafts are marked **Draft - For Review**. Unsupported sheets are listed as missing
in the register. Evidence schedules are **Not to Scale**. Generic equipment envelopes
are marked **Typical - verify against site**. These exports record the available
survey evidence; they do not certify manufacturer dimensions or engineering compliance.

## File limits

Photos use the existing 500-per-site limit, up to 20 per upload batch and 5 MiB each.
Supporting documents are limited to 30 MiB each, five per upload batch and 50 per
survey. PDF files support up to 80 pages; workbooks support up to 30 sheets and
500 embedded-image placements. The total processing limit is 2,000 bounded sources.
Macros, encrypted PDFs, external workbook relationships and embedded executable/OLE
content are unsupported. Workbook formulas are recorded as missing information and
are never executed. Supply recorded values when a formula result is needed.

## Start on Windows

Double-click **Start-iSurvix.cmd** in the project folder. It applies additive database
migrations and starts the application plus its independent survey worker. Keep the
PC and Ollama running during processing. Restarting preserves queued jobs; an
interrupted active job resumes after its lease expires, normally five minutes.
Keep the `.local` folder: it contains your database, photos, documents and outputs.
