"""Tests for PIB RSS parsing, myScheme search, caching, and failure handling."""

import httpx
import pytest

from app.services.sources import (
    SourceError,
    clear_source_cache,
    collect_sources,
    fetch_pib_updates,
    search_myscheme,
)

PIB_XML = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel><title>Press Information Bureau</title>
<item>
  <title>Cabinet approves pension scheme for farmers</title>
  <link>https://pib.gov.in/PressReleasePage.aspx?PRID=1</link>
  <description><![CDATA[<p>The Union Cabinet approved a pension scheme.</p>]]></description>
  <pubDate>Fri, 30 Oct 2026 10:00:00 GMT</pubDate>
</item>
<item>
  <title>Health ministry releases guidelines</title>
  <link>https://pib.gov.in/PressReleasePage.aspx?PRID=2</link>
  <description>New guidelines for hospitals.</description>
  <pubDate>Thu, 29 Oct 2026 10:00:00 GMT</pubDate>
</item>
</channel></rss>
"""

SCHEMES_JSON = {
    "status": "success",
    "data": [
        {
            "_id": "1",
            "slug": "pm-kisan",
            "en": {"basicDetails": {"schemeName": "Pradhan Mantri Kisan Samman Nidhi"}},
        },
        {
            "_id": "2",
            "slug": "kcc",
            "en": {"basicDetails": {"schemeName": "Kisan Credit Card"}},
        },
        {
            "_id": "3",
            "slug": "nssw",
            "en": {"basicDetails": {"schemeName": "New Swarnima Scheme For Women"}},
        },
    ],
}


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    clear_source_cache()
    yield
    clear_source_cache()


def make_client(calls: dict[str, int] | None = None, fail: bool = False) -> httpx.Client:
    calls = calls if calls is not None else {}

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        calls[host] = calls.get(host, 0) + 1
        if fail:
            raise httpx.ConnectError("network down", request=request)
        if host == "pib.gov.in":
            return httpx.Response(200, text=PIB_XML)
        return httpx.Response(200, json=SCHEMES_JSON)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_pib_updates_normalizes_items() -> None:
    items = fetch_pib_updates(limit=5, client=make_client())

    assert len(items) == 2
    assert items[0].source == "pib"
    assert items[0].title == "Cabinet approves pension scheme for farmers"
    assert items[0].summary == "The Union Cabinet approved a pension scheme."
    assert items[0].published_at.startswith("Fri, 30 Oct 2026")


def test_pib_is_cached_between_calls() -> None:
    calls: dict[str, int] = {}
    client = make_client(calls)

    fetch_pib_updates(limit=5, client=client)
    fetch_pib_updates(limit=5, client=client)

    assert calls["pib.gov.in"] == 1


def test_search_myscheme_filters_by_query() -> None:
    items = search_myscheme("kisan", limit=10, client=make_client())

    assert [item.title for item in items] == [
        "Kisan Credit Card",
        "Pradhan Mantri Kisan Samman Nidhi",
    ]
    assert items[0].url == "https://www.myscheme.gov.in/schemes/kcc"


def test_search_myscheme_without_query_returns_catalogue_head() -> None:
    items = search_myscheme("", limit=2, client=make_client())

    assert len(items) == 2


def test_network_failure_raises_source_error() -> None:
    with pytest.raises(SourceError):
        fetch_pib_updates(limit=5, client=make_client(fail=True))


def test_collect_sources_returns_partial_results_when_one_source_fails() -> None:
    client = make_client()

    def broken_pib(**kwargs: object) -> list:
        raise SourceError("PIB RSS unavailable")

    items, errors = collect_sources("kisan", limit=5, client=client, pib_fetcher=broken_pib)

    assert errors == ["PIB RSS unavailable"]
    assert items
    assert all(item.source == "myscheme" for item in items)


def test_collect_sources_reports_both_failures() -> None:
    def broken(*args: object, **kwargs: object) -> list:
        raise SourceError("down")

    items, errors = collect_sources("kisan", limit=5, scheme_fetcher=broken, pib_fetcher=broken)

    assert items == []
    assert errors == ["down", "down"]
