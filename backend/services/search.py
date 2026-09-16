"""Search adapter. It returns only retrieved search-result metadata, never invented evidence."""

from __future__ import annotations

import html
import re
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx

from backend.config import settings
from backend.schemas.messages import Source


class SearchService:
    """Minimal replaceable web-search adapter using DuckDuckGo's HTML results."""

    async def search(self, query: str, limit: int | None = None) -> list[Source]:
        result_limit = limit or settings.search.max_results
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        try:
            async with httpx.AsyncClient(timeout=settings.search.timeout_seconds, follow_redirects=True) as client:
                response = await client.get(url, headers={"User-Agent": "WikiCurator/1.0"})
                response.raise_for_status()
        except httpx.HTTPError:
            return []

        pattern = re.compile(
            r'class="result__a"[^>]*href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>.*?'
            r'class="result__snippet"[^>]*>(?P<snippet>.*?)</(?:a|div)>',
            re.S,
        )
        sources: list[Source] = []
        seen: set[str] = set()
        for match in pattern.finditer(response.text):
            source_url = html.unescape(match.group("url"))
            if "duckduckgo.com/l/?" in source_url:
                source_url = parse_qs(urlparse(source_url).query).get("uddg", [""])[0]
                source_url = unquote(source_url)
            source_url = re.sub(r"<.*?>", "", source_url).strip()
            title = re.sub(r"<.*?>", "", html.unescape(match.group("title"))).strip()
            snippet = re.sub(r"<.*?>", "", html.unescape(match.group("snippet"))).strip()
            domain = urlparse(source_url).netloc.lower()
            if not source_url.startswith(("https://", "http://")) or not domain or source_url in seen:
                continue
            seen.add(source_url)
            sources.append(Source(title=title or domain, url=source_url, snippet=snippet, domain=domain))
            if len(sources) >= result_limit:
                break
        return sources
