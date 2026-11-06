# Corporate website refresh (revision 5)

Published to isurvix.com on 6 November 2026 under explicit owner authorization.

- Source manifest lists 23 allowlisted files only. Never publish this whole directory: it includes tests, source notes and reference copies of existing shared assets.
- Assets and sitemap are uploaded first, HTML next, guarded .htaccess last. Preserve every unlisted live file, old cached assets, authentication links and application records.
- Genuine owner-supplied iField, iGeoview and iMoneta logos are optimized WebP assets. Private source provenance and original-file backup are retained under the main project .local/public-website-refresh-20261106 directory.
- Homepage-only Login is intentional. Desktop control is compact; mobile retains a usable touch target. Authentication stays at https://app.isurvix.com/login/.
- iField is available in private beta; planned housing and unreleased products remain labelled accurately. No invented client references or manufacturer claims.
- Privacy information explains the local email-draft builder and separate platform without asserting legal certification.
- Minimal browser security headers were verified on live responses. No bot protection/CDN was disabled. Initial automated-browser 403 behavior needs provider investigation.

Run unit and isolated HTTP integration checks from the project root:

```powershell
.local\venv\Scripts\python.exe -m unittest discover -s website\corporate\tests -p "test_*.py" -q
```

Browser QA uses the existing Playwright/Edge installation; no new browser downloads or operational submissions are required. Current evidence includes 20 source/HTTP tests, 183 preview-browser assertions and 4 independent adversarial checks. See private live verification before claiming deployed behavior.
