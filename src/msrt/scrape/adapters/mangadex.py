"""MangaDex chapter scraper.

v0.2a delivers only the *skeleton*: the adapter recognises MangaDex
chapter / title URLs (and ``mangadex.org/chapter/<UUID>`` short forms),
but ``fetch()`` raises ``NotImplementedError`` pointing at v0.2b. This
is enough to validate the registry routing without touching the
network — full client + At-Home server resolution lands in v0.2b
together with the tests against a saved JSON fixture.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from msrt.scrape.base import ChapterScraper, FetchError, FetchResult
from msrt.scrape.registry import register

_MANGADEX_HOSTS: frozenset[str] = frozenset(
    {"mangadex.org", "www.mangadex.org", "canary.mangadex.dev"}
)
# Match only ``/chapter/<UUID>`` or ``/title/<UUID>`` prefixes — UUIDs
# elsewhere in the path (eg. embedded in a tracking parameter) shouldn't
# count as a chapter URL. UUIDs are accepted in both lowercase and
# uppercase to match real-world links pasted by users.
_CHAPTER_OR_TITLE_RE = re.compile(
    r"^/(?:chapter|title)/"
    r"(?P<uuid>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
    r"(?:/.*)?$",
    re.IGNORECASE,
)


@register
class MangaDexScraper(ChapterScraper):
    """Skeleton adapter; the real fetch path is implemented in v0.2b."""

    name = "mangadex"

    def matches(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
        except ValueError:
            return False
        host = (parsed.netloc or "").lower()
        if host not in _MANGADEX_HOSTS:
            return False
        return bool(_CHAPTER_OR_TITLE_RE.match(parsed.path))

    async def fetch(self, url: str, output_dir: Path) -> FetchResult:
        if not self.matches(url):
            raise FetchError(
                f"URL MangaDex non valido: {url!r}. Atteso un link "
                "tipo https://mangadex.org/chapter/<UUID>."
            )
        raise NotImplementedError(
            "Adapter MangaDex completo arriva in v0.2b "
            "(API /at-home/server + downloader). Per ora salva le scan "
            "manualmente e passa la cartella a 'msrt run-local'."
        )
