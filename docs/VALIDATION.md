# Validation and research gates

Run `python -m unittest discover -s tests -v` from the repository root. Also run `node --check public/app.js`. Numerical unit tests establish code behavior; they do **not** prove financial predictive accuracy.

The release includes a deterministic demo so interface behavior can be tested without a provider. Live ingestion needs network access and the optional yfinance dependency. If that connection has not been tested in your environment, verify it through a manual workflow run before describing the dashboard as live.

## Required before claiming calibration

1. Collect point-in-time hourly OHLC data with instrument/contract identity, release timestamps and provenance. Retain revisions separately if inputs are revised.
2. Partition chronologically: fit volatility/features on the past, fit calibration only on earlier out-of-sample predictions, then score an untouched future period. Use purged/embargoed splits for overlapping horizons.
3. Resolve touch from observed high/low, finish from close, and target-before-stop from suitably fine data. If both barriers lie within one observed bar and their order is unknown, mark ambiguous rather than inventing an order.
4. Compare Brier score, log loss, reliability by bucket, interval coverage and sharpness against a simple constant-volatility baseline. Report uncertainty and the number of resolved independent observations.
5. Measure noise-driven publication changes and shock-response lag. Tune deadband and persistence on training/validation periods, never the final holdout.
6. Repeat by horizon and regime. Test 2008, 2014–16, 2020, 2022 and recent periods only where compatible historical observations genuinely exist. Do not pretend that a short free intraday series covers these episodes.
7. Treat nonpositive April 2020 prices with a separate suitable model. The present log-price engine rejects them; deleting that period is not validation.
8. Disable any news/fundamental/regime feature whose ablation fails. Retrain decays/caps only after historical event replay and independent-source checks.
9. Maintain a prospective public outcome ledger and reliability chart before advertising a calibrated track record.

## Known approximations

- A parametric volatility model and simulated tails are assumptions. Estimates can be wrong during structural breaks.
- Finite simulation error is distinct from model uncertainty. A narrow Monte Carlo error bar is not evidence of narrow real-world uncertainty.
- Target grids have finite resolution. Do not describe a rounded lookup as an exact probability at an arbitrary submitted price.
- Bridge-based between-step hit checks and same-step target/stop ordering require numerical convergence checks and special treatment when jumps occur.
- Normal weekly trading sessions do not cover every holiday or unscheduled closure. Calendar horizons that contain no trading time cannot be treated as ordinary open-market hours.
- Continuous/front-month futures can introduce roll discontinuities. Validate an appropriate roll policy before drawing conclusions from long archives.
- Recent hourly data is not enough to demonstrate three-month forecasting skill or political-event accuracy.

The UI must retain uncalibrated/experimental labels until these gates are supported by actual stored evidence. Do not replace missing scores with plausible-looking numbers.
