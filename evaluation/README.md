# Synthetic ablation

Run `python evaluation/ablation.py` from the repository root. The script writes `ablation_results.json` and exits non-zero if any hand-labeled fixture status differs from the heuristic fact-checker's status.

The six cases exercise a clean single-source match, matching text at multiple URLs, an invented quantity, a conflicting year, a negation conflict, and an unrelated unsupported statement. The baseline publishes every proposed claim. The multi-agent path runs the fact-checker and writer allowlist before publication.

Interpret the numbers only as a narrow mechanism test. The passages and labels are original synthetic fixtures, not an external or representative benchmark. A matching phrase does not establish truth, entailment, source quality, or source independence; this test does not measure research coverage or claim-generation quality.
