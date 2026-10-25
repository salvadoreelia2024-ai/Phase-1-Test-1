# WTI Observatory

A minimalist, snapshot-based WTI probability research website. White and black, restrained lime highlights, responsive charts, light/dark themes, and no browser-side model simulation or API keys.

**Starts in clearly marked demonstration mode.** The bundled snapshot uses synthetic prices. It is not today's market and is not a validated trading signal. The repository contains a runnable statistical engine and data-update pipeline, but does not claim to have passed the architecture plan's historical calibration or public-readiness gates. See `docs/ARCHITECTURE.md` for the implemented/deferred boundary.

## 1. Put the code on GitHub

1. Extract the ZIP.
2. Create an empty GitHub repository.
3. Upload the **contents inside `wti-observatory`** to the repository root, including `.github/workflows`. `netlify.toml`, `README.md`, `requirements.txt`, and the `public` directory should appear at the top level.
4. Commit the files. If your file manager hides names beginning with a dot, enable hidden files so the workflows are included.

Or, inside the extracted project folder:

```sh
git init
git add .
git commit -m "Add WTI Observatory"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

## 2. Publish with Netlify

Import the GitHub repository into Netlify and use:

| Setting | Value |
|---|---|
| Base directory | Empty (repository root) |
| Build command | Empty |
| Publish directory | `public` |
| Functions directory | Not needed |

The included `netlify.toml` sets the publish directory and security/cache headers. This site needs no JavaScript dependency installation or frontend build. Publishing first shows the functioning demonstration dashboard. Importing the repository does not itself activate real market data.

For a quick manual deployment, drag the **`public` folder** into Netlify's manual deployment interface. Manual deployments will not automatically receive GitHub snapshot updates. A Git-connected deployment is recommended for scheduled data.

Cloudflare Pages and other static hosts can also serve `public`; their security-header configuration may differ. Do not publish the entire repository as the web root.

## 3. Run locally

Python 3.12 recommended. From the project root:

```sh
python -m http.server 5173 --directory public
```

Open http://localhost:5173. Do not double-click `index.html`: browsers restrict JSON fetching from `file://` URLs.

To work on the engine:

```sh
python -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows PowerShell instead:
# .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

See `docs/DATA_SOURCES.md` for provider configuration and `docs/ARCHITECTURE.md` for the scheduled update commands and persistence design.

## 4. Enable observed market updates

After the site displays correctly, open your GitHub repository's **Actions** tab and select **Update market snapshot → Run workflow** on your default branch. The workflow requests repository contents write permission so it can save snapshots and its SQLite archive. Repository policy or branch protection may block this; check the run log if the update fails.

A successful run commits `public/data/snapshot.json` and `state/archive.sqlite`. Netlify's Git-connected deployment then serves the updated snapshot. The badge changes from **Demonstration** to **Research snapshot**. This means observed inputs, not verified forecasting accuracy. The hourly scheduler is included; scheduled workflows may require enabling in a fork.

To run the same update yourself after installing requirements:

```sh
python -m engine.update
```

A weekend, provider block, or stale quote can cause the update to fail safely. Read the Actions error; the site retains the previous snapshot with its original timestamp. Do not replace it with invented current prices. The frontend does not need an API key and this version uses no paid services.

## Reading the result

- **Touch** means reaching the chosen target at any time within the window.
- **Finish** means ending beyond the target.
- **Target before stop** counts a target hit only if it precedes the optional stop.
- **Hit time** is conditional on paths that hit; it is not a promise that the target will be reached.
- The entry input describes the position. Simulation begins at the snapshot's reference price.
- Inputs use the published price grid, visibly disclosed in the UI. A snapshot cannot answer arbitrary unsupported prices with invented precision.
- The percentile fan is a distribution of simulated prices, not three predictions.
- Sensitivity ranges are not empirically calibrated confidence intervals.

## Important implementation boundaries

`CL=F` is a rolling WTI futures proxy, **not the same instrument as TVC:USOIL**, spot oil, or a broker's CFD. Futures rolls and provider delays can affect comparisons. There is no guaranteed fixed 10–15 minute delay; the source timestamp controls staleness.

The downloadable version does not ship trained geopolitical/news effects, full AIS tracking, a fitted hidden Markov classifier, licensed exchange data, or a proven live track record. These appear as unavailable or context-only, not fabricated market readings. Supporting every integration in the plan requires provider access, historical datasets, and validation over time.

GitHub scheduling is best-effort, not an incident-response system. Workflow minutes, artifact storage, repository growth, provider restrictions, and host deployment quotas may limit a free installation. The hourly schedule is deliberately more conservative than the plan's eventual five-minute ingestion service.

Never place provider secrets in `public`, browser JavaScript, or Git commits. Use GitHub Actions secrets for private values. Review provider redistribution terms before a public launch.

## Repository map

- `public/` — deployable frontend and published snapshot
- `engine/` — data ingestion, simulation, calibration/stability utilities and update orchestration
- `scripts/` — reproducible demo generation
- `tests/` — engine and independent integration checks
- `.github/workflows/` — source checks and scheduled snapshot updates
- `docs/` — architecture, data sources, validation and QA notes

## Reference documentation

- Netlify build configuration: https://docs.netlify.com/build/configure-builds/overview/
- Netlify file configuration: https://docs.netlify.com/build/configure-builds/file-based-configuration/
- GitHub scheduling limits: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule

Statistical research software. Not financial advice or a guarantee of accuracy.
