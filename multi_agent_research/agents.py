"""Specialist agents. Each role has a narrow input/output contract and a separate policy."""

from __future__ import annotations

import re
from collections.abc import Sequence

from .models import (
    CandidateClaim,
    ClaimAssessment,
    Draft,
    Evidence,
    Finding,
    PageFetcher,
    ResearchTask,
    ReviewResult,
    SearchClient,
    SearchHit,
)

MAX_QUERIES = 3
MAX_RESULTS_PER_QUERY = 8
MAX_PAGES = 6
MAX_EXCERPT_CHARS = 2200
MAX_CLAIMS = 12

_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "in",
    "into",
    "is",
    "it",
    "its",
    "may",
    "might",
    "of",
    "on",
    "or",
    "our",
    "should",
    "that",
    "the",
    "their",
    "them",
    "there",
    "these",
    "this",
    "those",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "will",
    "with",
    "would",
    "you",
    "your",
}
_NEGATION = {"no", "not", "never", "neither", "nor", "without", "cannot", "n't"}
_OPPOSITES = (
    (
        {"increase", "increased", "increases", "rising", "rose", "higher", "up", "grew"},
        {"decrease", "decreased", "decreases", "falling", "fell", "lower", "down", "shrank"},
    ),
    (
        {"open", "opened", "launch", "launched", "start", "started", "begin", "began"},
        {"close", "closed", "end", "ended", "stop", "stopped"},
    ),
    (
        {"approve", "approved", "accept", "accepted", "allow", "allowed"},
        {"reject", "rejected", "deny", "denied", "prohibit", "prohibited"},
    ),
    ({"positive", "gain", "gained", "profit", "profitable"}, {"negative", "loss", "lost", "deficit", "unprofitable"}),
)


def tokenize(text: str) -> set[str]:
    # Negation is intentionally retained: removing it would make a major class of
    # contradictions look like agreement under token-overlap checks.
    return {token for token in re.findall(r"[a-z0-9']+", text.casefold()) if token not in _STOP_WORDS}


def _normalized(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [" ".join(part.split()) for part in parts if len(part.strip()) >= 35]


def _claim_overlap(left: str, right: str) -> float:
    claim_tokens = tokenize(left)
    if not claim_tokens:
        return 0.0
    return len(claim_tokens & tokenize(right)) / len(claim_tokens)


def _numeric_conflict(claim: str, sentence: str, shared_fraction: float) -> bool:
    claim_numbers = set(re.findall(r"\b\d{2,4}(?:[.,]\d+)?%?\b", claim))
    sentence_numbers = set(re.findall(r"\b\d{2,4}(?:[.,]\d+)?%?\b", sentence))
    if claim_numbers and sentence_numbers and claim_numbers.isdisjoint(sentence_numbers):
        claim_non_numeric = tokenize(re.sub(r"\b\d{2,4}(?:[.,]\d+)?%?\b", "", claim))
        sentence_non_numeric = tokenize(re.sub(r"\b\d{2,4}(?:[.,]\d+)?%?\b", "", sentence))
        return len(claim_non_numeric & sentence_non_numeric) / max(1, len(claim_non_numeric)) >= 0.72
    return False


def _polarity_conflict(claim: str, sentence: str, shared_fraction: float) -> bool:
    if shared_fraction < 0.68:
        return False
    claim_tokens = tokenize(claim)
    sentence_tokens = tokenize(sentence)
    claim_negative = bool(claim_tokens & _NEGATION)
    sentence_negative = bool(sentence_tokens & _NEGATION)
    if claim_negative != sentence_negative:
        return True
    for left, right in _OPPOSITES:
        if (claim_tokens & left and sentence_tokens & right) or (claim_tokens & right and sentence_tokens & left):
            return True
    return False


class ResearcherAgent:
    """Searches and fetches public-page evidence through injected tools."""

    def __init__(self, search: SearchClient, fetcher: PageFetcher) -> None:
        self.search_client = search
        self.fetcher = fetcher

    def plan(self, question: str) -> list[ResearchTask]:
        clean = " ".join(question.split())[:200]
        # The three workers have deliberately different evidence-seeking mandates.
        return [
            ResearchTask("independent coverage", clean),
            ResearchTask("primary or official sources", f"{clean} official primary source"),
            ResearchTask("counterevidence and limitations", f"{clean} limitations criticism contrary evidence"),
        ][:MAX_QUERIES]

    def search_task(self, task: ResearchTask, max_results: int = 5) -> tuple[list[SearchHit], list[str]]:
        bounded_results = max(1, min(int(max_results), MAX_RESULTS_PER_QUERY))
        try:
            hits = self.search_client.search(task.query, bounded_results)
            return list(hits)[:bounded_results], []
        except Exception as exc:  # adapter failures are reported, not hidden
            return [], [f"Search failed for {task.purpose}: {type(exc).__name__}: {exc}"]

    def fetch_hits(self, hits: Sequence[SearchHit], max_pages: int = 5) -> tuple[list[Evidence], list[str]]:
        bounded_pages = max(1, min(int(max_pages), MAX_PAGES))
        evidence: list[Evidence] = []
        warnings: list[str] = []
        for hit in list(hits)[:bounded_pages]:
            try:
                page = self.fetcher.fetch(hit.url)
                excerpt = " ".join(page.text.split())[:MAX_EXCERPT_CHARS]
                if not excerpt:
                    warnings.append(f"No readable text extracted from {hit.url}")
                    continue
                evidence.append(
                    Evidence(
                        source_id=f"S{len(evidence) + 1}",
                        title=page.title or hit.title,
                        url=hit.url,
                        query=hit.query,
                        excerpt=excerpt,
                        retrieved_at=page.retrieved_at,
                    )
                )
            except Exception as exc:  # one bad page must not discard remaining evidence
                warnings.append(f"Fetch failed for {hit.url}: {type(exc).__name__}: {exc}")
        return evidence, warnings


class AnalystAgent:
    """Produces source-linked candidate claims by selecting relevant exact sentences."""

    def analyze(self, question: str, evidence: Sequence[Evidence], limit: int = MAX_CLAIMS) -> list[CandidateClaim]:
        question_tokens = tokenize(question)
        ranked: list[tuple[float, int, str, Evidence]] = []
        seen: set[str] = set()
        for evidence_index, item in enumerate(evidence):
            for sentence in _sentences(item.excerpt):
                normalized = _normalized(sentence)
                if normalized in seen:
                    continue
                seen.add(normalized)
                tokens = tokenize(sentence)
                if not tokens:
                    continue
                overlap = len(tokens & question_tokens) / max(1, len(question_tokens))
                if overlap > 0:
                    ranked.append((overlap, evidence_index, sentence, item))
        ranked.sort(key=lambda row: (-row[0], row[1], row[2]))
        candidates: list[CandidateClaim] = []
        for score, _, sentence, item in ranked[: max(1, min(limit, MAX_CLAIMS))]:
            candidates.append(
                CandidateClaim(
                    claim_id=f"C{len(candidates) + 1}",
                    text=sentence,
                    source_ids=(item.source_id,),
                    relevance=round(score, 4),
                )
            )
        return candidates


class FactCheckerAgent:
    """Independently checks proposed claims against all retrieved excerpts.

    Similarity and opposition rules are conservative screening heuristics, not
    natural-language entailment or a determination of truth.
    """

    def assess(self, candidates: Sequence[CandidateClaim], evidence: Sequence[Evidence]) -> list[ClaimAssessment]:
        known_ids = {item.source_id for item in evidence}
        assessments: list[ClaimAssessment] = []
        for candidate in candidates:
            supported: set[str] = set()
            conflicts: set[str] = set()
            normalized_claim = _normalized(candidate.text)
            for item in evidence:
                normalized_excerpt = _normalized(item.excerpt)
                exact = bool(normalized_claim and normalized_claim in normalized_excerpt)
                overlap = _claim_overlap(candidate.text, item.excerpt)
                if exact or overlap >= 0.78:
                    supported.add(item.source_id)
                for sentence in _sentences(item.excerpt):
                    if _normalized(sentence) == normalized_claim:
                        continue
                    sentence_overlap = _claim_overlap(candidate.text, sentence)
                    if _numeric_conflict(candidate.text, sentence, sentence_overlap) or _polarity_conflict(
                        candidate.text, sentence, sentence_overlap
                    ):
                        conflicts.add(item.source_id)
                        break
            invalid_ids = tuple(sorted(set(candidate.source_ids) - known_ids))
            if conflicts:
                status = "disputed"
                rationale = (
                    "A separate excerpt triggers a numeric or polarity opposition heuristic; human review is needed."
                )
            elif len({item.url for item in evidence if item.source_id in supported}) >= 2:
                status = "multi_source_match"
                rationale = "Close text appears at multiple URLs; this does not establish source independence or truth."
            elif supported:
                status = "single_source"
                rationale = "One retrieved excerpt contains a close textual match; independent corroboration was not established."
            else:
                status = "unverified"
                rationale = "No retrieved excerpt passed the exact-match or conservative token-overlap screen."
            warnings = (f"Candidate cited unknown source IDs: {', '.join(invalid_ids)}",) if invalid_ids else ()
            assessments.append(
                ClaimAssessment(
                    claim_id=candidate.claim_id,
                    text=candidate.text,
                    status=status,
                    supported_by=tuple(sorted(supported)),
                    potentially_conflicting_with=tuple(sorted(conflicts)),
                    citation_warnings=warnings,
                    rationale=rationale,
                )
            )
        return assessments


class WriterAgent:
    """Writes only claims allowed by the fact-check policy, with visible provenance."""

    ALLOWED_STATUSES = {"single_source", "multi_source_match"}

    def draft(
        self, question: str, candidates: Sequence[CandidateClaim], assessments: Sequence[ClaimAssessment]
    ) -> Draft:
        candidate_ids = {candidate.claim_id for candidate in candidates}
        assessment_by_id = {assessment.claim_id: assessment for assessment in assessments}
        findings: list[Finding] = []
        excluded: list[str] = []
        for candidate in candidates:
            assessment = assessment_by_id.get(candidate.claim_id)
            if assessment and assessment.status in self.ALLOWED_STATUSES and assessment.supported_by:
                findings.append(
                    Finding(
                        claim_id=candidate.claim_id,
                        text=candidate.text,
                        status=assessment.status,
                        source_ids=assessment.supported_by,
                    )
                )
            else:
                excluded.append(candidate.claim_id)
        excluded.extend(sorted(set(assessment_by_id) - candidate_ids))
        return Draft(
            title=f"Research brief: {question.strip()}",
            findings=tuple(findings),
            excluded_claim_ids=tuple(dict.fromkeys(excluded)),
        )


class ReviewerAgent:
    """Audits report claims and citations independently before they leave the pipeline."""

    def review(
        self, draft: Draft, evidence: Sequence[Evidence], assessments: Sequence[ClaimAssessment]
    ) -> ReviewResult:
        evidence_by_id = {item.source_id: item for item in evidence}
        assessment_by_id = {item.claim_id: item for item in assessments}
        errors: list[str] = []
        warnings: list[str] = []
        seen_claim_ids: set[str] = set()
        for finding in draft.findings:
            if finding.claim_id in seen_claim_ids:
                errors.append(f"Duplicate finding ID: {finding.claim_id}")
            seen_claim_ids.add(finding.claim_id)
            if not finding.source_ids:
                errors.append(f"Finding {finding.claim_id} has no citations")
            assessment = assessment_by_id.get(finding.claim_id)
            if not assessment or assessment.status not in WriterAgent.ALLOWED_STATUSES:
                errors.append(f"Finding {finding.claim_id} did not pass the fact-check gate")
            for source_id in finding.source_ids:
                item = evidence_by_id.get(source_id)
                if not item:
                    errors.append(f"Finding {finding.claim_id} cites unknown source {source_id}")
                elif _normalized(finding.text) not in _normalized(item.excerpt):
                    errors.append(f"Finding {finding.claim_id} is not an exact excerpt from {source_id}")
            if assessment and assessment.citation_warnings:
                warnings.extend(assessment.citation_warnings)
        return ReviewResult(
            passed=not errors,
            checked_findings=len(draft.findings),
            errors=tuple(errors),
            warnings=tuple(dict.fromkeys(warnings)),
        )
