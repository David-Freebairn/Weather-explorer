"""
home.py — Weather Explorer
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Landing page: pick a SILO weather station, then choose an analysis.

  1. Rainfall chart   — calendar-style grid of daily rainfall (year or month)
  2. Monthly averages — long-term monthly rain/evap/temperature averages
  3. Snapshot         — one year's daily temperature + monthly rainfall

Default record duration: 1900 → current (see core/silo.py _FULL_START).

Run via the router (Menu.py) — not directly. Page config and the
overall navigation menu are set up there.
"""

import base64
import io
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import folium
import numpy as np
import streamlit as st
from streamlit_folium import st_folium

from core.nav import RAINFALL, MONTHLY, SNAPSHOT, SEASON, ODDS, HOWWET, TREND
from core.reliability import get_pct_observed, is_loaded, reliability_color, reliability_label
from core.silo import fetch_nearby_stations, search_stations
from core.styles import apply_styles, save_station, load_station

apply_styles()

_ICON_PATH = Path(__file__).resolve().parent / "assets" / "we_icon.png"
_SEASON_ICON_PATH = Path(__file__).resolve().parent / "assets" / "season_icon.jpg"
_HOWWET_ICON_PATH = Path(__file__).resolve().parent / "assets" / "howwet_card_icon.jpg"

ABOUT_TEXT = """
**To get started:**

- Select a location by name, use the map to see if SILO sites are available with better quality. It may take a minute to initially load climate data.
- Select an analysis from the menu.
    - Season
    - Howwet+
    - Odds?
    - Snapshot
    - Variability vs Trend
- Adjust each query to suit your situation e.g. dates, soil type etc.
- Information is available from the About button on most analyses.

**Background**

Weather drives how an agricultural system performs, especially in our Australian conditions where variability is high and uncertainty dominates many decisions. These apps use recent and long-term weather data (SILO) to provide estimates of how the current season is tracking: rainfall, soil water, nitrogen mineralisation. One analysis provides estimates of the chances or odds of rainfall at specific times while two analyses aim to give an overview of the climate i.e. what happens over many years.

**Decision framework**

Decisions are generally based on an understanding of Current conditions and Future expectations. Current conditions are what we sense around us and can be inferred by recent weather data. Future expectations are based on our experience, with a natural bias toward recent experiences. Weather Explorer's five analyses provide insight into both current conditions (soil water, nitrate mineralisation) and future events (rainfall). Application of long-term records help us avoid the trap of recent history bias by providing objective assessment of odds of rain and soil water.

- **How's the season** provides an objective assessment of rain since a specified date. Is the season well above, below or near average?
- **How much rain is stored?** uses recent rainfall data to estimate soil water through a fallow and into a crop.
- **What are the odds?** provides an unbiased estimate of the chances of a specified rain event.
- **Snapshot** provides a graphical comparison of a year's weather in the context of long-term values.
- **Variability vs Trend** provides an objective picture of rainfall and temperature trends since 1900 and within four 30-year periods.

**Acknowledgements**

Weather data: Queensland Government's SILO database sourced from the Bureau of Meteorology and the many voluntary weather recorders across the Australian continent since the 1890's.

Soil water and nitrate mineralisation estimate: Uses a well-tested water balance model used in models such as PERFECT, Howwet? and ApSim.

Interface: Elements of graphical presentations come from Howoften?, Howwet? and PYCalc while the "Snapshot" graphic is based on an image in the New York Times.

**Disclosure**

These analyses have been developed based on previous experience in designing climate focused decision support tools using Anthropic's Claude AI software. This software was built to prototype new capabilities.
"""


def _station_picker_map(stations: list, chosen_label: str):
    """
    Render search results as clickable markers. Returns the label of the
    station whose marker was clicked this run, or None.

    Only stations with known lat/lon are plotted; if none qualify, the
    caller should skip calling this (nothing to show).
    """
    located = [s for s in stations if s.get("lat") is not None and s.get("lon") is not None]
    if not located:
        return None

    lats = [s["lat"] for s in located]
    lons = [s["lon"] for s in located]
    center = [sum(lats) / len(lats), sum(lons) / len(lons)]
    # Rough zoom from spread of results — tighter cluster, closer zoom.
    spread = max(max(lats) - min(lats), max(lons) - min(lons)) if len(located) > 1 else 0.1
    zoom = 9 if spread < 0.5 else (7 if spread < 2 else 5)

    m = folium.Map(location=center, zoom_start=zoom, tiles="CartoDB positron")
    for s in located:
        is_chosen = s["label"] == chosen_label
        folium.CircleMarker(
            location=[s["lat"], s["lon"]],
            radius=14 if is_chosen else 11,
            tooltip=s["label"],
            popup=s["label"],
            color="#1a5276" if is_chosen else "#2980b9",
            fill=True,
            fill_color="#e8a33d" if is_chosen else "#2980b9",
            fill_opacity=0.9 if is_chosen else 0.75,
            weight=3 if is_chosen else 2,
        ).add_to(m)

    result = st_folium(
        m, height=320, use_container_width=True,
        returned_objects=["last_object_clicked_tooltip"],
        key="we_station_map",
    )
    return result.get("last_object_clicked_tooltip") if result else None


def _reliability_map(station: dict, radius_km: int):
    """
    Map of `station` with a dashed radius circle and nearby SILO stations
    colour-coded by data reliability (bundled silo_reliability.csv,
    joined on station id against the live SILO 'near' results).
    """
    try:
        nearby = fetch_nearby_stations(station["id"], radius_km=radius_km)
    except Exception as e:
        st.warning(f"Could not load nearby stations: {e}")
        return
    if not nearby:
        st.caption("No other SILO stations found in range.")
        return

    if not is_loaded():
        st.warning(
            "Reliability data file not found (`data/silo_reliability.csv`) — "
            "stations below are shown without colour coding. Check that the "
            "`data/` folder was included when this app was deployed.",
            icon="\u26a0\ufe0f",
        )

    m = folium.Map(location=[station["lat"], station["lon"]], zoom_start=9,
                    tiles="CartoDB positron")
    folium.Circle(
        location=[station["lat"], station["lon"]],
        radius=radius_km * 1000,  # metres
        color="#1a5276", weight=1.5, fill=False, dash_array="6,6",
    ).add_to(m)

    tooltip_lookup = {}
    for s in nearby:
        pct = get_pct_observed(s["id"])
        is_center = s["id"] == station["id"]
        tip = f'{s["name"]} — {reliability_label(pct)}'
        tooltip_lookup[tip] = s
        folium.CircleMarker(
            location=[s["lat"], s["lon"]],
            radius=16 if is_center else 12,
            tooltip=tip,
            color="#000000" if is_center else reliability_color(pct),
            weight=3 if is_center else 2,
            fill=True,
            fill_color=reliability_color(pct),
            fill_opacity=0.85,
        ).add_to(m)

    result = st_folium(
        m, height=380, use_container_width=True,
        returned_objects=["last_object_clicked_tooltip"],
        key="we_reliability_map",
    )

    st.caption(
        "\U0001F7E2 \u226590% observed &nbsp;&nbsp; "
        "\U0001F7E0 50\u201389% &nbsp;&nbsp; "
        "\U0001F534 <50% &nbsp;&nbsp; "
        "\u26AA no data &nbsp;&nbsp;\u00b7&nbsp;&nbsp; "
        f"dashed circle = {radius_km} km radius &nbsp;&nbsp;\u00b7&nbsp;&nbsp; "
        "click a dot to switch station",
        unsafe_allow_html=True,
    )

    clicked_tip = result.get("last_object_clicked_tooltip") if result else None
    clicked = tooltip_lookup.get(clicked_tip) if clicked_tip else None
    if clicked and clicked["id"] != station["id"]:
        label = clicked["name"]
        if clicked.get("state"):
            label += f'  [{clicked["state"]}]'
        if clicked.get("lat") is not None and clicked.get("lon") is not None:
            label += f'  ({clicked["lat"]:.3f}, {clicked["lon"]:.3f})'
        st.session_state["we_chosen"]    = label
        st.session_state["we_confirmed"] = True
        save_station({**clicked, "label": label})
        st.rerun()


def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", transparent=True, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


@st.cache_data
def _image_file_b64(path: str) -> str:
    """Base64-encode a static image file as PNG (matches the data-URI
    mime type _render_cards expects), regardless of the source format."""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@st.cache_data
def _icon_calendar_b64() -> str:
    """Small calendar-grid preview, echoing the Rainfall chart page."""
    rng = np.random.default_rng(7)
    grid = rng.uniform(0, 1, size=(3, 7))
    grid[grid < 0.72] = np.nan  # mostly blank, like a real rain calendar
    fig, ax = plt.subplots(figsize=(2.3, 1.15), dpi=100)
    ax.imshow(grid, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(np.arange(-0.5, 7, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, 3, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    return _fig_to_b64(fig)


@st.cache_data
def _icon_monthly_avg_b64() -> str:
    """Small bar + dual-line preview, echoing the Monthly averages page."""
    months = np.arange(12)
    rain = np.array([45, 42, 46, 44, 50, 58, 58, 52, 50, 52, 50, 53])
    tmax = np.array([30, 29.5, 27, 22, 17, 13, 12, 14, 18, 22.5, 26, 29.5])
    tmin = np.array([15, 15, 12.5, 8.5, 5, 3, 2, 3, 6, 9, 11.5, 14])

    fig, ax1 = plt.subplots(figsize=(2.5, 1.3), dpi=100)
    ax1.bar(months, rain, color="#1a5276", alpha=0.8, width=0.7)
    ax1.set_xticks([]); ax1.set_yticks([])
    for spine in ax1.spines.values():
        spine.set_visible(False)

    ax2 = ax1.twinx()
    ax2.plot(months, tmax, color="#c0392b", lw=1.6)
    ax2.plot(months, tmin, color="#e67e22", lw=1.6)
    ax2.set_xticks([]); ax2.set_yticks([])
    for spine in ax2.spines.values():
        spine.set_visible(False)

    return _fig_to_b64(fig)


@st.cache_data
def _icon_snapshot_b64() -> str:
    """Small daily-temperature + monthly-rainfall preview, echoing Snapshot."""
    rng = np.random.default_rng(3)
    x = np.arange(120)
    base_max = 22 + 8 * np.sin(2 * np.pi * (x - 10) / 120)
    base_min = 12 + 7 * np.sin(2 * np.pi * (x - 10) / 120)
    tmax = base_max + rng.normal(0, 2, 120)
    tmin = base_min + rng.normal(0, 2, 120)
    rain = rng.uniform(10, 60, 12)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(2.5, 1.5), dpi=100,
                                    gridspec_kw={"height_ratios": [1.4, 1]})
    ax1.plot(x, tmax, color="#c0392b", lw=0.9)
    ax1.plot(x, tmin, color="#2980b9", lw=0.9)
    ax2.bar(np.arange(12), rain, color="#1a5276", alpha=0.8, width=0.7)
    for ax in (ax1, ax2):
        ax.set_xticks([]); ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
    fig.subplots_adjust(hspace=0.15)
    return _fig_to_b64(fig)


@st.cache_data
def _icon_trend_b64() -> str:
    """Small scatter + best-fit-line preview, echoing the Trend page."""
    rng = np.random.default_rng(13)
    x = np.arange(60)
    y = 300 + 0.3 * x + rng.normal(0, 40, 60)
    slope, intercept = np.polyfit(x, y, 1)

    fig, ax = plt.subplots(figsize=(2.5, 1.3), dpi=100)
    ax.scatter(x, y, s=8, color="#7fb3e8", alpha=0.8, edgecolor="none")
    ax.plot(x, slope * x + intercept, color="#c0392b", lw=1.6)
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    return _fig_to_b64(fig)


@st.cache_data
def _icon_odds_b64() -> str:
    """Small hit/miss threshold-bar preview, echoing the Odds page."""
    rng = np.random.default_rng(5)
    vals = rng.uniform(5, 60, 20)
    threshold = 30
    colors = ["#4da6ff" if v >= threshold else "#b8cfe8" for v in vals]

    fig, ax = plt.subplots(figsize=(2.5, 1.3), dpi=100)
    ax.bar(np.arange(20), vals, color=colors, width=0.7)
    ax.axhline(threshold, color="#0b1f3a", lw=1.3, ls="--")
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    return _fig_to_b64(fig)


title_col1, title_col2, title_col3 = st.columns([1, 8, 1], vertical_alignment="center")
with title_col1:
    if _ICON_PATH.exists():
        st.image(str(_ICON_PATH), width=64)
with title_col2:
    st.markdown("# Weather explorer")
with title_col3:
    with st.popover("\u2139\uFE0F About"):
        st.markdown(ABOUT_TEXT)

# ── Handle "Change" reset (must happen before widgets render) ─────────────────
if st.session_state.pop("we_reset", False):
    st.session_state["we_stations"]   = []
    st.session_state["we_confirmed"]  = False
    st.session_state["we_chosen"]     = None
    st.session_state["we_last_query"] = ""
    st.session_state["we_query"]      = ""
    st.session_state.pop("climate_df",  None)
    st.session_state.pop("climate_key", None)
    save_station(None)

for k, v in [("we_stations", []), ("we_confirmed", False),
             ("we_chosen", None), ("we_last_query", "")]:
    if k not in st.session_state:
        st.session_state[k] = v

# Pre-populate from a station chosen earlier this session
_shared = load_station()
if _shared and not st.session_state.get("we_confirmed"):
    st.session_state["we_stations"]  = [_shared]
    st.session_state["we_confirmed"] = True
    st.session_state["we_chosen"]    = _shared.get("label") or _shared.get("name", "")

# ── Select a weather station ───────────────────────────────────────────────────
with st.container(border=True):
    st.markdown('<p class="section-title">Select a weather station (SILO)</p>',
                unsafe_allow_html=True)

    confirmed = st.session_state.get("we_confirmed", False)

    if not confirmed:
        query = st.text_input(
            "station", label_visibility="collapsed",
            placeholder="e.g. Dalby — press Enter, then select from the list",
            key="we_query",
        )
        if query and len(query) >= 3:
            if st.session_state.get("we_last_query") != query:
                with st.spinner("Searching..."):
                    try:
                        st.session_state["we_stations"] = search_stations(query.strip())
                    except Exception as e:
                        st.error(f"Search failed: {e}")
                        st.session_state["we_stations"] = []
                st.session_state["we_last_query"] = query

            stations = st.session_state.get("we_stations", [])
            if stations:
                labels = [s["label"] for s in stations]
                chosen = st.session_state.get("we_chosen") or labels[0]
                if chosen not in labels:
                    chosen = labels[0]
                if len(labels) == 1:
                    st.session_state["we_chosen"]    = labels[0]
                    st.session_state["we_confirmed"] = True
                    save_station(stations[0])
                    st.rerun()
                else:
                    st.caption(f"**{len(labels)} stations found** — select one:")
                    rc1, rc2 = st.columns([5, 1])
                    with rc1:
                        chosen = st.radio(
                            "Station", options=labels,
                            index=labels.index(chosen) if chosen in labels else 0,
                            key="we_radio", label_visibility="collapsed",
                        )
                    with rc2:
                        st.markdown('<div style="margin-top:4px">', unsafe_allow_html=True)
                        if st.button("Select", key="we_select", width="stretch"):
                            st.session_state["we_chosen"]    = chosen
                            st.session_state["we_confirmed"] = True
                            save_station(next(s for s in stations if s["label"] == chosen))
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)

                    st.caption("...or click a station on the map:")
                    clicked_label = _station_picker_map(stations, chosen)
                    if clicked_label and clicked_label in labels:
                        st.session_state["we_chosen"]    = clicked_label
                        st.session_state["we_confirmed"] = True
                        save_station(next(s for s in stations if s["label"] == clicked_label))
                        st.rerun()
            elif st.session_state.get("we_last_query"):
                st.warning("No stations found. Try a shorter search term.")
    else:
        chosen = st.session_state.get("we_chosen", "")
        c1, c2 = st.columns([5, 1])
        with c1:
            st.success(f"\U0001F4CD {chosen}")
        with c2:
            if st.button("Change", key="we_change", width="stretch"):
                st.session_state["we_reset"] = True
                st.rerun()

        _station = load_station()
        if _station and _station.get("lat") is not None and _station.get("lon") is not None:
            with st.expander("Show reliability map"):
                radius_km = st.slider(
                    "Radius (km)", min_value=10, max_value=200,
                    value=int(st.session_state.get("persist_we_radius", 50)),
                    step=10, key="we_radius",
                )
                st.session_state["persist_we_radius"] = radius_km
                _reliability_map(_station, radius_km=radius_km)

station = load_station()

st.write("")


def _render_cards(cards):
    cols = st.columns(len(cards))
    for col, (title, sub, icon_b64, target, key) in zip(cols, cards):
        with col:
            with st.container(border=True, key=key):
                st.markdown(
                    f'<div style="text-align:center;">'
                    f'<h3 style="margin:0.2rem 0 0.15rem 0;font-size:1.15rem;">{title}</h3>'
                    f'<p style="color:#666;font-size:0.85rem;margin:0 0 0.6rem 0;">{sub}</p>'
                    f'<img src="data:image/png;base64,{icon_b64}" '
                    f'style="width:100%;border:1px solid #e5e5e5;border-radius:6px;'
                    f'background:#fafafa;padding:4px;box-sizing:border-box;"/>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.page_link(target, label="Open", disabled=not station,
                             use_container_width=True)


# ── Current weather, future odds ─────────────────────────────────────────────
st.markdown("**Current weather, future odds**")
_render_cards([
    ("Season?", "This season vs history", _image_file_b64(str(_SEASON_ICON_PATH)),
     SEASON, "we_card_season"),
    ("Howwet +N", "Soil water, nitrogen", _image_file_b64(str(_HOWWET_ICON_PATH)),
     HOWWET, "we_card_howwet"),
    ("What chance?", "Rainfall frequency analysis", _icon_odds_b64(),
     ODDS, "we_card_odds"),
])

st.write("")

# ── History ───────────────────────────────────────────────────────────────────
st.markdown("**History**")
_render_cards([
    ("Snapshot", "By year, long term rainfall", _icon_snapshot_b64(),
     SNAPSHOT, "we_card_snapshot"),
    ("Trend vs variability", "Rainfall, temperature trend", _icon_trend_b64(),
     TREND, "we_card_trend"),
    ("Rainfall chart", "Calendar", _icon_calendar_b64(),
     RAINFALL, "we_card_rainfall"),
    ("Climate by month", "Rainfall, evap., temperature", _icon_monthly_avg_b64(),
     MONTHLY, "we_card_monthly"),
])

if not station:
    st.caption("Select a station above to enable these.")
