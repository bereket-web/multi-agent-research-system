# Design decisions

## Why a separate Project 08

Project 07 (`/workspace/open_research_agent`) already performs bounded search/fetch, extracts exact evidence, and produces cited reports. Project 08 keeps a portable implementation rather than importing Project 07 internals, then adds three independently scoped, concurrent researcher workers; a candidate-claim ledger; a separate claim-check stage; writer policy; reviewer audit; and fail-closed orchestration. The separation makes this repository runnable without Project 07 installed.

## Role contracts

| Role | Input | Output | Does not do |
|---|---|---|---|
| Orchestrator | Question and fixed limits | Three research mandates, stage trace, final routing decision | Decide factual claims |
| Coverage researcher | Broad query | Search hits for the question | Write report conclusions |
| Primary-source researcher | Official/primary query | Distinct search hits | Assume official means correct |
| Counterevidence researcher | Limitation/contrary query | Distinct search hits | Resolve disagreements by vote |
| Analyst | Evidence ledger | Exact-sentence candidate claims | Mark a claim true |
| Fact checker | Candidate claims + all excerpts | Support IDs, conflict IDs, status, rationale | Prove entailment or source independence |
| Writer | Screened claims | Cited draft and excluded-claim ledger | Add unsupported synthesis |
| Reviewer | Draft + ledger + gate results | Pass/fail with errors and warnings | Repair citations silently |

All role components are deterministic. This is an intentional first implementation: the meaningful distinction is scoped responsibilities and handoff gates, not calling the same LLM repeatedly under different labels. Reproducible fake-tool tests run with no credentials or network.

## Evidence and conflict policy

Source IDs are assigned by the application after successful fetch. Analyst claims are exact extracted sentences. Only exact normalized candidate text in an excerpt is eligible as citation support; token overlap, changed numbers, negation, and selected opposing terms can flag possible conflicts but do not create supporting citations. Status `multi_source_match` records the same exact normalized text at multiple URLs only; URLs may be syndicated or share a source. Disputed and unverified claims are excluded from the report. The reviewer checks that each included sentence is present in its cited excerpt and was permitted by the writer policy. These checks validate process/provenance, not whether the source is right or supports the claim logically.

## Why conservative text checks

An entailment model would add another model, token/model provenance, evaluation requirements, deployment cost, and another unverified failure mode. For a small first build, conservative rules are transparent, testable, and fail closed. The cost is false negatives for paraphrases and sophisticated contradictions; this is documented rather than hidden.

## Safety boundary

Search workers only search. Fetching validates HTTP(S) URLs, rejects local/private destinations, rechecks redirects, and caps bytes and caller wait with a 12-second total deadline. A synchronous socket operation that outlives the deadline may remain in a daemon worker; the global worker cap is nine. Page text is data: the software does not execute it, send it to an LLM, or let it invoke tools. DNS validation is not a complete defense against rebinding; production deployment would need network egress policy.

## Evaluation boundary

The synthetic ablation isolates claim-screening behavior. It does not demonstrate that researchers find all relevant evidence, that an included claim is true, or that a multi-agent workflow beats a single model on real research tasks. A future external study should use a licensed, adjudicated corpus, claim-level evidence labels, source-lineage annotations, and a preregistered single-agent baseline.
