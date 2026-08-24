"""
pages/4_Season.py — Weather Explorer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Season's comparison — how this season's cumulative rainfall compares to
every year on record, plus a forward-looking plume for the next N months.

Ported from RiskAware's "How's the season?" page, adapted to Weather
Explorer's shared-station pattern (station picked once on Menu, no
separate per-page station picker / start-year control), with three
additions on top of the original:
  - Chart is twice the vertical size of the original.
  - The three most recent complete years are highlighted in the
    look-back spaghetti (distinct colours, heavier line, labelled).
  - A forward-looking 20th/50th/80th-percentile plume for the next N
    months: for every historical year, replay that year's daily
    rainfall for the same forward calendar window onto today's actual
    cumulative total, then take the day-by-day percentile envelope
    across all replays. Same "replay historical years onto today"
    technique as the look-back series and as Howwet+'s PASW plumes.
"""

import io
from calendar import monthrange

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import matplotlib.gridspec as gridspec

import numpy as np
import pandas as pd
import streamlit as st

from core.nav import HOME
from core.silo import ensure_climate_cached, SiloUnavailableError, load_sample_data
from core.styles import apply_styles, load_station

apply_styles()

C_HIST     = "#7ab4d8"
C_MEDIAN   = "#1a4a6e"
C_CURRENT  = "#cc2200"
C_BG       = "#ffffff"
C_GRID     = "#e0e8f0"
C_PLUME    = "#e8a33d"
HIGHLIGHT_COLORS = ["#e8a33d", "#4f9d69", "#7d5ba6"]  # last, 2nd-last, 3rd-last year


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


# ── Helpers ───────────────────────────────────────────────────────────────────

def days_in_month(y: int, m: int) -> int:
    return monthrange(y, m)[1]


def shift_month(y: int, m: int, delta: int):
    idx = (y * 12 + (m - 1)) + delta
    return idx // 12, idx % 12 + 1


def build_rain_lookup(df: pd.DataFrame) -> dict:
    """
    (year, month, day) -> rain, built once per station/dataset and reused
    by both build_series() and build_forward_plume(). Vectorized (zip over
    the underlying arrays) rather than df.iterrows(), which is slow for a
    ~100+ year daily record and was previously being paid twice per rerun.
    """
    return dict(zip(zip(df.index.year, df.index.month, df.index.day), df["rain"].values))


def build_series(df: pd.DataFrame, months_back: int, lookup: dict):
    """
    Look-back series: cumulative rainfall for every historical year,
    aligned to the same calendar window as the current season.
    """
    today = df.index.max().date()
    end_y, end_m, end_d = today.year, today.month, today.day

    start_m, start_y = end_m - months_back, end_y
    while start_m <= 0:
        start_m += 12
        start_y -= 1
    year_offset = end_y - start_y

    data_years = sorted(df.index.year.unique())
    first_end_y = data_years[0] + year_offset

    series = {}
    for ey in range(first_end_y, end_y + 1):
        sy = ey - year_offset
        is_current = (ey == end_y)
        cum = 0.0
        dates, cums = [], []
        missing_streak = 0

        wy, wm, wd = sy, start_m, 1
        stop_m = end_m
        stop_d = end_d if is_current else days_in_month(ey, end_m)

        ok = True
        while True:
            if wy > ey:
                break
            if wy == ey and wm > stop_m:
                break
            if wy == ey and wm == stop_m and wd > stop_d:
                break

            rain = lookup.get((wy, wm, wd))
            if rain is None:
                if not is_current:
                    missing_streak += 1
                    if missing_streak > 5:
                        ok = False
                        break
                rain = 0.0
            else:
                missing_streak = 0

            cum += rain
            dates.append(pd.Timestamp(wy, wm, wd))
            cums.append(cum)

            wd += 1
            if wd > days_in_month(wy, wm):
                wd = 1
                wm += 1
            if wm > 12:
                wm = 1
                wy += 1

        if ok and dates:
            series[ey] = pd.Series(cums, index=dates)

    if not series or end_y not in series:
        return None, end_y, None, None, None

    current = series[end_y]
    current_total = float(current.iloc[-1])
    n_current = len(current)

    comp_years  = [y for y in series if y != end_y and len(series[y]) >= n_current]
    comp_totals = [float(series[y].iloc[n_current - 1]) for y in comp_years]

    if not comp_years:
        return series, end_y, None, None, None

    better = sum(1 for t in comp_totals if t > current_total)
    pctile = round((1 - better / len(comp_years)) * 100)

    median_vals = []
    for i in range(n_current):
        vals = sorted(float(series[y].iloc[i]) for y in comp_years if len(series[y]) > i)
        if not vals:
            median_vals.append(np.nan)
            continue
        mid = len(vals) // 2
        med = (vals[mid - 1] + vals[mid]) / 2 if len(vals) % 2 == 0 else vals[mid]
        median_vals.append(med)

    median_ser = pd.Series(median_vals, index=current.index)
    diff_mm = round(current_total - float(median_ser.iloc[-1]))

    return series, end_y, median_ser, pctile, diff_mm


def _current_forward_dates(today, n_days: int):
    """
    Day-by-day dates starting the day after `today`, for `n_days` days.
    Used as the x-axis for the forward plume: percentile *values* come
    from replaying each historical year's rainfall, but the dates must
    be aligned to the current year's forward window, not to whichever
    historical year a given trajectory's rainfall happened to come from.
    """
    wy, wm, wd = today.year, today.month, today.day
    wd += 1
    if wd > days_in_month(wy, wm):
        wd = 1
        wm += 1
    if wm > 12:
        wm = 1
        wy += 1
    dates = []
    for _ in range(n_days):
        dates.append(pd.Timestamp(wy, wm, wd))
        wd += 1
        if wd > days_in_month(wy, wm):
            wd = 1
            wm += 1
        if wm > 12:
            wm = 1
            wy += 1
    return dates


def build_forward_plume(df: pd.DataFrame, current_year: int, current_total: float,
                         months_forward: int, lookup: dict):
    """
    Forward-looking plume: for every historical year (excluding the
    current one), replay that year's daily rainfall for the calendar
    window immediately following today (same month/day, different
    year) for `months_forward` months, added onto today's actual
    cumulative total. Returns the day-by-day 20th/50th/80th percentile
    across all replayed trajectories, anchored at today's value.
    """
    today = df.index.max().date()
    end_m, end_d = today.month, today.day
    data_years = sorted(df.index.year.unique())

    trajectories = {}
    for hy in data_years:
        if hy == current_year:
            continue

        wy, wm, wd = hy, end_m, end_d
        wd += 1
        if wd > days_in_month(wy, wm):
            wd = 1
            wm += 1
        if wm > 12:
            wm = 1
            wy += 1

        stop_y, stop_m = shift_month(hy, end_m, months_forward)
        stop_d = min(end_d, days_in_month(stop_y, stop_m))

        cum = current_total
        dates, cums = [], []
        missing_streak = 0
        ok = True
        while True:
            if wy > stop_y or (wy == stop_y and wm > stop_m):
                break
            if wy == stop_y and wm == stop_m and wd > stop_d:
                break

            rain = lookup.get((wy, wm, wd))
            if rain is None:
                missing_streak += 1
                if missing_streak > 5:
                    ok = False
                    break
                rain = 0.0
            else:
                missing_streak = 0

            cum += rain
            dates.append(pd.Timestamp(wy, wm, wd))
            cums.append(cum)

            wd += 1
            if wd > days_in_month(wy, wm):
                wd = 1
                wm += 1
            if wm > 12:
                wm = 1
                wy += 1

        if ok and dates:
            trajectories[hy] = pd.Series(cums, index=dates)

    if not trajectories:
        return None

    max_len = max(len(s) for s in trajectories.values())
    full = {y: s for y, s in trajectories.items() if len(s) == max_len} or trajectories
    n = max_len
    ref_dates = _current_forward_dates(today, n)

    p20, p50, p80 = [], [], []
    for i in range(n):
        vals = sorted(float(s.iloc[i]) for s in full.values() if len(s) > i)
        if not vals:
            p20.append(np.nan); p50.append(np.nan); p80.append(np.nan)
            continue
        p20.append(float(np.percentile(vals, 20)))
        p50.append(float(np.percentile(vals, 50)))
        p80.append(float(np.percentile(vals, 80)))

    anchor = pd.Timestamp(today)
    p20_ser = pd.concat([pd.Series([current_total], index=[anchor]), pd.Series(p20, index=ref_dates)])
    p50_ser = pd.concat([pd.Series([current_total], index=[anchor]), pd.Series(p50, index=ref_dates)])
    p80_ser = pd.concat([pd.Series([current_total], index=[anchor]), pd.Series(p80, index=ref_dates)])
    return p20_ser, p50_ser, p80_ser


# ── Chart drawing (shared by the on-screen chart and the JPEG export) ─────────

def _draw_chart(ax, series, current_year, median_ser, highlight_years,
                 plume, months_back, months_forward, station_name):
    current = series[current_year]

    for ey, s in series.items():
        if ey == current_year or ey in highlight_years:
            continue
        n = min(len(s), len(current))
        ax.plot(current.index[:n], s.values[:n], color=C_HIST, lw=0.9, alpha=0.4, zorder=1)

    for i, ey in enumerate(highlight_years):
        s = series.get(ey)
        if s is None:
            continue
        n = min(len(s), len(current))
        color = HIGHLIGHT_COLORS[i % len(HIGHLIGHT_COLORS)]
        ax.plot(current.index[:n], s.values[:n], color=color, lw=1.8, alpha=0.9, zorder=2)

    # End-of-look-back labels (highlighted years + median): declutter so
    # close-together values don't overlap into unreadable text.
    end_labels = []
    for i, ey in enumerate(highlight_years):
        s = series.get(ey)
        if s is None:
            continue
        n = min(len(s), len(current))
        end_labels.append([float(s.values[n - 1]), str(ey),
                            HIGHLIGHT_COLORS[i % len(HIGHLIGHT_COLORS)]])
    if median_ser is not None:
        ax.plot(median_ser.index, median_ser.values, color=C_MEDIAN, lw=2, ls="--", zorder=3)
        last_valid = median_ser.dropna()
        if len(last_valid):
            end_labels.append([float(last_valid.iloc[-1]), "median", C_MEDIAN])

    if end_labels:
        end_labels.sort(key=lambda t: t[0])
        all_vals = [v for s in series.values() for v in s.values] + list(median_ser.dropna().values if median_ser is not None else [])
        y_ref = max(all_vals) if all_vals else 1.0
        min_gap = 0.06 * y_ref
        adj_y = [end_labels[0][0]]
        for val, _, _ in end_labels[1:]:
            adj_y.append(max(val, adj_y[-1] + min_gap))
        label_x = current.index[-1] + pd.Timedelta(days=6)
        for (orig_val, text, color), y_pos in zip(end_labels, adj_y):
            # Small dot at the curve's true value, plus a thin leader line to
            # the (possibly decluttered) label position, so the label stays
            # traceable back to its actual line even when nudged apart.
            ax.plot(current.index[-1], orig_val, "o", color=color, ms=3, zorder=6)
            ax.annotate(text, xy=(current.index[-1], orig_val),
                        xytext=(label_x, y_pos),
                        textcoords="data", xycoords="data",
                        ha="left", va="center", fontsize=8, color=color,
                        fontweight="bold" if text != "median" else "normal",
                        arrowprops=dict(arrowstyle="-", color=color, lw=0.7,
                                         alpha=0.6, shrinkA=0, shrinkB=2))

    ax.plot(current.index, current.values, color=C_CURRENT, lw=2.5, zorder=4,
            label=f"{current_year} (current)")
    ax.plot(current.index[-1], current.values[-1], "o", color=C_CURRENT,
            ms=7, mfc="none", mew=2, zorder=5)
    ax.axvline(current.index[-1], color="#888", lw=1, ls=":", zorder=2)

    if plume is not None:
        p20_ser, p50_ser, p80_ser = plume
        ax.fill_between(p20_ser.index, p20_ser.values, p80_ser.values,
                         color=C_PLUME, alpha=0.22, zorder=2, linewidth=0)
        ax.plot(p50_ser.index, p50_ser.values, color=C_PLUME, lw=1.6, ls="--", zorder=3)
        ax.annotate("80%ile", xy=(p80_ser.index[-1], p80_ser.values[-1]),
                    xytext=(6, 4), textcoords="offset points",
                    fontsize=8.5, color=C_PLUME, va="center", fontweight="bold")
        ax.annotate("20%ile", xy=(p20_ser.index[-1], p20_ser.values[-1]),
                    xytext=(6, -4), textcoords="offset points",
                    fontsize=8.5, color=C_PLUME, va="center", fontweight="bold")

    ax.set_ylabel("Cumulative rainfall (mm)", fontsize=10, color="#555")
    ax.set_ylim(bottom=0)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=6, integer=True))
    ax.tick_params(labelsize=9)
    ax.grid(axis="y", color=C_GRID, lw=0.7, zorder=0)

    n_months = months_back + months_forward
    if n_months <= 14:
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    elif n_months <= 30:
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    else:
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.tick_params(axis="x", labelsize=8.5)
    plt.setp(ax.xaxis.get_majorticklabels(), ha="center")

    ax.set_title(
        f"{station_name}   \u00b7   looking back {months_back} months, "
        f"forward {months_forward} months",
        fontsize=11, color="#1a2332", pad=8, loc="left",
    )
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)


def make_chart(series, current_year, median_ser, highlight_years, plume,
               station_name, months_back, months_forward):
    plt.rcParams.update({
        "font.family": "sans-serif",
        "axes.facecolor": C_BG,
        "figure.facecolor": C_BG,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.8,
    })
    fig, ax = plt.subplots(figsize=(12, 6.3))  # 2x original height, then -30% per feedback
    _draw_chart(ax, series, current_year, median_ser, highlight_years, plume,
                months_back, months_forward, station_name)
    plt.tight_layout(pad=1.2)
    return fig


# ── UI ────────────────────────────────────────────────────────────────────────

st.markdown("## Season")
st.caption("This season's rainfall vs history, and what the next few months could look like")

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

c1, c2, c3, c4 = st.columns([2, 1.6, 1.6, 2])
with c1:
    st.success(f"\U0001F4CD {station.get('label', station.get('name', ''))}")
with c2:
    months_back = st.number_input("Look back (months)", min_value=1, max_value=60,
                                   value=8, step=1, key="se_months_back")
with c3:
    months_forward = st.number_input("Look forward (months)", min_value=1, max_value=24,
                                      value=2, step=1, key="se_months_forward")
with c4:
    st.page_link(HOME, label="Change station")

with st.expander("\u2139\ufe0f About this analysis"):
    st.markdown("""
**Season** compares cumulative rainfall for the current season against every
other year on record, and projects a plausible range for the months ahead.

- The **look-back** side replays every historical year's rainfall over the
  same calendar window as this season, so far. The **percentile** shows
  where this season sits relative to those years; the **dashed line** is
  the median (50th percentile) — half of years were wetter, half drier.
- The three most recent complete years are highlighted so recent trend is
  easy to spot against the full spread.
- The **look-forward plume** replays every historical year's rainfall for
  the months *ahead*, starting from this season's actual total to date.
  The shaded band spans the 20th–80th percentile of those replayed
  outcomes — a rough sense of the range of totals the season could still
  reach, not a forecast.

**Applications**
- An objective read on this season relative to longer-term conditions.
- Use to set expectations for fallow, in-crop rain, and yield.

A copy of the results can be downloaded as an image.
""")

# ── Analysis ──────────────────────────────────────────────────────────────────
rain_lookup = build_rain_lookup(df)
series, current_year, median_ser, pctile, diff_mm = build_series(df, int(months_back), rain_lookup)

if series is None:
    st.warning("Not enough data for this window.")
    st.stop()
if pctile is None:
    st.warning("Not enough comparable years to calculate a percentile.")
    st.stop()

current_total = float(series[current_year].iloc[-1])
highlight_years = [y for y in (current_year - 1, current_year - 2, current_year - 3)
                    if y in series]

plume = build_forward_plume(df, current_year, current_total, int(months_forward), rain_lookup)

diff_sign = "+" if diff_mm >= 0 else ""  # noqa: F841 (kept for readability at call sites)
diff_dir  = "above" if diff_mm >= 0 else "below"
abs_diff  = abs(diff_mm)

data_years = sorted(df.index.year.unique())
min_y, max_y = data_years[0], data_years[-1]
ann_mean = int(df.groupby(df.index.year)["rain"].sum().mean())
name = station.get("name", "")

st.markdown(f"""
<div style="background:#f0f6ff; border-radius:10px; padding:18px 22px 14px 22px; margin-bottom:4px;">
  <div style="font-size:1.45rem; font-weight:700; color:#1a3a5c; margin-bottom:2px;">
    Season's comparison
  </div>
  <div style="font-size:0.95rem; color:#444; margin-bottom:10px;">
    <b>{name}</b>&nbsp;&nbsp;
    <span style="color:#888;">({min_y}\u2013{max_y})</span>&nbsp;&nbsp;
    Mean annual rainfall <b>{ann_mean} mm</b>
  </div>
  <div style="display:flex; align-items:baseline; gap:0; flex-wrap:wrap;">
    <span style="font-size:1.02rem; color:#444; font-weight:500;">Rainfall in the last&nbsp;</span>
    <span style="font-size:1.02rem; color:#e06b00; font-weight:700;">{months_back} month{"s" if months_back != 1 else ""}</span>
    <span style="font-size:1.02rem; color:#444; font-weight:500;">&nbsp;is in the&nbsp;</span>
    <span style="font-size:1.02rem; color:#2979c4; font-weight:700;">{pctile} %ile</span>
    <span style="font-size:1.02rem; color:#888; font-weight:400;">&nbsp;( {abs_diff} mm {diff_dir} the average )</span>
  </div>
</div>
""", unsafe_allow_html=True)

fig = make_chart(series, current_year, median_ser, highlight_years, plume,
                 name, int(months_back), int(months_forward))
st.pyplot(fig, width="stretch")
plt.close(fig)

# ── Composite JPEG download (header panel + chart) ─────────────────────────────
# Built only on request, not on every rerun — matplotlib composition here
# costs real time (a header panel with hand-laid-out text plus a full
# re-draw of the chart), and most reruns are just the user adjusting the
# months sliders, not asking to download.


def _build_composite_jpeg() -> io.BytesIO:
    PANEL_H, CHART_H, DPI = 1.5, 6.3, 150

    comp_fig = plt.figure(figsize=(12, PANEL_H + CHART_H), facecolor="white")
    spec = gridspec.GridSpec(2, 1, figure=comp_fig, height_ratios=[PANEL_H, CHART_H], hspace=0.0)

    hax = comp_fig.add_subplot(spec[0])
    hax.set_facecolor("#f0f6ff")
    hax.set_xlim(0, 1); hax.set_ylim(0, 1)
    hax.axis("off")
    hax.text(0.012, 0.95, "Season's comparison", ha="left", va="top",
              fontsize=14, fontweight="bold", color="#1a3a5c", transform=hax.transAxes)
    hax.text(0.012, 0.68, f"{name}    ({min_y}\u2013{max_y})    Mean annual rainfall {ann_mean} mm",
              ha="left", va="top", fontsize=9.5, color="#444", transform=hax.transAxes)

    parts = [
        ("Rainfall in the last ", "#444", False),
        (f"{months_back} month{'s' if months_back != 1 else ''}", "#e06b00", True),
        (" is in the ", "#444", False),
        (f"{pctile} %ile", "#2979c4", True),
        (f"  ( {abs_diff} mm {diff_dir} the average )", "#888", False),
    ]
    comp_fig.canvas.draw()
    renderer = comp_fig.canvas.get_renderer()
    ax_bbox = hax.get_window_extent(renderer=renderer)
    x_cur, y_row = 0.012, 0.28
    for txt, col, bold in parts:
        t = hax.text(x_cur, y_row, txt, ha="left", va="top", fontsize=10.5,
                     fontweight="bold" if bold else "normal", color=col, transform=hax.transAxes)
        comp_fig.canvas.draw()
        bb = t.get_window_extent(renderer=renderer)
        x_cur += bb.width / ax_bbox.width

    cax = comp_fig.add_subplot(spec[1])
    cax.set_facecolor(C_BG)
    _draw_chart(cax, series, current_year, median_ser, highlight_years, plume,
                int(months_back), int(months_forward), name)
    cax.set_title("")  # header panel already carries the title

    comp_fig.tight_layout(pad=0.8)

    buf = io.BytesIO()
    comp_fig.savefig(buf, format="jpeg", dpi=DPI, bbox_inches="tight", facecolor="white")
    buf.seek(0)
    plt.close(comp_fig)
    return buf


dl_key = f"season_jpeg::{sid}::{months_back}::{months_forward}"
col_l, col_c, col_r = st.columns([1, 2, 1])
with col_c:
    if st.button("\U0001F4E5  Prepare download image (JPEG)", width="stretch"):
        with st.spinner("Generating image\u2026"):
            st.session_state[dl_key] = _build_composite_jpeg().getvalue()
    if dl_key in st.session_state:
        st.download_button(
            "\U0001F5BC\uFE0F  Download chart (JPEG)", data=st.session_state[dl_key],
            file_name=f"season_{name.replace(' ', '_')}_{months_back}mo.jpg",
            mime="image/jpeg", width="stretch",
        )
