from __future__ import annotations

import hashlib
import http.cookiejar
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import BinaryIO, Callable


USER_AGENT = "aim59-compat/0.1"
MAX_INSTALLER_SIZE = 64 * 1024 * 1024


class DownloadError(RuntimeError):
    pass


class _OldVersionFormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.action: str | None = None
        self.csrf: str | None = None
        self._in_download_form = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "form":
            action = values.get("action") or ""
            self._in_download_form = "/software/download/" in action
            if self._in_download_form:
                self.action = action
        elif tag == "input" and self._in_download_form:
            if values.get("name") == "csrfmiddlewaretoken":
                self.csrf = values.get("value")

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self._in_download_form = False


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _copy_response(
    response: BinaryIO,
    destination: Path,
    progress: Callable[[int], None] | None,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    received = 0
    temporary = destination.with_suffix(destination.suffix + ".part")
    try:
        with temporary.open("wb") as output:
            while True:
                block = response.read(128 * 1024)
                if not block:
                    break
                received += len(block)
                if received > MAX_INSTALLER_SIZE:
                    raise DownloadError("Download exceeded the 64 MiB safety limit")
                output.write(block)
                if progress:
                    progress(received)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _opener() -> urllib.request.OpenerDirector:
    cookies = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))


def download_direct(
    url: str,
    destination: Path,
    progress: Callable[[int], None] | None = None,
) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise DownloadError("Installer URLs must use HTTP or HTTPS")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            _copy_response(response, destination, progress)
    except (OSError, urllib.error.URLError) as exc:
        raise DownloadError(f"Download failed: {exc}") from exc


def download_oldversion(
    page_url: str,
    destination: Path,
    progress: Callable[[int], None] | None = None,
) -> None:
    opener = _opener()
    page_request = urllib.request.Request(page_url, headers={"User-Agent": USER_AGENT})
    try:
        with opener.open(page_request, timeout=60) as response:
            page = response.read(2 * 1024 * 1024).decode("utf-8", errors="replace")
    except (OSError, urllib.error.URLError) as exc:
        raise DownloadError(f"Could not load OldVersion page: {exc}") from exc

    parser = _OldVersionFormParser()
    parser.feed(page)
    if not parser.action or not parser.csrf:
        raise DownloadError("OldVersion download form was not found; the site may have changed")

    endpoint = urllib.parse.urljoin(page_url, parser.action)
    body = urllib.parse.urlencode({"csrfmiddlewaretoken": parser.csrf}).encode("ascii")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": page_url,
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with opener.open(request, timeout=120) as response:
            _copy_response(response, destination, progress)
    except (OSError, urllib.error.URLError) as exc:
        raise DownloadError(f"OldVersion download failed: {exc}") from exc


def terminal_progress(received: int) -> None:
    if sys.stderr.isatty():
        mib = received / (1024 * 1024)
        print(f"\r  Downloaded {mib:5.1f} MiB", end="", file=sys.stderr, flush=True)
