"""
pages/3_Snapshot.py — Weather Explorer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
A review of one year's weather: daily temperature (max/min + long-term
averages) and monthly rainfall vs long-term mean, for the selected
station.

Ported from RiskAware's Snapshot page, trimmed to this one panel —
the "last 100 years" annual rainfall chart is not included at this
stage.

Uses the shared SILO full-record cache from core/silo.py (1900 → current).
"""

import io
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

import numpy as np
import streamlit as st

from core.nav import HOME
from core.silo import ensure_climate_cached, SiloUnavailableError, load_sample_data
from core.styles import apply_styles, load_station

apply_styles()

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _handle_silo_down(exc):
    st.warning(
        f"\u26A0\uFE0F SILO is currently unavailable ({exc}). "
        "You can use the bundled sample dataset to explore the app, if one is bundled."
    )
    if st.button("\U0001F4C2  Use sample data", key="use_sample"):
        try:
            df, station_info = load_sample_data(session_state=st.session_state)
            st.session_state["we_station"] = station_info
            st.rerun()
        except FileNotFoundError as e:
            st.error(str(e))
    st.stop()


st.markdown("## Snapshot")
st.caption("A review of one year's temperature and rainfall")

station = load_station()
if not station:
    st.info("No station selected yet.")
    st.page_link(HOME, label="\u2190 Back to select a station")
    st.stop()

sid = station.get("id") or station.get("number")
lat = station.get("lat")
lon = station.get("lon")

with st.spinner(f"Loading climate data for {station['name']}\u2026 (first load may take 30\u201360 seconds)"):
    try:
        ensure_climate_cached(sid, lat=lat, lon=lon, session_state=st.session_state)
    except SiloUnavailableError as e:
        _handle_silo_down(e)
    except Exception as e:
        st.error(f"Data fetch failed: {e}")
        st.stop()

df = st.session_state["climate_df"].copy()

today = date.today()
available = sorted(df["year"].unique())

c1, c2, c3 = st.columns([2, 3, 2])
with c1:
    st.success(f"\U0001F4CD {station.get('label', station.get('name', ''))}")
with c2:
    target_year = st.number_input(
        "Year", min_value=int(available[0]), max_value=int(available[-1]),
        value=min(int(today.year - 1), int(available[-1])),
        step=1, key="snap_year",
    )
with c3:
    st.page_link(HOME, label="Change station")

dy   = df[df["year"] == target_year].copy()
hist = df[df["year"] < target_year].copy()

if dy.empty:
    st.warning(f"No data for {target_year} at this station.")
    st.stop()

# Temperature long-term monthly averages
monthly_tmax = hist.groupby("month")["tmax"].mean()
monthly_tmin = hist.groupby("month")["tmin"].mean()
dy["avg_tmax"] = dy["month"].map(monthly_tmax)
dy["avg_tmin"] = dy["month"].map(monthly_tmin)

monthly_actual = (dy.groupby("month")["rain"]
                    .sum()
                    .reindex(range(1, 13), fill_value=0))
monthly_mean   = (hist.groupby(["year", "month"])["rain"]
                      .sum()
                      .groupby("month").mean()
                      .reindex(range(1, 13), fill_value=0))

# ── Plotly interactive chart ────────────────────────────────────────────────────
import plotly.graph_objects as go
from plotly.subplots import make_subplots

TITLE_FONT = dict(size=13, color="#444")
AXIS_FONT  = dict(size=11)
GRID_COLOR = "rgba(0,0,0,0.07)"

st.markdown(f"### Year \u2014 {target_year}")

fig1 = make_subplots(rows=2, cols=1, shared_xaxes=False,
                     row_heights=[0.58, 0.42], vertical_spacing=0.14,
                     subplot_titles=[f"Temperature (\u00b0C) \u2014 {target_year}",
                                     f"Rainfall (mm) \u2014 {target_year} monthly vs long-term mean"])

x = dy.index
fig1.add_trace(go.Scatter(x=x, y=dy["tmax"], name="Daily max",
    line=dict(color="rgba(192,57,43,0.9)", width=1), mode="lines"), row=1, col=1)
fig1.add_trace(go.Scatter(x=x, y=dy["tmin"], name="Daily min",
    line=dict(color="rgba(41,128,185,0.9)", width=1),
    fill="tonexty", fillcolor="rgba(150,180,210,0.12)", mode="lines"), row=1, col=1)
fig1.add_trace(go.Scatter(x=x, y=dy["avg_tmax"], name="Avg max",
    line=dict(color="rgba(230,126,34,1)", width=1.5, dash="dash"), mode="lines"), row=1, col=1)
fig1.add_trace(go.Scatter(x=x, y=dy["avg_tmin"], name="Avg min",
    line=dict(color="rgba(142,68,173,1)", width=1.5, dash="dash"), mode="lines"), row=1, col=1)

fig1.add_trace(go.Bar(x=MONTH_NAMES, y=monthly_actual.values.round(1),
    name=f"{target_year} monthly total", marker_color="rgba(26,82,118,0.75)"), row=2, col=1)
fig1.add_trace(go.Scatter(x=MONTH_NAMES, y=monthly_mean.values.round(1),
    name="Long-term mean", line=dict(color="rgba(26,188,156,0.95)", width=2),
    mode="lines+markers", marker=dict(size=5)), row=2, col=1)

fig1.update_layout(height=560, margin=dict(l=50, r=20, t=50, b=80),
    legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.1, font=AXIS_FONT),
    plot_bgcolor="white", paper_bgcolor="white", hovermode="x unified", bargap=0.15)
for ann in fig1.layout.annotations:
    ann.update(font=TITLE_FONT, x=0.5, xanchor="center")
fig1.update_xaxes(showgrid=False, tickformat="%b", tickfont=AXIS_FONT, row=1, col=1)
fig1.update_xaxes(showgrid=False, tickfont=AXIS_FONT, row=2, col=1)
fig1.update_yaxes(gridcolor=GRID_COLOR, tickfont=AXIS_FONT)
fig1.update_yaxes(title_text="\u00b0C", row=1, col=1, title_font=AXIS_FONT)
fig1.update_yaxes(title_text="mm", row=2, col=1, title_font=AXIS_FONT, rangemode="tozero")
st.plotly_chart(fig1, width="stretch", key="snap_fig1")

# ── Export (JPEG) ─────────────────────────────────────────────────────────────
meta_str  = (f"Station {sid} \u00b7 {station.get('state','')} \u00b7 "
             f"{lat:.3f}, {lon:.3f}" if lat is not None and lon is not None
             else f"Station {sid}")
safe_name = station["name"].replace(" ", "_")


def _build_jpeg() -> io.BytesIO:
    C = dict(
        tmax="tab:red", tmin="tab:blue", fill="lightsteelblue",
        avg_tmax="#e67e22", avg_tmin="#8e44ad",
        rain_bar="#1a5276", rain_mean="#1abc9c",
    )
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 9), dpi=120, facecolor="white",
                                    gridspec_kw={"height_ratios": [1.4, 1.0], "hspace": 0.4})
    fig.suptitle(f"{station['name']}  \u00b7  {meta_str}", fontsize=13, y=0.98, color="#333")

    xd = dy.index
    ax1.fill_between(xd, dy["tmin"], dy["tmax"], color=C["fill"], alpha=0.35, linewidth=0)
    ax1.plot(xd, dy["tmax"],     color=C["tmax"],     lw=0.8, label="Daily max")
    ax1.plot(xd, dy["tmin"],     color=C["tmin"],     lw=0.8, label="Daily min")
    ax1.plot(xd, dy["avg_tmax"], color=C["avg_tmax"], lw=1.4, ls="--", label="Avg max")
    ax1.plot(xd, dy["avg_tmin"], color=C["avg_tmin"], lw=1.4, ls="--", label="Avg min")
    ax1.set_title(f"Temperature (\u00b0C) \u2014 {target_year}", fontsize=11, pad=6, color="#444")
    ax1.set_ylabel("\u00b0C", fontsize=10)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax1.xaxis.set_major_locator(mdates.MonthLocator())
    ax1.set_xlim(xd[0], xd[-1])
    ax1.tick_params(labelsize=9)
    ax1.grid(axis="y", color="0.92", linewidth=0.7)
    ax1.spines[["top", "right"]].set_visible(False)

    xi = np.arange(12)
    ax2.bar(xi, monthly_actual.values, color=C["rain_bar"], alpha=0.85,
            label=f"{target_year} monthly total", zorder=2)
    ax2.plot(xi, monthly_mean.values, color=C["rain_mean"], lw=2, marker="o", ms=4,
             label="Long-term mean", zorder=3)
    ax2.set_title(f"Rainfall (mm) \u2014 {target_year} monthly vs long-term mean",
                  fontsize=11, pad=6, color="#444")
    ax2.set_ylabel("mm", fontsize=10)
    ax2.set_xticks(xi)
    ax2.set_xticklabels(MONTH_NAMES, fontsize=9)
    ax2.set_ylim(bottom=0)
    ax2.tick_params(labelsize=9)
    ax2.grid(axis="y", color="0.92", linewidth=0.7)
    ax2.spines[["top", "right"]].set_visible(False)

    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    fig.legend(h1 + h2, l1 + l2, loc="lower center", ncol=6, fontsize=9,
               frameon=False, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=[0, 0.05, 1, 0.95])

    buf = io.BytesIO()
    fig.savefig(buf, format="jpeg", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


col_l, col_c, col_r = st.columns([1, 2, 1])
with col_c:
    with st.spinner("Generating image\u2026"):
        jpeg_buf = _build_jpeg()
    st.download_button(
        "\U0001F4E5  Download snapshot (JPEG)",
        data=jpeg_buf,
        file_name=f"{safe_name}_{target_year}_snapshot.jpg",
        mime="image/jpeg",
        width="stretch",
    )
