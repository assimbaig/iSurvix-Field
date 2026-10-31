# Local browser dependencies

These are checked-in browser resources for the existing application. Runtime
pages load them from Django static storage; no CDN fallback is configured.
`manifest.json` records each original source, component/version, SHA256 and
copied license notice. The connected preparation step downloaded about 3.3 MB
explicitly; it did not download an AI model or alter the machine trust store.

| Component | Version | Included notice |
| --- | --- | --- |
| Bootstrap | 5.3.3 | MIT |
| Font Awesome Free | 6.5.1 | CSS code MIT; included fonts SIL OFL 1.1; upstream notice also describes CC BY 4.0 for SVG/JS icons |
| Leaflet | 1.9.4 | BSD 2-Clause |
| Leaflet red marker | 234813b7dffa11eee06f41618e1f5752c6b7bd8d | BSD 2-Clause |
| Inter | 4.1 | SIL OFL 1.1 |
| jQuery | 3.6.0 | MIT |
| Select2 | 4.1.0-rc.0 | MIT |

Bootstrap, Leaflet and Font Awesome bytes match the five existing stylesheet/
script SRI values. Inter's variable-font bytes remain original; `inter.css` is
a local font-face declaration replacing the unversioned Google Fonts request.
Leaflet image/font dependencies and available source maps are included locally.
The marker is pinned to an exact commit instead of the previous moving URL.

Official references: [Bootstrap download](https://getbootstrap.com/docs/5.3/getting-started/download/),
[Leaflet local files](https://leafletjs.com/download.html),
[Font Awesome notice](https://github.com/FortAwesome/Font-Awesome/blob/6.5.1/LICENSE.txt),
[Inter release](https://github.com/rsms/inter/releases/tag/v4.1), and
[marker notice](https://github.com/pointhi/leaflet-color-markers/blob/234813b7dffa11eee06f41618e1f5752c6b7bd8d/LICENSE).

This inventory is not a legal review, vulnerability clearance or commercial
license approval. Preserve each notice when redistributing the customer package.
