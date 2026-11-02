"""Coordinator that routes artifacts between independently scoped specialist roles."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from .agents import AnalystAgent, FactCheckerAgent, ResearcherAgent, ReviewerAgent, WriterAgent
from .models import AgentEvent, PageFetcher, ResearchReport, SearchClient


class ResearchOrchestrator:
    """Runs a bounded research graph and refuses to emit findings after failed review."""

    def __init__(self, search: SearchClient, fetcher: PageFetcher) -> None:
        self.researcher = ResearcherAgent(search, fetcher)
        self.analyst = AnalystAgent()
        self.fact_checker = FactCheckerAgent()
        self.writer = WriterAgent()
        self.reviewer = ReviewerAgent()

    def run(self, question: str, max_results: int = 5, max_pages: int = 5) -> ResearchReport:
        clean_question = " ".join(question.split())
        if not clean_question:
            raise ValueError("Research question must not be empty")
        events: list[AgentEvent] = []
        warnings: list[str] = []

        tasks = self.researcher.plan(clean_question)
        events.append(
            AgentEvent(
                "orchestrator",
                "plan",
                1,
                len(tasks),
                "Assigned a three-worker budget: broad coverage, primary sources, and counterevidence.",
            )
        )
        # Workers execute different evidence-seeking mandates concurrently. Their
        # outputs are kept in planned order so reports remain deterministic.
        with ThreadPoolExecutor(max_workers=min(3, len(tasks))) as pool:
            worker_results = list(pool.map(lambda task: self.researcher.search_task(task, max_results), tasks))
        hits = []
        seen_urls: set[str] = set()
        role_names = ("coverage_researcher", "primary_source_researcher", "counterevidence_researcher")
        for index, (task, (task_hits, task_warnings)) in enumerate(zip(tasks, worker_results, strict=True)):
            warnings.extend(task_warnings)
            unique_hits = []
            for hit in task_hits:
                if hit.url not in seen_urls:
                    seen_urls.add(hit.url)
                    unique_hits.append(hit)
                    hits.append(hit)
            events.append(
                AgentEvent(
                    role_names[index], "search", 1, len(unique_hits), f"Mandate: {task.purpose}; query: {task.query}"
                )
            )
        evidence, fetch_warnings = self.researcher.fetch_hits(hits, max_pages=max_pages)
        warnings.extend(fetch_warnings)
        events.append(
            AgentEvent(
                "researcher_coordinator",
                "fetch_and_assign_ids",
                len(hits),
                len(evidence),
                "Fetched a bounded unique-page set and assigned source IDs in application code.",
            )
        )

        candidates = self.analyst.analyze(clean_question, evidence)
        events.append(
            AgentEvent(
                "analyst",
                "extract_candidates",
                len(evidence),
                len(candidates),
                "Selected relevant sentences verbatim; candidates are not treated as verified facts.",
            )
        )

        assessments = self.fact_checker.assess(candidates, evidence)
        events.append(
            AgentEvent(
                "fact_checker",
                "screen_claims",
                len(candidates),
                len(assessments),
                "Checked exact/overlap support and heuristic conflicts across retrieved excerpts.",
            )
        )

        draft = self.writer.draft(clean_question, candidates, assessments)
        events.append(
            AgentEvent(
                "writer",
                "write_cited_draft",
                len(assessments),
                len(draft.findings),
                "Included only single-source or multi-URL text matches; disputed/unverified claims excluded.",
            )
        )

        review = self.reviewer.review(draft, evidence, assessments)
        events.append(
            AgentEvent(
                "reviewer",
                "audit_draft",
                len(draft.findings),
                len(draft.findings),
                "Independently checked source IDs, exact excerpt provenance, and fact-check status.",
            )
        )
        final_findings = draft.findings
        excluded = draft.excluded_claim_ids
        if not review.passed:
            warnings.extend(review.errors)
            # Fail closed: no finding reaches the final report if structural review fails.
            final_findings = ()
            excluded = tuple(dict.fromkeys((*excluded, *(finding.claim_id for finding in draft.findings))))
            events.append(
                AgentEvent(
                    "orchestrator",
                    "fail_closed",
                    len(draft.findings),
                    0,
                    "Reviewer rejected the draft; findings withheld instead of bypassing the gate.",
                )
            )
        if review.warnings:
            warnings.extend(review.warnings)
        return ResearchReport(
            question=clean_question,
            tasks=tuple(tasks),
            evidence=tuple(evidence),
            candidates=tuple(candidates),
            assessments=tuple(assessments),
            findings=tuple(final_findings),
            excluded_claim_ids=tuple(excluded),
            review=review,
            events=tuple(events),
            warnings=tuple(dict.fromkeys(warnings)),
        )
