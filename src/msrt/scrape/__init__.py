"""Site adapters and download primitives for source pages.

Layout:

* :mod:`msrt.scrape.base` — abstract scraper interface, ``FetchResult``,
  ``FetchedPage``, and ``FetchError`` (the only error type pipeline code
  ever needs to catch).
* :mod:`msrt.scrape.registry` — picks the right adapter for a given URL
  via a small ordered list of ``matches()`` predicates.
* :mod:`msrt.scrape.adapters` — one module per supported site
  (MangaDex, MangaFire, …). Adapters are intentionally tiny: each
  returns a ``FetchResult``, and the surrounding pipeline does the
  atomic-promote / dedup / packaging.
* :mod:`msrt.scrape.downloader` — shared HTTP client with per-host
  rate limiting, retry policy, and Cloudflare-friendly headers.
* :mod:`msrt.scrape.browser_capture` — Playwright fallback for sites
  that don't expose a stable JSON reader.
* :mod:`msrt.scrape.cover` — best-effort cover-art resolver chain
  (MangaDex → AniList → on-disk composite → AI generation).
* :mod:`msrt.scrape.selection` — chapter-range / chapter-list parsers
  shared between the CLI and the UI batch endpoint.

A new adapter only needs to subclass ``ChapterScraper`` and register
itself in :mod:`msrt.scrape.registry`; nothing else in the pipeline
needs to change.
"""
