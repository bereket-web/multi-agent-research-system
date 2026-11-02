"""CLI for a bounded live run or a deterministic offline demonstration."""

from __future__ import annotations

import argparse
import sys

from .demo import demo_report
from .orchestrator import ResearchOrchestrator
from .render import to_json, to_markdown
from .web import DuckDuckGoSearch, SafePageFetcher


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a bounded, evidence-led multi-agent research brief.")
    parser.add_argument("question", nargs="?", help="Research question (omit when using --demo)")
    parser.add_argument("--demo", action="store_true", help="Use bundled fictional evidence; makes no network requests")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of Markdown")
    parser.add_argument("--max-results", type=int, default=5, help="Results per search intent (hard cap: 8)")
    parser.add_argument("--max-pages", type=int, default=5, help="Pages to fetch (hard cap: 6)")
    args = parser.parse_args(argv)
    if args.demo:
        report = demo_report()
    elif args.question:
        report = ResearchOrchestrator(DuckDuckGoSearch(), SafePageFetcher()).run(
            args.question, max_results=args.max_results, max_pages=args.max_pages
        )
    else:
        parser.error("provide a research question or use --demo")
    print(to_json(report) if args.json else to_markdown(report))
    return 0 if report.review.passed else 2


if __name__ == "__main__":
    sys.exit(main())
