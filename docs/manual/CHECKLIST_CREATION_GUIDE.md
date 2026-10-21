# Create and manage checklists

Project Admins open **Checklist templates** to use the compact checklist table.
Search by name or filter Draft, Published and Disabled. Select rows for bulk
actions. Hover over an action icon to read its purpose before clicking it.

## Create from zero

1. Select **Create checklist**, enter its name, industry and workflow, then select
   **Recommend sections**.
2. Keep the suggested sections you need, remove others and add any new section
   names. Select **Accept sections & recommend checkpoints**.
3. Select the suggested checkpoints for each accepted section. Add your own
   checkpoints with the input type, answer requirement and photo requirement.
   Every accepted section needs at least one checkpoint.
4. Select **Accept checkpoints & create draft**. Review its labels, choices,
   requirements, evidence rules and branding in the editor. Save or publish.
5. Assign the published checklist to the intended project before assigning new
   site work. Saved tasks retain their original template and approvals.

Recommendations start with the appropriate standard templates. Published,
enabled checklists in your permitted projects also contribute suggestions (the
100 most recent published versions);
frequently used sections and checkpoints appear earlier. Drafts, disabled
templates, foreign projects and survey answers do not teach this library.
Suggestions always require your selection; they never change a published template.

## Status and safe changes

| State | Available actions |
| --- | --- |
| Draft, unused | Edit, publish, replicate, export, disable or delete. |
| Published, unused | View, replicate, export, disable, or explicitly unpublish before editing. |
| Used by any saved task | View, replicate, export or disable. Its structure cannot be edited, unpublished or deleted. |
| Disabled | Retained in the table and available to existing work. Enable it before new assignments or draft editing. |

Disable stops new assignments without removing historical work. Deleting requires
confirmation and an unused, unpublished draft with no project default or protected
historical reference. Change the project's default before deleting a referenced
draft. Bulk actions either all complete or leave the selected records unchanged.

## One-page Excel sample

Select **Download one-page sample**. It contains one worksheet named **Checklist**.
Set the name, industry and workflow at the top. Replace the example rows, repeat
section names to group points and add rows underneath. Keep row 7 headings.

| Column | What to enter |
| --- | --- |
| Section | The heading that contains the checkpoint. |
| Checkpoint | Your question or inspection point. |
| Input type | text, textarea, number, date, select, inspection or photo. |
| Required | Yes for a mandatory answer, No for an optional answer. |
| Photo | None, Optional or Required. |
| Choices | For select inputs, separate choices with `\|`. |
| Unit | A recorded unit, such as m or V, where applicable. |
| Help | Brief instructions for the Engineer. |

Use **text** with **Required photo** when both text and a photograph are mandatory.
Use **photo** for a photograph-only point. Optional photographs do not block submission;
Required photographs must satisfy the application's normal evidence validation.

Import through **Checklist Wizard → Import Excel**, inspect the preview and confirm
draft creation. To add points to an existing unused draft, open it and select
**Import extra points**. Preview and confirm the additions; existing points remain.
Repeated confirmation of the same preview does not add the points twice.

Use the existing advanced Excel format for repeating tables and detailed evidence
rules. Formulas, macros and external workbook links are unsupported.

## Open the intended revision

In **Existing checklist**, **Edit existing draft** and **Replicate checklist** have
separate selections. Choose the draft and select **Open draft editor** to edit
that exact saved revision. Replicate creates a separate draft from the selected
saved source. The editor sidebar, name, revision and status identify the record
being edited. Saving returns to the same revision; a stale open window cannot
overwrite a newer save.

The two compact header rows contain the name, revision actions and **Checklist
required** setting. Enable that setting for the integrated AI Checklist & Drawings
survey workflow. Inspections retain their existing workflow. Longer publication
guidance is under **Help**. Published, disabled and used revisions remain protected.

## Edit the hierarchy

The checklist tree has **Group → Section → Checklist field** levels. Expand a
heading and select a node to open its properties beside the tree. On a phone,
properties appear below the tree. The checklist picker collapses to save space.

- Use **+ Group**, **+ Section** or **+ Field** to add to the selected location.
  Edit its name or settings in Properties.
- Select section checkboxes and choose **Group selected** to use an existing or
  new group. A section's **Parent group** also moves it between groups.
- Select a named group and choose **Ungroup** to keep every section and field
  while removing the group. Ungrouped sections remain supported.
- Use **Up** and **Down** in Properties to reorder sibling groups, sections or
  fields. Grouping and movement retain existing field IDs and evidence rules.
- Select **Save draft** to keep the hierarchy and settings. Expansion and selection
  are remembered in the current browser tab for that particular revision.

**Import extra points** still opens the reviewed Excel append workflow. It adds
points to an editable draft while retaining the existing structure.

## Review recommended additions

**Recommended additions** lists real points from the matching standard and scoped
published library. Each suggestion identifies its target, source and reason.
Search or page through suggestions, expand **Review & edit**, adjust the proposed
field or target section, then choose **Accept addition** or **Dismiss**. New sections
can be placed in an existing group or left ungrouped.

Acceptance adds the point to this editable draft; **Save draft** persists it.
Repeated acceptance does not duplicate the same point. Dismissals also persist
when saved; use **Show dismissed** and **Restore** to reconsider them. Published
revisions cannot accept suggestions. An unavailable source shows an error with
retry, or an honest empty state. Suggestions are library recommendations, not
site evidence or compliance decisions.

## Compact branding

**Client logos and company branding** starts collapsed with configured names and
thumbnails. Expand it for Company, Left client and Right client controls. The
company name comes from the Admin company account. Empty file inputs preserve
saved logos. Upload a replacement or explicitly tick **Remove existing logo**,
then save. Published revisions and historical report snapshots remain protected.
