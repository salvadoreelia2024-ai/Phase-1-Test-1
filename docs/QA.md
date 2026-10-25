# Verification record

Checked on 24 October 2026.

## Passed

- `python scripts/generate_demo.py`: generates the shipped synthetic snapshot through the real engine.
- `python -m unittest discover -s tests -v`: 14 tests covering the Gaussian reflection-principle limit, deterministic random simulation, invalid prices, trading-session weekends/breaks, calibration metrics, publication stability, snapshot probability bounds, horizon and barrier monotonicity, scenario quantiles, archival deduplication, provider failure, and retry after a failed publication write.
- `node --check public/app.js`: JavaScript syntax.
- `node tests/frontend-smoke.mjs`: unit smoke checks using a small DOM double: valid snapshot load, repeated calculation, horizon selection, short positions and stops, rejected invalid prices, theme changes, chart element creation, and source context.

The independent debugger identified two publication defects. Both were fixed: demo state cannot seed the first live reference; a failed static file write rolls back the processed-bar state so that the same input can be retried. Publication persistence compares signed changes so oscillating candidates do not satisfy the persistence rule.

## Not verified here

- Browser rendering, mobile layout, real drag behavior, and assistive-technology interaction. The managed preview server was available, but browser access was blocked by the environment's browser policy. DOM-double tests are not browser tests.
- An end-to-end Yahoo/EIA market-data pull, GitHub-hosted run, or Netlify deployment in the owner's accounts. No credentials/accounts were configured or deployment performed.
- Statistical predictive accuracy, historical crisis calibration, economic skill, or live out-of-sample performance. Numerical consistency tests cannot establish these claims.

## Before treating the site as operational

Run the GitHub update workflow, inspect the actual provider timestamps, and check the deployed desktop/mobile interface. Continue the historical validation and source-integration work listed in ARCHITECTURE.md. The initial package is a research implementation, not completion of all five release gates.
