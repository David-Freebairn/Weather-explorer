# Weather Explorer

A standalone Streamlit app for exploring SILO weather station records.
This app is also the consolidation point for David's three related
apps (Weather Explorer, RiskAware, Howwet+) — see "Consolidation" below.

## Pages

Grouped in the sidebar into two sections:

**Current weather, future odds**
1. **Season?** — this season's cumulative rainfall vs every
   year on record (spaghetti + median, three most recent years
   highlighted), plus a forward-looking 20th–80th percentile plume for
   the months ahead. *(built — ported from RiskAware)*
2. **Howwet +N** — plant-available soil water (PASW) and nitrate
   mineralisation through a fallow and following crop, against a
   20th–80th percentile historical band since 1995, plus a nitrogen
   balance / yield calculator and a downloadable Word report. *(built
   — ported from the standalone Howwet+ app)*
3. **What chance?** — rainfall frequency analysis: how often has
   a given amount of rain fallen within a given window, between two
   dates, across the record. *(built — ported from RiskAware)*

**History**
4. **Snapshot** — one year's daily temperature and monthly rainfall vs
   long-term mean, plus 100 years of annual rainfall with rolling
   5/10/30-yr averages. *(built — ported from RiskAware's fuller
   version, replacing Weather Explorer's earlier trimmed one)*
5. **Trend vs variability** — annual rainfall or annual average
   temperature, as a scatter with a single line of best fit across the
   whole record, plus a second chart splitting the record into four
   roughly-equal historical periods (~30 years each) each with its
   own independently-fitted trend, to surface whether the trend has
   been stable or has shifted between eras. *(built)*
6. **Rainfall chart** — calendar-style grid of daily rainfall for a
   chosen year (12 months x 31 days), with a Total and long-term
   Average row underneath. *(built)*
7. **Climate by month** — long-term monthly rain, evaporation, and
   min/max temperature (dual-axis chart), with an annual min/max/avg
   summary table underneath. *(built — formerly "Monthly averages")*

## Consolidation (RiskAware + Howwet+ → Weather Explorer)

David is merging RiskAware's and Howwet+'s pages into this app rather
than maintaining three separate deployments. Decisions made along the
way:
- RiskAware's fallow-PASW page and standalone YieldRisk page are
  **dropped** — Howwet+ covers the same ground more fully.
- A "Trend vs variability" page was considered and **left out** for
  now — Snapshot's existing 100-year annual-rainfall panel already
  covers most of that ground.
- Ported pages keep the original apps' analysis/chart/export logic
  unchanged; only the station-selection UI was adapted to Weather
  Explorer's shared pattern (station picked once on Menu, not
  per-page). Howwet+ also keeps its background climate-prefetch thread
  (kicks off as soon as a station is confirmed, so it's often already
  cached by the time you finish setting up soil/dates), now triggered
  off the shared station instead of its own local one.
- Howwet+'s own core/ modules (soil profile, water balance, nitrogen,
  yield, cover-Excel reader, Word-report builder) were copied in under
  `core/howwet_*.py` — prefixed to keep them visually distinct from
  Weather Explorer's shared core/ modules. Its `core/silo.py` was
  **not** copied — Weather Explorer's own `core/silo.py` is a strict
  superset (same interface, wider default fetch range: 1900 vs 1995)
  and is used directly.
- Added `openpyxl` (crop-cover Excel reader) and `python-docx` (Word
  report export) to requirements.txt. `lxml` was in Howwet+'s original
  requirements but isn't actually imported anywhere in its
  code — its soil-XML parser uses the standard-library
  `xml.etree.ElementTree` — so it (and the `packages.txt` system
  libraries it needed) wasn't carried over.

## Structure

```
Menu.py                       # Entrypoint: page config + navigation router
home.py                       # Menu content: station picker + analysis cards
core/nav.py                   # StreamlitPage objects + sidebar SECTIONS dict
                               # (cross-page links use these objects, not
                               # filename strings — see note below)
core/silo.py                  # SILO fetch/cache (station search, daily
                               # climate data, disk + session cache,
                               # SILO-down fallback, nearby-station search)
core/styles.py                 # Shared CSS + station persistence helpers
core/reliability.py            # Bundled station-reliability lookup (map colouring)
core/howwet_*.py               # Howwet+'s own modules (soil, water balance,
                                # nitrogen, yield, cover-Excel, Word report)
pages/1_Rainfall_chart.py     # Built
pages/2_Monthly_averages.py   # Built (titled "Climate by month")
pages/3_Snapshot.py           # Built (RiskAware's fuller version)
pages/4_Season.py             # Built
pages/5_Odds.py               # Built (ported from RiskAware)
pages/6_Howwet.py             # Built (ported from the standalone Howwet+ app)
pages/7_Trend.py              # Built (annual rainfall/temp trend, all-years + 4-period)
data/*.xml, data/generic_crop.xlsx   # Howwet+'s soil profiles + crop cover template
assets/howwet_icon*.png              # Howwet+'s icons (in-app + report)
assets/we_icon.png                   # Weather Explorer's own app icon (title row + browser tab)
```

Run locally with `streamlit run Menu.py`. Same file for the Streamlit
Community Cloud "main file" setting.

### Why `core/nav.py`?

Pages are wired up via Streamlit's `st.Page`/`st.navigation` API rather
than the older filename-string style (`st.page_link("Menu.py")`). The
string-matching approach is known to be fragile — whether it resolves
correctly can depend on the exact working directory `streamlit run` was
invoked from, and has a history of `StreamlitPageNotFoundError`s across
different setups (see streamlit/streamlit#8070 and related issues).
`core/nav.py` defines each page once as an object (`HOME`, `RAINFALL`,
`MONTHLY`, `SNAPSHOT`, `SEASON`, `ODDS`); every page imports from there and calls
`st.page_link(HOME, ...)` instead of a path string. Because of this,
`st.set_page_config()` is called exactly once, in `Menu.py` — it can't
be called again inside `home.py` or the `pages/` scripts.

## Data record

Default duration is 1900 → current (`core/silo.py::_FULL_START`). Actual
coverage depends on the station's own record length.

## Deployment notes (carried over from Howwet+/RiskAware)

- Pin to Python 3.12 via `.python-version` — Python 3.14 has caused
  segfaults on Streamlit Community Cloud.
- Requires Streamlit ≥ 1.36 for `st.Page`/`st.navigation`.
- Station data is cached to `.silo_cache/<station_id>.parquet` (24h) and
  to `st.session_state`, so switching pages doesn't re-fetch.
- If SILO is unreachable, pages show a warning and (if a
  `sample_data/` bundle with `dalby_sample.parquet` +
  `dalby_station.json` is added) offer a sample-data fallback via
  `core.silo.load_sample_data()`.
