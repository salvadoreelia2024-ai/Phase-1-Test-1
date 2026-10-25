# Data sources and setup

## Included demonstration

The committed snapshot is synthetic and clearly marked as a demo. Its WTI and Nasdaq values are illustrative, not present-day quotes. A successful live update replaces it; an unsuccessful update leaves it intact.

## Market adapter

`engine/ingest.py` optionally imports [yfinance](https://ranaroussi.github.io/yfinance/) and requests one month of hourly data using the documented [history API](https://ranaroussi.github.io/yfinance/reference/yfinance.price_history.html).

| Symbol | Meaning | Use |
| --- | --- | --- |
| `CL=F` | Yahoo front-month WTI futures series | Volatility inputs and reference price |
| `BZ=F` | Yahoo Brent futures series | Matched-bar Brent–WTI context spread |
| `^IXIC` | Nasdaq Composite | Context quote; change is since the preceding hourly bar |
| `^OVX` | Cboe oil volatility index through Yahoo | Archived context only |

**CL=F is not TVC:USOIL.** Contract rolls, instrument construction, data vendors and timing can create differences. Never rename Yahoo futures as a live TradingView spot quote. No contract-roll adjustment has been validated; roll jumps can contaminate volatility. Input data is hourly completed bars, with additional provider/network delay. It does not promise a universal 10–15 minute delay.

Timestamps are normalized to UTC. Yahoo labels bars at their start, so published input timestamps are shifted to the nominal hourly endpoint. Equity final sessions and exceptional market closures can contain shorter bars; the endpoint is an hourly bar convention, not an exact last-trade timestamp. Values must be finite, positive, and satisfy low ≤ close ≤ high. WTI requires at least 100 bars and a final nominal endpoint less than four hours old. Weekends/holidays therefore preserve the last snapshot. This is conservative staleness handling, not a full exchange-calendar freshness policy.

A missing optional market leaves that context unavailable. A missing/stale WTI market blocks publication. There is **no independent provider fallback** in this release: archived values remain visible with their original timestamps. Do not substitute natural gas, an ETF, daily spot prices, or a different contract simply because an endpoint works.

Install the optional adapter with `python -m pip install 'yfinance>=0.2.54,<1'`. No API key is needed. Provider access and rate limits may change. The code cannot guarantee access from every hosting region. yfinance is an unofficial access library; review Yahoo and exchange terms, including display and redistribution, before public operation.

## Official news

The [EIA RSS directory](https://www.eia.gov/tools/rssfeeds/) links its [Today in Energy feed](https://www.eia.gov/rss/todayinenergy.xml). The adapter stores titles, official HTTPS links, dates and source labels. It deduplicates by link, bounds the response size and archives metadata. No article body is republished. All collected headlines have zero model contribution. The feed is broader than WTI and is not a complete conflict/news alert system.

## Connecting the remaining plan sources

Future adapters should preserve raw observations, source IDs, timestamps and quality flags. Use feature-specific out-of-sample ablation before enabling any effect. Examples: EIA inventory requires a free EIA key; FRED requires its own free key; AISstream requires registration. Put such credentials in GitHub repository secrets, never in the static JSON, source code or browser. No secrets are required by the delivered adapter.

## Scheduler

The workflow is scheduled at minute 17 each hour. [GitHub documents](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows) that scheduled runs can be delayed and operate on the default branch. Enable Actions and allow repository write permission for the workflow's bot, or publish snapshots through your own deployment service. Branch protection can prevent its commit; inspect failed Actions rather than assuming a live update succeeded. Check current account minutes and provider terms; this repository makes no promise that arbitrary usage stays free.
