"""Synthetic mechanism check: direct-publish baseline versus claim-screening gate.

This is not a benchmark of live web research or factual accuracy.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from multi_agent_research.agents import FactCheckerAgent, WriterAgent  # noqa: E402
from multi_agent_research.models import CandidateClaim, Evidence  # noqa: E402


@dataclass(frozen=True)
class Case:
    name: str
    claim: str
    excerpts: tuple[tuple[str, str, str], ...]  # source ID, URL, excerpt
    expected: str


CASES = (
    Case(
        "supported single source",
        "The fictional Aurora Observatory opened in 2020.",
        (("S1", "https://fixture.test/aurora", "The fictional Aurora Observatory opened in 2020."),),
        "single_source",
    ),
    Case(
        "same statement at multiple URLs",
        "The fictional Luma Lab publishes an annual report.",
        (
            ("S1", "https://fixture.test/luma-a", "The fictional Luma Lab publishes an annual report."),
            ("S2", "https://fixture.test/luma-b", "The fictional Luma Lab publishes an annual report."),
        ),
        "multi_source_match",
    ),
    Case(
        "invented quantity",
        "The fictional Aurora Observatory operates 300 telescopes.",
        (("S1", "https://fixture.test/aurora", "The fictional Aurora Observatory opened in 2020."),),
        "unverified",
    ),
    Case(
        "conflicting year",
        "The fictional Bluebird Observatory opened in 2018.",
        (
            ("S1", "https://fixture.test/bluebird-a", "The fictional Bluebird Observatory opened in 2018."),
            ("S2", "https://fixture.test/bluebird-b", "The fictional Bluebird Observatory opened in 2019."),
        ),
        "disputed",
    ),
    Case(
        "negation conflict",
        "The fictional trial reduced incidents by 18%.",
        (
            ("S1", "https://fixture.test/trial-a", "The fictional trial reduced incidents by 18%."),
            ("S2", "https://fixture.test/trial-b", "The fictional trial did not reduce incidents by 18%."),
        ),
        "disputed",
    ),
    Case(
        "unrelated unsupported claim",
        "The fictional route is powered by hydrogen.",
        (("S1", "https://fixture.test/aurora", "The fictional Aurora Observatory opened in 2020."),),
        "unverified",
    ),
)


def run() -> dict[str, object]:
    checker = FactCheckerAgent()
    writer = WriterAgent()
    outcomes = []
    baseline_problem_claims = 0
    gated_problem_claims = 0
    baseline_published = 0
    gated_published = 0
    for index, case in enumerate(CASES, start=1):
        evidence = tuple(
            Evidence(
                source_id=source_id,
                title=f"Synthetic {source_id}",
                url=url,
                query="synthetic evaluation",
                excerpt=excerpt,
                retrieved_at="synthetic fixture",
            )
            for source_id, url, excerpt in case.excerpts
        )
        candidate = CandidateClaim(
            claim_id=f"C{index}", text=case.claim, source_ids=(evidence[0].source_id,), relevance=1.0
        )
        assessment = checker.assess((candidate,), evidence)[0]
        draft = writer.draft("Synthetic fixture", (candidate,), (assessment,))
        baseline_published += 1  # A direct one-pass writer has no independent claim gate.
        baseline_problem = case.expected in {"unverified", "disputed"}
        baseline_problem_claims += int(baseline_problem)
        gated_accept = bool(draft.findings)
        gated_published += int(gated_accept)
        gated_problem_claims += int(gated_accept and baseline_problem)
        outcomes.append(
            {
                "case": case.name,
                "expected_gate_status": case.expected,
                "actual_gate_status": assessment.status,
                "gate_matches_expected": assessment.status == case.expected,
                "direct_publish_includes": True,
                "multi_agent_gate_includes": gated_accept,
                "supporting_source_ids": list(assessment.supported_by),
                "potential_conflict_source_ids": list(assessment.potentially_conflicting_with),
            }
        )
    return {
        "evaluation_type": "small, original synthetic mechanism check; not a real-world benchmark",
        "case_count": len(CASES),
        "direct_publish_baseline": {
            "published_claims": baseline_published,
            "known_unsupported_or_disputed_claims_included": baseline_problem_claims,
            "known_problem_inclusion_rate": baseline_problem_claims / max(1, baseline_published),
        },
        "multi_agent_screening_gate": {
            "published_claims": gated_published,
            "known_unsupported_or_disputed_claims_included": gated_problem_claims,
            "known_problem_inclusion_rate": gated_problem_claims / max(1, gated_published),
            "correct_status_cases": sum(bool(item["gate_matches_expected"]) for item in outcomes),
        },
        "scope_note": "The test isolates claim screening on supplied excerpts. It does not assess search recall, truth, entailment, source quality, or source independence.",
        "cases": outcomes,
    }


def main() -> int:
    results = run()
    out_path = Path(__file__).with_name("ablation_results.json")
    out_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))
    return 0 if all(item["gate_matches_expected"] for item in results["cases"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
