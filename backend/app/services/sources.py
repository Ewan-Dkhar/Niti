"""Live government source feeds: PIB RSS and myScheme search.

Both feeds are public but undocumented/shape-shifting, so requests are cached,
normalized, and allowed to fail independently. No sample data is substituted:
if a source is unreachable the response says so and returns whatever the other
source produced.
"""

from __future__ import annotations

import html
import logging
import re
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from typing import Generic, TypeVar

import httpx

from app.core.config import Settings, get_settings
from app.schemas import SourceItem

logger = logging.getLogger(__name__)

MYSCHEME_SCHEMES_URL = "https://www.myscheme.gov.in/api/apisetu/schemes"
PIB_RSS_URL = "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3"
MYSCHEME_BASE_URL = "https://www.myscheme.gov.in/schemes"
DEFAULT_TIMEOUT_SEC = 20.0
DEFAULT_TTL_SEC = 900
USER_AGENT = "Niti/0.1 (civic policy explainer; contact: local dev)"

T = TypeVar("T")


class SourceError(RuntimeError):
    """A live source could not be refreshed."""


class TTLCache(Generic[T]):
    def __init__(self, ttl_sec: int) -> None:
        self.ttl_sec = ttl_sec
        self._entries: dict[str, tuple[float, T]] = {}

    def get(self, key: str) -> T | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        stored_at, value = entry
        if time.monotonic() - stored_at > self.ttl_sec:
            self._entries.pop(key, None)
            return None
        return value

    def set(self, key: str, value: T) -> T:
        self._entries[key] = (time.monotonic(), value)
        return value

    def clear(self) -> None:
        self._entries.clear()


_scheme_cache: TTLCache[list[SourceItem]] = TTLCache(DEFAULT_TTL_SEC)
_pib_cache: TTLCache[list[SourceItem]] = TTLCache(DEFAULT_TTL_SEC)


def clear_source_cache() -> None:
    _scheme_cache.clear()
    _pib_cache.clear()


def _http_client(client: httpx.Client | None, timeout: float) -> tuple[httpx.Client, bool]:
    if client is not None:
        return client, False
    return httpx.Client(timeout=timeout, follow_redirects=True), True


def _strip_html(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _get(client: httpx.Client, url: str) -> httpx.Response:
    response = client.get(url, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response


def _parse_pib(xml_text: str) -> list[SourceItem]:
    xml_text = xml_text.lstrip("\ufeff").strip()
    root = ET.fromstring(xml_text)
    items: list[SourceItem] = []
    for node in root.iter("item"):
        title = _strip_html(node.findtext("title"))
        link = (node.findtext("link") or "").strip()
        if not title or not link:
            continue
        items.append(
            SourceItem(
                source="pib",
                title=title,
                url=link,
                summary=_strip_html(node.findtext("description")),
                published_at=(node.findtext("pubDate") or "").strip() or None,
            )
        )
    return items


def fetch_pib_updates(
    *,
    limit: int = 20,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
) -> list[SourceItem]:
    """Return the latest PIB releases from the live RSS feed."""
    settings = settings or get_settings()
    cached = _pib_cache.get("pib")
    if cached is None:
        http, owned = _http_client(client, DEFAULT_TIMEOUT_SEC)
        try:
            response = _get(http, settings.pib_rss_url)
            items = _parse_pib(response.text)
        except (httpx.HTTPError, ET.ParseError) as exc:
            logger.warning("PIB RSS refresh failed: %s", exc)
            raise SourceError(f"PIB RSS unavailable: {exc}") from exc
        finally:
            if owned:
                http.close()
        if not items:
            raise SourceError("PIB RSS returned no items")
        cached = _pib_cache.set("pib", items)
    return cached[:limit]


def _load_schemes(
    *,
    settings: Settings,
    client: httpx.Client | None,
) -> list[SourceItem]:
    cached = _scheme_cache.get("schemes")
    if cached is not None:
        return cached

    http, owned = _http_client(client, DEFAULT_TIMEOUT_SEC)
    try:
        response = _get(http, settings.myscheme_api_url)
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("myScheme refresh failed: %s", exc)
        raise SourceError(f"myScheme unavailable: {exc}") from exc
    finally:
        if owned:
            http.close()

    items: list[SourceItem] = []
    for entry in payload.get("data") or []:
        slug = entry.get("slug")
        details = (entry.get("en") or {}).get("basicDetails") or {}
        name = (details.get("schemeName") or "").strip()
        if not slug or not name:
            continue
        items.append(
            SourceItem(
                source="myscheme",
                title=name,
                url=f"{MYSCHEME_BASE_URL}/{slug}",
                summary=(details.get("schemeShortTitle") or "").strip() or None,
            )
        )

    if not items:
        raise SourceError("myScheme returned no schemes")
    return _scheme_cache.set("schemes", items)


def _score(query_tokens: list[str], item: SourceItem) -> int:
    haystack = f"{item.title} {item.summary or ''}".lower()
    return sum(1 for token in query_tokens if token in haystack)


def search_myscheme(
    query: str = "",
    *,
    limit: int = 20,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
) -> list[SourceItem]:
    """Search the live myScheme catalogue locally after one cached fetch."""
    settings = settings or get_settings()
    items = _load_schemes(settings=settings, client=client)
    tokens = [token for token in re.split(r"\W+", query.lower()) if len(token) > 2]
    if not tokens:
        return items[:limit]
    scored = [(_score(tokens, item), item) for item in items]
    matches = [item for score, item in scored if score > 0]
    matches.sort(key=lambda item: (-_score(tokens, item), item.title.lower()))
    return matches[:limit]


def collect_sources(
    query: str = "",
    *,
    limit: int = 10,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
    pib_fetcher: Callable[..., list[SourceItem]] = fetch_pib_updates,
    scheme_fetcher: Callable[..., list[SourceItem]] = search_myscheme,
) -> tuple[list[SourceItem], list[str]]:
    """Fetch both sources, returning items plus per-source error messages."""
    items: list[SourceItem] = []
    errors: list[str] = []

    try:
        if query.strip():
            items.extend(scheme_fetcher(query, limit=limit, settings=settings, client=client))
        else:
            items.extend(scheme_fetcher("", limit=limit, settings=settings, client=client))
    except SourceError as exc:
        errors.append(str(exc))

    try:
        pib_items = pib_fetcher(limit=max(limit, 10), settings=settings, client=client)
        if query.strip():
            tokens = [token for token in re.split(r"\W+", query.lower()) if len(token) > 2]
            pib_items = [item for item in pib_items if _score(tokens, item) > 0]
        items.extend(pib_items[:limit])
    except SourceError as exc:
        errors.append(str(exc))

    return items, errors
