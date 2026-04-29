# Browser Capture Fallback Design

## Context

`msrt run-local` is validated for local image folders. The remaining product gap is URL input, especially MangaFire-like readers where raw image URLs may be hidden, protected, or unstable while the page is still readable in a normal browser.

The browser capture fallback exists to turn a visible reader page into a local image folder without bypassing site protections. Once images are captured, the existing local translation pipeline remains the source of truth.

## Decision

`msrt run <URL>` uses a strategy chain:

1. Dedicated adapter / raw download.
2. Generic DOM image extraction.
3. Browser capture fallback.

The fallback is automatic. Users do not need to pass a separate `--fallback browser` flag for normal use. If raw extraction fails or yields incomplete/invalid pages, the URL pipeline opens the browser capture path.

## Safety Boundary

The browser fallback must not bypass authentication, Turnstile, captcha, Cloudflare, or equivalent human checks.

If a human check is detected or the scan is not visible:

1. The tool keeps the browser open.
2. The CLI prints a clear message asking the user to complete the verification/login manually.
3. The tool waits until a valid scan is visible, then continues automatically.
4. If no scan becomes visible before timeout/cancel, the run fails with a clear error.

No stealth mode, token forging, captcha solving, or anti-bot circumvention belongs in this project.

## Capture Semantics

The fallback captures the manga page, not the browser window.

Preferred order:

1. If the DOM exposes a raw image URL after render, use that URL and download the raw file.
2. If not, screenshot the largest valid manga image/canvas element.
3. If element screenshot is unreliable, crop the page screenshot to the detected manga page bounding box.

The capture must exclude navbar, sidebars, background art, controls, comments, and reader chrome. It should validate minimum dimensions before accepting a page. Low-resolution captures continue only with a warning because OCR quality can degrade.

## Navigation

The browser fallback supports two reader layouts:

- Paged reader: capture current page, advance via next button/keyboard/URL state, stop on page count reached or repeated page hash.
- Long strip: scroll through the document, detect page-sized image elements, capture each once, stop when no new valid pages are found.

The first implementation should prioritize paged readers because MangaFire exposes page/chapter controls and the user's target flow is chapter-based reading.

## Output

Browser capture writes a normal local page folder under the URL cache, then hands that folder to the existing `run-local` path.

The `RunManifest` records:

- `input.type = "url"`
- source URL
- strategy selected: `browser-capture`
- browser viewport and device scale factor
- captured page count
- page hashes
- whether manual intervention was needed
- warnings such as low-resolution capture or duplicate pages skipped

## Testing

Automated tests should avoid live MangaFire/network dependency.

Unit/integration coverage:

- synthetic HTML fixture with navbar/sidebar and a central scan image
- element selection chooses scan over UI assets
- crop excludes reader chrome
- duplicate page hash stops/skip logic
- manifest records `browser-capture`
- manual-intervention state can be simulated without solving any challenge

Manual E2E:

- MangaFire Wistoria chapter URL on the user's machine
- normal reader visible: fallback captures pages automatically
- challenge visible: user completes it manually, tool resumes

## Placement In Roadmap

v0.2 builds URL pipeline foundation and MangaDex.

v0.3 adds MangaFire plus automatic browser capture fallback. If MangaFire direct extraction remains blocked, browser capture becomes the practical path to the user's target workflow: URL in, translated PDF out.
