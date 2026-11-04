# Corporate iField entry pages

This is an eight-file **partial update** for the existing `isurvix.com` corporate
website. It preserves the site's existing shared styles, scripts, fonts, images
and other pages. It is not a standalone copy of the whole corporate website.

The homepage has one compact, right-aligned **Login** disclosure. Its accessible
name is **Login to iSurvix Platform**. The existing dark contact-pill design
opens the real iField login; other platforms
remain noninteractive until their login destinations are available. Product
pages provide information and previews without separate sign-in controls.
Authentication and project permissions remain in the Django application.

`source-manifest.json` lists the only eight publishable files and their hashes.
Publish versioned assets before the HTML that references them. Do not upload
this README or tests, delete unlisted website files, or replace the existing
site root with this partial directory. Keep previous cached assets available
for rollback. In particular, `platform-login-v4.css` uses a new URL; it does not
overwrite the previously cached `platform-login.css` or `platform-login-v3.css`.

Offline source checks, using the project's existing Python environment:

```powershell
.local\venv\Scripts\python.exe -m unittest discover -s website\corporate\tests -p "test_*.py" -v
```

Optional browser verification uses an already installed Playwright and browser.
It does not install packages, download a browser, read credentials, create
business records or approve work. On Windows the default browser is Microsoft
Edge. Live mode reads the actual public website; preview mode substitutes only
the local homepage and versioned CSS while using the existing public assets.

```powershell
node website\corporate\tests\header.browser.cjs
node website\corporate\tests\header.browser.cjs --preview
```

Screenshots and reports are written under `.local/corporate-qa/`, outside this
publishable directory. Initial corporate CDN browser checks may run before the
page appears; the test allows normal browser JavaScript to complete them and
does not bypass protection. JavaScript-free disclosure behavior is tested in
preview mode; the CDN's first-visit check can itself require JavaScript.

These checks cover this corporate-page integration. They do not establish
native AI availability, company isolation, engineering compliance, production
capacity or complete release acceptance.
