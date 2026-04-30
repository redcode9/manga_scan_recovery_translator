"""Site-specific scrapers.

Importing this package triggers registration of every adapter via the
``@register`` decorator on each subclass. The registry module imports
this package lazily so we don't have a circular dependency at startup.
"""

from msrt.scrape.adapters import mangadex, mangafire

__all__ = ["mangadex", "mangafire"]
