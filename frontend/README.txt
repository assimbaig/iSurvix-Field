iSurvix Survey — Latest Published Preview
Saved: 16 October 2026
Published source commit: 2e3e77d6acf21724e30c72167a1138413462654b

CONTENTS
- dist/: complete static frontend, editable JavaScript and CSS, logos and image assets.
- check-site-routing.cjs: functional checks for the latest site and wizard workflow.
- VERSION.json: source version and release scope.

LATEST CHANGES
- Latest uploaded iSurvix logo.
- Team lead Sites opens a site status summary and register.
- Each Site ID opens a read-only wizard from Sites.
- Review lists only sites Under Review; Site ID opens the review wizard.
- Wizard continuation is saved separately per Site ID and mode.
- Duplicate wizard launch buttons and arrows removed from the site register.
- Full approval, multi-section partial approval, full rejection, and decision history.
- Separate Engineer experience: assigned sites, pending/complete lists, guided checklist, photos, submission, and read-only submitted records.
- Admin checklist templates, section/field editing, client logos and versioning retained.

RUN LOCALLY
1. Extract the ZIP.
2. Open a terminal in the extracted folder.
3. Run: python -m http.server 8000 --directory dist
4. Open http://localhost:8000
No build or package installation is required. A local HTTP server is recommended instead of opening index.html directly.

STATIC HOSTING
Upload the CONTENTS of dist (index.html and assets/) to a separate static web directory, such as a preview subdomain. Enable HTTPS. Preserve the assets folder paths.
Do not replace a working Django application with this static preview.

FUNCTIONAL CHECKS
With Node.js available, run from the extracted folder:
node check-site-routing.cjs
The checks cover the current status register, site links, read-only guards, review eligibility, saved wizard steps, URL restoration, and engineer flow. Visual browser verification is pending.

SCOPE AND DATA
This package is the frontend preview. It contains no Django backend, database, server configuration, credentials, or real authentication.
The role selector is a demonstration control. Real permissions and project/site access must be enforced by the backend before production use.
Records, template edits, photos and wizard progress use browser localStorage. Changes are local to that browser/device and are not shared with other users. Local browser data is not bundled in this ZIP.
Sample photos and illustrative imagery do not count as uploaded survey evidence.
Large-scale uploads, shared storage, server-side approval locks, production Excel exports and backend integration remain separate deployment work.

EXISTING DJANGO APP
Keep the existing application, database and photographs backed up. Connect the frontend to authenticated Django APIs, repair the previously identified backend issues, and test in staging before replacing the live survey interface.
