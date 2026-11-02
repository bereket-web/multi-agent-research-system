"""Offline synthetic scenario demonstrating support, corroboration, and conflict handling."""

from __future__ import annotations

from .models import Page, SearchHit
from .orchestrator import ResearchOrchestrator


class DemoSearch:
    def search(self, query: str, max_results: int) -> list[SearchHit]:
        records = [
            ("https://example.org/bluebird-a", "Bluebird Observatory — fictional record A"),
            ("https://example.org/bluebird-b", "Bluebird Observatory — fictional record B"),
            ("https://example.org/bluebird-c", "Bluebird Observatory — fictional record C"),
        ]
        return [
            SearchHit(title=title, url=url, snippet="Synthetic demonstration only.", query=query)
            for url, title in records[:max_results]
        ]


class DemoFetcher:
    TEXT = {
        "https://example.org/bluebird-a": (
            "Bluebird Observatory — fictional record A",
            "In this fictional portfolio example, Bluebird Observatory opened in 2018. "
            "The fictional observatory records twelve sky events each month.",
        ),
        "https://example.org/bluebird-b": (
            "Bluebird Observatory — fictional record B",
            "For this fictional portfolio example, Bluebird Observatory opened in 2018. "
            "Its fictional catalog is published each June.",
        ),
        "https://example.org/bluebird-c": (
            "Bluebird Observatory — fictional record C",
            "In this fictional portfolio example, Bluebird Observatory opened in 2019. "
            "The fictional observatory records twelve sky events each month.",
        ),
    }

    def fetch(self, url: str) -> Page:
        title, text = self.TEXT[url]
        return Page(title=title, text=text, retrieved_at="synthetic fixture; no network request")


def demo_report():
    return ResearchOrchestrator(DemoSearch(), DemoFetcher()).run(
        "What is known about the fictional Bluebird Observatory and its opening date?", max_results=3, max_pages=3
    )
