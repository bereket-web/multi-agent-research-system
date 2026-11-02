"""Small standard-library web adapters with conservative URL and resource bounds."""

from __future__ import annotations

import ipaddress
import socket
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse, urlunparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .models import Page, SearchHit

USER_AGENT = "MultiAgentResearchPortfolio/0.1 (bounded public-page research)"
MAX_PAGE_BYTES = 1_000_000
TIMEOUT_SECONDS = 12


def validate_public_url(url: str, resolve: bool = True) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only absolute HTTP(S) URLs without embedded credentials are allowed")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost") or host.endswith(".local"):
        raise ValueError("Local hostnames are not allowed")
    if resolve:
        try:
            addresses = {
                entry[4][0]
                for entry in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
            }
        except OSError as exc:
            raise ValueError(f"Unable to resolve host: {host}") from exc
        for address in addresses:
            ip = ipaddress.ip_address(address.split("%", 1)[0])
            if not ip.is_global:
                raise ValueError(f"Non-public destination is not allowed: {host}")
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/", "", parsed.query, ""))


def _unwrap_result_url(raw_url: str) -> str:
    candidate = raw_url if ":" in raw_url else "https:" + raw_url
    parsed = urlparse(candidate)
    if parsed.hostname and parsed.hostname.endswith("duckduckgo.com") and parsed.path == "/l/":
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return target or candidate
    return candidate


class _SearchParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[dict[str, str]] = []
        self.in_link = False
        self.in_snippet = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        classes = (attr.get("class") or "").split()
        if tag == "a" and "result-link" in classes:
            href = attr.get("href") or ""
            self.items.append({"title": "", "url": _unwrap_result_url(href), "snippet": ""})
            self.in_link = True
        elif tag in {"td", "div"} and ({"result-snippet", "result__snippet"} & set(classes)) and self.items:
            self.in_snippet = True

    def handle_data(self, data: str) -> None:
        if self.in_link and self.items:
            self.items[-1]["title"] += data
        elif self.in_snippet and self.items:
            self.items[-1]["snippet"] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self.in_link = False
        if tag in {"td", "div"}:
            self.in_snippet = False


def _is_search_challenge(html: str) -> bool:
    lowered = html.casefold()
    return any(
        marker in lowered for marker in ("anomaly-modal", "complete the following challenge", "bots use duckduckgo")
    )


class DuckDuckGoSearch:
    """No-key DuckDuckGo Lite search. Its HTML is an unstable, best-effort interface."""

    endpoint = "https://lite.duckduckgo.com/lite/"

    def search(self, query: str, max_results: int = 5) -> list[SearchHit]:
        request = Request(
            self.endpoint + "?q=" + quote_plus(query[:220]), headers={"User-Agent": USER_AGENT, "Accept": "text/html"}
        )
        with build_opener().open(request, timeout=TIMEOUT_SECONDS) as response:
            status = getattr(response, "status", 200)
            html = response.read(700_000).decode("utf-8", errors="replace")
        if status != 200 or _is_search_challenge(html):
            raise RuntimeError(
                f"DuckDuckGo Lite search unavailable (HTTP {status}; provider challenge or non-success response)"
            )
        parser = _SearchParser()
        parser.feed(html)
        results: list[SearchHit] = []
        seen: set[str] = set()
        for item in parser.items:
            try:
                url = validate_public_url(item["url"], resolve=False)
            except ValueError:
                continue
            if url in seen:
                continue
            seen.add(url)
            results.append(
                SearchHit(
                    title=" ".join(item["title"].split()) or url,
                    url=url,
                    snippet=" ".join(item["snippet"].split()),
                    query=query,
                )
            )
            if len(results) >= max(1, min(max_results, 8)):
                break
        return results


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        target = validate_public_url(urljoin(req.full_url, newurl), resolve=True)
        return super().redirect_request(req, fp, code, msg, headers, target)


class _TextParser(HTMLParser):
    BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "br", "tr"}
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self.in_title = False
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP:
            self.skip_depth += 1
        elif tag == "title":
            self.in_title = True
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth -= 1
        elif tag == "title":
            self.in_title = False
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        clean = " ".join(data.split())
        if not clean:
            return
        if self.in_title:
            self.title_parts.append(clean)
        else:
            self.parts.append(clean)


class SafePageFetcher:
    """Fetches static public HTML only; limits redirects, timeout, and response bytes."""

    def fetch(self, url: str) -> Page:
        safe_url = validate_public_url(url, resolve=True)
        opener = build_opener(_SafeRedirectHandler())
        request = Request(safe_url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            content_type = response.headers.get("Content-Type", "").lower()
            if "html" not in content_type:
                raise ValueError(f"Unsupported content type: {content_type or 'unknown'}")
            payload = response.read(MAX_PAGE_BYTES + 1)
        if len(payload) > MAX_PAGE_BYTES:
            raise ValueError(f"Page exceeded {MAX_PAGE_BYTES} byte limit")
        parser = _TextParser()
        parser.feed(payload.decode("utf-8", errors="replace"))
        text = " ".join(" ".join(parser.parts).split())
        return Page(
            title=" ".join(parser.title_parts).strip(),
            text=text[:28_000],
            retrieved_at=datetime.now(timezone.utc).isoformat(),
        )
