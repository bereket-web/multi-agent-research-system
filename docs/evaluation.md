# Evaluation notes

The repository has three kinds of checks:

- **Software tests** use fake search and fetch adapters to verify bounds, role routing, source IDs, writer filtering, reviewer rejection, provider-challenge detection, and fail-closed behavior. They do not make network calls.
- **Synthetic ablation** uses six original, hand-labeled text fixtures to verify that a claim gate blocks the specific unsupported and conflicting examples supplied to it.
- **Live adapter smoke** was attempted once. DuckDuckGo returned HTTP 202 with an anti-bot challenge page, so no page was fetched and live end-to-end search remains unverified; see [the smoke note](../evaluation/live-smoke.md).

Neither offline nor synthetic results measure truth, entailment, real search coverage, source authority, generalization, or production performance. A multi-URL text match is not proof of independent corroboration; the system has no publisher-lineage data. Do not advertise synthetic fixture counts as model accuracy or research quality.
