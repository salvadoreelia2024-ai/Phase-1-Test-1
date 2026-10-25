# Architecture and implementation boundary

This repository is an executable research foundation for the supplied WTI architecture, not evidence that all five scientific release gates have passed. The delivered interface is usable immediately with an explicitly synthetic snapshot. Turning on market ingestion supplies observed inputs, but does not make the probabilities calibrated.

## Runtime

1. GitHub Actions calls `python -m engine.update` hourly, at minute 17 UTC, or on manual dispatch.
2. The backend fetches and validates completed hourly WTI futures bars. SQLite stores OHLC inputs, provider failures, EIA headline metadata, publishing state, snapshot versions and audit records.
3. The model builds a deterministic, precomputed probability grid for all supported horizons. The configured random seed and a stored publication prevent browser refreshes from producing new odds.
4. Publishing rules choose whether to retain the previous result or publish a new one. The frontend fetches only `public/data/snapshot.json` and looks up results.
5. GitHub commits the static snapshot and `state/archive.sqlite`. Netlify rebuilds its static publication from the connected repository. No server-side function or paid API is needed to display a snapshot.

The dashboard has no provider credentials and does not run a Monte Carlo simulation. Its supported target/stop levels are a finite published grid. Follow its explicit level selection/validation rather than interpreting an unsupported arbitrary price as an exact simulated level.

## What is implemented

- Static responsive dashboard; long/short position inputs; optional stop; horizon controls; scenario chart; model status and data provenance.
- Python Monte Carlo engine, volatility fitting, seeded generation and precomputed snapshot output.
- Market ingestion through the optional yfinance adapter, with hourly OHLC archiving and strict positive-price validation.
- Reference-price and publication stability mechanisms, persisted between scheduled runs.
- Calibration/validation utilities and numerical tests, without fabricated backtest scores.
- EIA headline metadata collection: links and titles only, never article text. These stories are **context only** and contribute zero to probabilities.
- Safe publication: malformed, missing or stale WTI input does not overwrite the previous snapshot. Failure is visible in Actions; the stored snapshot continues to age in the dashboard.

## Still research/integration work

| Architecture requirement | Current boundary |
| --- | --- |
| Full historical walk-forward calibration across crises | Utilities and numerical tests are not a completed multi-regime study. No fitted production calibration map or demonstrated accuracy is supplied. |
| Live prediction outcome resolution and public reliability scoreboard | Requires a maintained outcome ledger, adequate data, and operational measurement; no invented results are displayed. |
| Free alternate WTI provider | No automatic independent live fallback is configured. The fallback is the last valid snapshot. An adapter must verify the same contract and bar convention before use. |
| EIA inventory, CFTC positioning, rigs, curve and seasonality | Not automatically ingested or fitted as predictive factors. |
| Trained HMM or gradient-boosted market regime | Not a validated trained classifier. Any descriptive volatility state must not be presented as one. |
| OVX fitted blend | OVX is fetched as context, not given an unvalidated predictive coefficient. |
| GDELT/FinBERT event classification and fitted decaying event effects | Not connected to live probabilities. EIA RSS alone is not this pipeline. |
| PortWatch, AIS, tanker positions, maritime alert triggers | Context placeholders/unavailable, not inferred normal status. No live ship map is fabricated. |
| Automatic corroborated headline shock bypass | Not wired. The engine's bypass API is reserved for a later verified trigger service. |
| Exchange holidays, exceptional closures and weekend gap distributions | Normal weekly session logic is a simplification; validate against a licensed exchange calendar before execution use. |
| 5-minute ingestion and immediate triggers | The supplied low-operations scheduler is hourly. GitHub scheduled jobs are best-effort, not a latency guarantee. |

## Operational trade-offs

SQLite is deliberately committed to the repository so archival state survives runners without relying on expiring caches. It contains market metadata, not secrets. This is simple for a private research deployment, but the database and Git history grow: migrate to durable object storage or PostgreSQL before long-running/public operation. Snapshots are archived in full and should eventually use compression and retention policies. Review provider redistribution terms before making this archive public.

No change is automatically attributed to a geopolitical event that the code has not independently measured. Ordinary publication reasons describe price/volatility updates. Parameter and source changes should receive new model versions and a calibration review.
