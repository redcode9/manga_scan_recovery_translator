"""Local FastAPI backend that powers the desktop/web UI (v0.4).

The UI server reuses the existing pipeline functions (``run_local``,
scrapers, ``run_doctor``, etc.) — it never re-implements scraping,
translation or packaging in the API layer. The split is intentional:
the UI orchestrates and visualises, the core does the work.

Public entry point: :func:`create_app`. Use ``uv run msrt ui`` to boot
``uvicorn`` against it on ``127.0.0.1`` (no LAN exposure).
"""

from msrt.ui_server.app import create_app

__all__ = ["create_app"]
