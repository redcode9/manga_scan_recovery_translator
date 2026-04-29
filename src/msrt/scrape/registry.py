"""Adapter registry — turns a URL into the right ``ChapterScraper``.

Adapters self-register via the ``@register`` decorator at import time.
The registry is intentionally simple: we walk it in declaration order
and return the first scraper that claims the URL. There is no priority
system in v0.2a; if a future adapter overlaps with another (e.g. a
generic euristic + a site-specific one) we'll add one then.
"""

from __future__ import annotations

from collections.abc import Iterable

from msrt.scrape.base import ChapterScraper, FetchError

_REGISTRY: list[type[ChapterScraper]] = []


def register(scraper_cls: type[ChapterScraper]) -> type[ChapterScraper]:
    """Class decorator that registers a ``ChapterScraper`` subclass."""

    if scraper_cls not in _REGISTRY:
        _REGISTRY.append(scraper_cls)
    return scraper_cls


def all_scrapers() -> Iterable[type[ChapterScraper]]:
    """Snapshot of registered adapters, in declaration order."""

    return list(_REGISTRY)


def scraper_for_url(url: str, *, site: str = "auto") -> ChapterScraper:
    """Return a scraper instance that handles ``url``.

    With ``site="auto"`` (the default) we try every registered adapter
    until one's ``matches()`` returns ``True``. Pass ``site="<name>"``
    to force a specific adapter regardless of the URL — useful when
    debugging or to opt into a less-strict generic scraper.

    Raises ``FetchError`` if no adapter claims the URL or the requested
    ``site`` name isn't registered.
    """

    # Trigger adapter registration. Importing the package's adapters
    # subpackage runs each module's ``@register`` decorators. Doing this
    # lazily avoids a circular import at module load time.
    import msrt.scrape.adapters  # noqa: F401  (registers adapters)

    if site != "auto":
        for cls in _REGISTRY:
            if getattr(cls, "name", "") == site:
                return cls()
        names = ", ".join(sorted({getattr(c, "name", "") for c in _REGISTRY}))
        raise FetchError(
            f"Adapter '{site}' non disponibile. Adapter registrati: {names or '(nessuno)'}."
        )

    for cls in _REGISTRY:
        instance = cls()
        if instance.matches(url):
            return instance
    raise FetchError(
        f"Nessun adapter supporta {url!r}. Usa --site per forzarne uno, "
        "oppure scarica le scan a mano e passa la cartella a 'msrt run-local'."
    )
