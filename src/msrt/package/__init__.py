"""Output packagers (CBZ, PDF) for translated chapters.

Each module here turns the ordered list of translated page images
produced by the pipeline into a final, shareable artefact:

* :mod:`msrt.package.cbz` — CBZ archive with an embedded ``ComicInfo.xml``.
* :mod:`msrt.package.pdf` — single-page-per-image PDF.
* :mod:`msrt.package.naming` — filename ordering rules shared by both
  packagers and the local-input collector.

Packagers are deliberately stateless and never reach out for assets:
they take the exact set of files the pipeline hands them and emit one
output. Stragglers from previous runs cannot leak in because the
pipeline pre-filters via the ``Chapter.pages`` order.
"""
