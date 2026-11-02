# Live adapter smoke note

On 2026-11-02, a one-query DuckDuckGo Lite smoke returned no search hits. Inspecting the provider response showed HTTP 202 with DuckDuckGo's anti-bot challenge page (“Unfortunately, bots use DuckDuckGo too” / `anomaly-modal`), not a normal search-results document. No search result was selected and no result page was fetched. The challenge was not bypassed.

The adapter now detects common challenge markers and raises an explicit search-unavailable error so the researcher role can surface the failure as a warning. This is evidence that the provider can block this environment; live search and page extraction are **not verified end to end**. Offline fake-adapter tests and the synthetic CLI demo do pass.
