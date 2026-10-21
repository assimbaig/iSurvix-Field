# Survey drawing example

`synthetic-survey/revision-001/` is clearly labelled synthetic training data. It is
not Z93004 or any real site, and is not suitable for construction or commissioning.

The sample contains a five-page vector PDF, five editable DXF sheets, PNG previews
of every sheet, a shared `geometry.json`, a manifest and a portable ZIP bundle.
Both PDF and DXF use exactly the same paper-millimetre entity records. The geometry
SHA256 is recorded in the PDF metadata, DXF dictionary and manifest. DXF entity
source hashes and sequence indices are stored in the `ISURVIX` extended data.

The site plan uses explicitly confirmed synthetic coordinates. The antenna,
equipment and grounding sheets are **evidence schedules**, not measured equipment
arrangements or electrical/structural designs. Unsupported sheets are listed in
the drawing register as missing. Missing labels and concealed connections are not
filled with plausible substitutes. Uncalibrated photographs never establish scale.

Generic cabinet/antenna/dish/platform envelopes come from the versioned
`backend/core/drawing_blocks_v1.json`. They are labelled "Typical - verify against
site" and carry no manufacturer accuracy claim. No actual manufacturer model,
bracket design, structural capacity, circuit protection or engineering compliance
has been verified. No design code or load combinations are claimed.

Project-assigned logo files are copied into `assets/` when supplied by the saved
project branding. The sample has no client artwork. Download the ZIP when sharing
branded DXF drawings so external logo references travel with the DXF files.

To regenerate into a **new empty destination** from the project root:

```powershell
.local/venv/Scripts/python.exe scripts/generate_survey_drawing_samples.py --output .local/drawing-sample-new
```

The exporter refuses to overwrite an existing completed revision. Failed exports
are not published; the same revision can be retried. Draft outputs remain marked
"DRAFT - FOR REVIEW". Only the integrated server-side human review/release workflow
may request released output. A release marks a reviewed survey record; it does not
certify engineering design or make unknown geometry accurate.

Current bounds: 32 sheets, 1,000 explicit measured records, 5,000 findings and
20,000 body entities. Excess drawing presentation content is flagged for review
in the register/verification notes; complete source processing records remain in
the survey. Text is ASCII for predictable PDF/CAD font portability; source records
retain their original text. DXF sheet coordinates use A3 paper millimetres; the
titleblock states the measured-diagram plotting ratio or "Not to Scale".
