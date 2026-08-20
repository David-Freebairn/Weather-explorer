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

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import numpy as np
import streamlit as st

from core.nav import RAINFALL, MONTHLY, SNAPSHOT, SEASON
from core.silo import search_stations
from core.styles import apply_styles, save_station, load_station

apply_styles()


def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", transparent=True, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
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
def _icon_season_b64() -> str:
    """Small spaghetti + forward-fan preview, echoing the Season page."""
    rng = np.random.default_rng(11)
    x_back = np.linspace(0, 1, 60)
    x_fwd = np.linspace(1, 1.6, 20)

    fig, ax = plt.subplots(figsize=(2.5, 1.3), dpi=100)
    for _ in range(14):
        walk = np.cumsum(rng.uniform(0, 1, 60))
        walk = walk / walk[-1] * rng.uniform(0.5, 1.0)
        ax.plot(x_back, walk, color="#7ab4d8", lw=0.8, alpha=0.4)

    highlight_colors = ["#e8a33d", "#4f9d69", "#7d5ba6"]
    for c in highlight_colors:
        walk = np.cumsum(rng.uniform(0, 1, 60))
        walk = walk / walk[-1] * rng.uniform(0.6, 0.95)
        ax.plot(x_back, walk, color=c, lw=1.4, alpha=0.9)

    current = np.cumsum(rng.uniform(0.3, 1, 60))
    current = current / current[-1] * 0.75
    ax.plot(x_back, current, color="#cc2200", lw=2)

    p20 = current[-1] + (x_fwd - 1) * 0.15
    p80 = current[-1] + (x_fwd - 1) * 1.1
    ax.fill_between(x_fwd, p20, p80, color="#e8a33d", alpha=0.28, linewidth=0)

    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    return _fig_to_b64(fig)


st.markdown("# Weather explorer")

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
    st.session_state["we_chosen"]    = _shared.get("label", "")

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

station = load_station()

st.write("")
st.markdown("**Select an analysis**")
st.write("")

# ── Analysis cards ──────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

cards = [
    (col1, "Rainfall chart", "Calendar", _icon_calendar_b64(),
     RAINFALL, "we_card_1"),
    (col2, "Monthly averages", "Rainfall, evap., temperature", _icon_monthly_avg_b64(),
     MONTHLY, "we_card_2"),
    (col3, "Snapshot", "Of a year", _icon_snapshot_b64(),
     SNAPSHOT, "we_card_3"),
    (col4, "Season", "This season vs history", _icon_season_b64(),
     SEASON, "we_card_4"),
]

for col, title, sub, icon_b64, target, key in cards:
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

if not station:
    st.caption("Select a station above to enable these.")
