# Weather Explorer

A standalone Streamlit app for exploring SILO weather station records.

## Pages

1. **Rainfall chart** — calendar-style grid of daily rainfall for a
   chosen year (12 months x 31 days), with a Total and long-term
   Average row underneath. *(built)*
2. **Monthly averages** — long-term monthly rain, evaporation, and
   min/max temperature (dual-axis chart), with an annual min/max/avg
   summary table underneath. *(built)*
3. **Snapshot** — one year's daily temperature and monthly rainfall
   vs long-term mean. *(built — trimmed from RiskAware; no long-term
   annual-totals panel at this stage)*
4. **Season** — this season's cumulative rainfall vs every year on
   record (spaghetti + median, three most recent years highlighted),
   plus a forward-looking 20th–80th percentile plume for the months
   ahead, built by replaying each historical year's rainfall onto
   today's actual total. *(built — ported from RiskAware's "How's the
   season?" page)*

## Structure

```
Menu.py                       # Entrypoint: page config + navigation router
home.py                       # Menu content: station picker + analysis cards
core/nav.py                   # StreamlitPage objects shared across all pages
                               # (cross-page links use these objects, not
                               # filename strings — see note below)
core/silo.py                  # SILO fetch/cache (station search, daily
                               # climate data, disk + session cache,
                               # SILO-down fallback)
core/styles.py                 # Shared CSS + station session-state helpers
pages/1_Rainfall_chart.py     # Built
pages/2_Monthly_averages.py   # Built
pages/3_Snapshot.py           # Built
pages/4_Season.py             # Built
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
`MONTHLY`, `SNAPSHOT`); every page imports from there and calls
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
