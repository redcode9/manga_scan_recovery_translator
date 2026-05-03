from __future__ import annotations

import asyncio
import itertools
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

from msrt.scrape.downloader import (
    DownloadError,
    DownloadJob,
    download_pages,
    find_duplicate_pages,
)


def _real_image_bytes(*, fmt: str = "PNG", color: str = "red") -> bytes:
    """Produce a tiny real image so the downloader's magic-byte validator
    accepts it. Returning bytes from ``Pillow`` keeps the tests honest:
    if our magic-byte detector regresses, the test would fail because
    the round-trip would no longer recognise the format."""

    buf = BytesIO()
    Image.new("RGB", (4, 4), color).save(buf, format=fmt)
    return buf.getvalue()


def _run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


def test_download_pages_writes_files_with_natural_names(tmp_path: Path) -> None:
    payloads = {
        "https://example.com/a.png": (_real_image_bytes(fmt="PNG"), "image/png"),
        "https://example.com/b.jpg": (
            _real_image_bytes(fmt="JPEG", color="blue"),
            "image/jpeg",
        ),
        "https://example.com/c.webp": (
            _real_image_bytes(fmt="WEBP", color="green"),
            "image/webp",
        ),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        body, ctype = payloads[str(request.url)]
        return httpx.Response(200, content=body, headers={"content-type": ctype})

    transport = httpx.MockTransport(handler)
    jobs = [
        DownloadJob(index=1, url="https://example.com/a.png"),
        DownloadJob(index=2, url="https://example.com/b.jpg"),
        DownloadJob(index=3, url="https://example.com/c.webp"),
    ]

    files = _run(download_pages(jobs, output_dir=tmp_path, transport=transport))

    assert [f.local_path.name for f in files] == ["001.png", "002.jpg", "003.webp"]
    for file in files:
        assert file.sha256.startswith("sha256:")
        # Files end up in output_dir, not in the staging dir.
        assert file.local_path.parent == tmp_path


def test_download_pages_purges_stale_canonical_pages_from_previous_fetch(
    tmp_path: Path,
) -> None:
    """Regression: a 50-page chapter followed by a 3-page chapter must
    leave only the new 001..003 in output_dir — not 004..050 from the
    previous run. Same class of bug as v0.1.z translated-pages cleanup,
    on the fetch side."""

    # Pre-populate the output dir as if a 5-page fetch had completed.
    for i in range(1, 6):
        (tmp_path / f"{i:03d}.png").write_bytes(b"old payload")
    # And drop a non-canonical user file that should NOT be touched.
    (tmp_path / "cover.jpg").write_bytes(b"user file")
    (tmp_path / "msrt-run.json").write_text("{}", encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_real_image_bytes(fmt="PNG"),
            headers={"content-type": "image/png"},
        )

    transport = httpx.MockTransport(handler)
    jobs = [
        DownloadJob(index=1, url="https://example.com/a.png"),
        DownloadJob(index=2, url="https://example.com/b.png"),
    ]

    files = _run(download_pages(jobs, output_dir=tmp_path, transport=transport))

    canonical = sorted(
        p.name
        for p in tmp_path.iterdir()
        if p.is_file() and p.name not in {"cover.jpg", "msrt-run.json"}
    )
    assert canonical == ["001.png", "002.png"], f"Stale canonical pages leaked: {canonical}"
    # Non-canonical user files must survive.
    assert (tmp_path / "cover.jpg").exists()
    assert (tmp_path / "msrt-run.json").exists()
    assert len(files) == 2


def test_download_pages_promotes_only_after_full_success(tmp_path: Path) -> None:
    """If even one page fails, ``output_dir`` must NOT contain stragglers
    from the successful tasks. The staging dir keeps them around for the
    user to inspect, but the canonical output is left clean."""

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("a.png"):
            return httpx.Response(
                200,
                content=_real_image_bytes(fmt="PNG"),
                headers={"content-type": "image/png"},
            )
        return httpx.Response(404, content=b"not found")

    transport = httpx.MockTransport(handler)
    jobs = [
        DownloadJob(index=1, url="https://example.com/a.png"),
        DownloadJob(index=2, url="https://example.com/missing.png"),
    ]

    with pytest.raises(DownloadError):
        _run(download_pages(jobs, output_dir=tmp_path, transport=transport))

    # output_dir clean (only .staging is allowed)
    canonical = [p for p in tmp_path.iterdir() if p.is_file() and p.suffix in {".png", ".jpg"}]
    assert canonical == [], f"Files leaked into output: {canonical}"


def test_download_pages_rejects_html_body_with_image_content_type(
    tmp_path: Path,
) -> None:
    """Regression for v0.2a.1 hardening: a server can lie via headers.
    HTML body with ``Content-Type: image/png`` must NOT pass validation
    just because the header is plausible. Magic bytes are authoritative."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"<html><body>You must log in to view this page</body></html>",
            headers={"content-type": "image/png"},
        )

    transport = httpx.MockTransport(handler)
    jobs = [DownloadJob(index=1, url="https://example.com/a.png")]

    with pytest.raises(DownloadError, match="non immagine"):
        _run(download_pages(jobs, output_dir=tmp_path, transport=transport))

    assert not (tmp_path / "001.png").exists()


def test_download_pages_rejects_json_body_with_image_content_type(
    tmp_path: Path,
) -> None:
    """Same bug class with a JSON error envelope. Some CDNs return JSON
    error structures wrapped in image/* Content-Types."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b'{"error":"forbidden"}',
            headers={"content-type": "image/jpeg"},
        )

    transport = httpx.MockTransport(handler)
    jobs = [DownloadJob(index=1, url="https://example.com/a.jpg")]

    with pytest.raises(DownloadError, match="non immagine"):
        _run(download_pages(jobs, output_dir=tmp_path, transport=transport))


def test_download_pages_rejects_html_with_200(tmp_path: Path) -> None:
    """A "soft fail" page (HTML or login wall served as 200) must NOT be
    written to disk as a fake image. This guards against silent failures
    on sites that don't return proper 4xx/5xx codes."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"<html><body>You must log in</body></html>",
            headers={"content-type": "text/html"},
        )

    transport = httpx.MockTransport(handler)
    jobs = [DownloadJob(index=1, url="https://example.com/a.png")]

    with pytest.raises(DownloadError, match="non immagine"):
        _run(download_pages(jobs, output_dir=tmp_path, transport=transport))


def test_download_pages_rejects_empty_body(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"", headers={"content-type": "image/png"})

    transport = httpx.MockTransport(handler)
    jobs = [DownloadJob(index=1, url="https://example.com/a.png")]

    with pytest.raises(DownloadError, match="non immagine"):
        _run(download_pages(jobs, output_dir=tmp_path, transport=transport))


def test_download_pages_retries_on_429_then_succeeds(tmp_path: Path) -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] < 3:
            return httpx.Response(429, content=b"slow down")
        return httpx.Response(
            200,
            content=_real_image_bytes(fmt="PNG"),
            headers={"content-type": "image/png"},
        )

    transport = httpx.MockTransport(handler)
    jobs = [DownloadJob(index=1, url="https://example.com/page.png")]

    # Patch the backoff so the test stays fast.
    from msrt.scrape import downloader as dl_mod

    real_sleep = asyncio.sleep

    async def instant_sleep(seconds: float) -> None:
        await real_sleep(0)

    original = dl_mod.asyncio.sleep
    dl_mod.asyncio.sleep = instant_sleep  # type: ignore[assignment]
    try:
        files = _run(download_pages(jobs, output_dir=tmp_path, transport=transport))
    finally:
        dl_mod.asyncio.sleep = original  # type: ignore[assignment]

    assert attempts["count"] == 3
    assert len(files) == 1


def test_download_pages_raises_on_non_retryable_status(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, content=b"not found")

    transport = httpx.MockTransport(handler)
    jobs = [DownloadJob(index=1, url="https://example.com/missing.png")]

    with pytest.raises(DownloadError, match="HTTP 404"):
        _run(download_pages(jobs, output_dir=tmp_path, transport=transport))


def test_download_pages_retries_on_cloudflare_520_then_succeeds(tmp_path: Path) -> None:
    """Regression: the overnight Wistoria run lost ch.8 / ch.15 to a
    transient HTTP 520 from MangaFire's CDN. Cloudflare 520-524 must
    be retryable like the other 5xx codes."""

    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(520, content=b"<!DOCTYPE html>")
        return httpx.Response(
            200,
            content=_real_image_bytes(fmt="PNG"),
            headers={"content-type": "image/png"},
        )

    transport = httpx.MockTransport(handler)
    jobs = [DownloadJob(index=1, url="https://5w0.example/a.png")]

    from msrt.scrape import downloader as dl_mod

    real_sleep = asyncio.sleep

    async def instant_sleep(seconds: float) -> None:
        await real_sleep(0)

    original = dl_mod.asyncio.sleep
    dl_mod.asyncio.sleep = instant_sleep  # type: ignore[assignment]
    try:
        files = _run(download_pages(jobs, output_dir=tmp_path, transport=transport))
    finally:
        dl_mod.asyncio.sleep = original  # type: ignore[assignment]

    assert attempts["count"] == 2
    assert len(files) == 1


def test_download_pages_summarises_html_error_body(tmp_path: Path) -> None:
    """Non-retryable HTML responses (e.g. a hard 404 returning the
    site's full error page) must NOT leak the HTML into the error
    message — that string ends up in manifests, diagnostics and UI."""

    big_html = (
        "<!DOCTYPE html><html><head><title>blocked</title></head>"
        "<body>" + ("padding " * 50) + "</body></html>"
    ).encode("utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, content=big_html, headers={"content-type": "text/html"})

    transport = httpx.MockTransport(handler)
    jobs = [DownloadJob(index=1, url="https://example.com/a.png")]

    with pytest.raises(DownloadError) as info:
        _run(download_pages(jobs, output_dir=tmp_path, transport=transport))
    msg = str(info.value)
    assert "HTTP 403" in msg
    assert "[HTML " in msg  # summarised
    assert "<!DOCTYPE html>" not in msg  # not leaked verbatim


def test_download_pages_keeps_results_in_index_order(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_real_image_bytes(fmt="PNG"),
            headers={"content-type": "image/png"},
        )

    transport = httpx.MockTransport(handler)
    jobs = [
        DownloadJob(index=10, url="https://example.com/j.png"),
        DownloadJob(index=2, url="https://example.com/b.png"),
        DownloadJob(index=1, url="https://example.com/a.png"),
    ]

    files = _run(download_pages(jobs, output_dir=tmp_path, transport=transport))

    assert [f.index for f in files] == [1, 2, 10]


def test_find_duplicate_pages_flags_identical_sha(tmp_path: Path) -> None:
    payload = _real_image_bytes(fmt="PNG")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload, headers={"content-type": "image/png"})

    transport = httpx.MockTransport(handler)
    jobs = [
        DownloadJob(index=1, url="https://example.com/a.png"),
        DownloadJob(index=2, url="https://example.com/b.png"),
    ]

    files = _run(download_pages(jobs, output_dir=tmp_path, transport=transport))
    warnings = find_duplicate_pages(files)

    assert len(warnings) == 1
    assert "duplicata" in warnings[0]


def test_download_pages_empty_input_returns_empty_list(tmp_path: Path) -> None:
    files = _run(download_pages([], output_dir=tmp_path))

    assert files == []


def test_download_pages_per_host_rate_limit_paces_requests(tmp_path: Path) -> None:
    """``min_delay_per_host`` must keep at least N seconds between two
    requests to the *same* host, even when concurrency would allow them
    to fire simultaneously."""

    timestamps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        timestamps.append(asyncio.get_running_loop().time())
        return httpx.Response(
            200,
            content=_real_image_bytes(fmt="PNG"),
            headers={"content-type": "image/png"},
        )

    transport = httpx.MockTransport(handler)
    jobs = [DownloadJob(index=i, url=f"https://example.com/p{i}.png") for i in range(1, 4)]

    files = _run(
        download_pages(
            jobs,
            output_dir=tmp_path,
            transport=transport,
            min_delay_per_host=0.05,
            concurrency=8,
        )
    )

    assert len(files) == 3
    # Adjacent requests separated by at least the configured delay.
    deltas = [b - a for a, b in itertools.pairwise(timestamps)]
    assert all(d >= 0.04 for d in deltas), f"rate-limit not enforced: deltas={deltas}"


def test_download_pages_rate_limit_does_not_block_other_hosts(tmp_path: Path) -> None:
    """Requests across different hosts should not serialise on each
    other's rate limiter."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_real_image_bytes(fmt="PNG"),
            headers={"content-type": "image/png"},
        )

    transport = httpx.MockTransport(handler)
    jobs = [
        DownloadJob(index=1, url="https://host-a.example.com/p.png"),
        DownloadJob(index=2, url="https://host-b.example.com/p.png"),
        DownloadJob(index=3, url="https://host-c.example.com/p.png"),
    ]

    files = _run(
        download_pages(
            jobs,
            output_dir=tmp_path,
            transport=transport,
            min_delay_per_host=0.5,
            concurrency=8,
        )
    )

    assert [f.index for f in files] == [1, 2, 3]
