"""Shared, deliberately small data contracts for the research team."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ResearchTask:
    purpose: str
    query: str


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    snippet: str
    query: str


@dataclass(frozen=True)
class Page:
    title: str
    text: str
    retrieved_at: str


@dataclass(frozen=True)
class Evidence:
    source_id: str
    title: str
    url: str
    query: str
    excerpt: str
    retrieved_at: str


@dataclass(frozen=True)
class CandidateClaim:
    claim_id: str
    text: str
    source_ids: tuple[str, ...]
    relevance: float = 0.0


@dataclass(frozen=True)
class ClaimAssessment:
    claim_id: str
    text: str
    status: str
    supported_by: tuple[str, ...]
    potentially_conflicting_with: tuple[str, ...]
    citation_warnings: tuple[str, ...] = ()
    rationale: str = ""


@dataclass(frozen=True)
class Finding:
    claim_id: str
    text: str
    status: str
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class Draft:
    title: str
    findings: tuple[Finding, ...]
    excluded_claim_ids: tuple[str, ...]


@dataclass(frozen=True)
class ReviewResult:
    passed: bool
    checked_findings: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class AgentEvent:
    role: str
    action: str
    input_count: int
    output_count: int
    note: str


@dataclass(frozen=True)
class ResearchReport:
    question: str
    tasks: tuple[ResearchTask, ...]
    evidence: tuple[Evidence, ...]
    candidates: tuple[CandidateClaim, ...]
    assessments: tuple[ClaimAssessment, ...]
    findings: tuple[Finding, ...]
    excluded_claim_ids: tuple[str, ...]
    review: ReviewResult
    events: tuple[AgentEvent, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)


class SearchClient(Protocol):
    def search(self, query: str, max_results: int) -> list[SearchHit]: ...


class PageFetcher(Protocol):
    def fetch(self, url: str) -> Page: ...
