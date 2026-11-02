"""Human-readable and machine-readable report renderers."""

from __future__ import annotations

import json
from dataclasses import asdict

from .models import ResearchReport


def to_markdown(report: ResearchReport) -> str:
    lines = [f"# Research brief: {report.question}", "", "## Evidence-screened findings", ""]
    if report.findings:
        for finding in report.findings:
            citations = ", ".join(f"[{source_id}]" for source_id in finding.source_ids)
            caveat = (
                " (one source; not independently corroborated)"
                if finding.status == "single_source"
                else " (matched across distinct URLs)"
            )
            lines.append(f"- {finding.text} {citations}{caveat}")
    else:
        lines.append("No findings passed the evidence and review gates. This is not evidence that no answer exists.")
    lines.extend(["", "## Sources", ""])
    if report.evidence:
        for item in report.evidence:
            lines.append(
                f"- **[{item.source_id}] [{item.title}]({item.url})** — retrieved {item.retrieved_at}; query: `{item.query}`"
            )
            lines.append(f"  - Excerpt: “{item.excerpt[:360]}{'…' if len(item.excerpt) > 360 else ''}”")
    else:
        lines.append("No pages were successfully fetched.")
    lines.extend(
        [
            "",
            "## What the checks mean",
            "",
            "The fact checker uses exact text and conservative token-overlap, numeric, and polarity heuristics. "
            "The reviewer checks citation provenance and gate status. Neither agent establishes truth, source authority, "
            "or logical entailment; read the linked sources before relying on a conclusion.",
            "",
            f"**Review:** {'passed' if report.review.passed else 'failed'}; "
            f"{report.review.checked_findings} finding(s) checked.",
        ]
    )
    if report.excluded_claim_ids:
        lines.extend(["", "## Excluded candidates", ""])
        assessments_by_id = {item.claim_id: item for item in report.assessments}
        for claim_id in report.excluded_claim_ids:
            assessment = assessments_by_id.get(claim_id)
            if assessment:
                lines.append(f"- **{claim_id} — {assessment.status}:** {assessment.text} — {assessment.rationale}")
            else:
                lines.append(f"- **{claim_id}:** withheld by the orchestrator after review failure.")
    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report.warnings)
    lines.extend(["", "## Agent trace", ""])
    for event in report.events:
        lines.append(
            f"- **{event.role} / {event.action}:** {event.input_count} in, {event.output_count} out — {event.note}"
        )
    return "\n".join(lines) + "\n"


def to_json(report: ResearchReport) -> str:
    return json.dumps(asdict(report), ensure_ascii=False, indent=2)
