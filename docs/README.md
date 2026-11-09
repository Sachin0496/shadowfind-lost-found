# ShadowFind - web build

This folder is the static build served by GitHub Pages.

The Flask app in `../app/` needs Python, which GitHub Pages cannot run. Here the
same pipeline is ported to the browser: `assets/vision.js` does the shadow
extraction with OpenCV.js and builds the identical 64-value descriptor, and
`assets/store.js` keeps the accounts, reports and claims in `localStorage`.

Everything is client-side, so the whole workflow (report, rank, claim, accept,
return) works from a plain static host.
