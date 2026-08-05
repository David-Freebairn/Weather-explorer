"""
pages/1_Rainfall_chart.py — Weather Explorer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"When the rain fell" — a digitised version of the classic paper rain
diary: days down the side, months across the top, daily totals (mm)
in the grid, with a Total and long-term Average row underneath.

Two views:
  • Year grid      — the full calendar year, all 12 months at once
  • Month calendar  — a single month laid out as a wall calendar
                      (Mon–Sun weeks), for a closer look at recent rain

Uses the shared SILO full-record cache from core/silo.py (1900 → current).
"""

import calendar
import io
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import numpy as np
import pandas as pd
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


st.markdown("## Rainfall chart")
st.caption("When the rain fell")

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
available_years = sorted(df["year"].unique())
today = date.today()

c1, c2 = st.columns([2, 5])
with c1:
    st.success(f"\U0001F4CD {station.get('label', station.get('name', ''))}")
with c2:
    st.page_link(HOME, label="Change station")

view = st.radio(
    "View", options=["Year grid", "Month calendar"],
    horizontal=True, label_visibility="collapsed",
)

# ═════════════════════════════════════════════════════════════════════════════
# VIEW 1 — full calendar year grid
# ═════════════════════════════════════════════════════════════════════════════
if view == "Year grid":
    default_year = available_years[-1]
    year = st.number_input(
        "Year", min_value=int(available_years[0]), max_value=int(available_years[-1]),
        value=int(default_year), step=1, key="rc_year",
    )

    dy   = df[df["year"] == year]
    hist = df[df["year"] != year]

    if dy.empty:
        st.warning(f"No data for {year} at this station.")
        st.stop()

    pivot = (dy.pivot_table(index="day", columns="month", values="rain", aggfunc="sum")
               .reindex(index=range(1, 32), columns=range(1, 13)))

    monthly_total = dy.groupby("month")["rain"].sum().reindex(range(1, 13), fill_value=0.0)
    monthly_avg   = (hist.groupby(["year", "month"])["rain"].sum()
                          .groupby("month").mean()
                          .reindex(range(1, 13), fill_value=0.0))

    def _rain_color(v):
        """Light-to-dark blue scale, roughly matching typical daily falls."""
        if pd.isna(v) or v <= 0:
            return "#ffffff"
        stops = [(0, (255, 255, 255)), (5, (222, 235, 247)), (15, (158, 202, 225)),
                  (30, (66, 146, 198)), (60, (33, 102, 172)), (120, (8, 48, 107))]
        for i in range(len(stops) - 1):
            lo_v, lo_c = stops[i]
            hi_v, hi_c = stops[i + 1]
            if v <= hi_v:
                f = (v - lo_v) / (hi_v - lo_v) if hi_v > lo_v else 1.0
                rgb = tuple(int(lo_c[j] + f * (hi_c[j] - lo_c[j])) for j in range(3))
                return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        return "#08306b"

    def _text_color(bg_hex):
        r, g, b = int(bg_hex[1:3], 16), int(bg_hex[3:5], 16), int(bg_hex[5:7], 16)
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        return "#ffffff" if lum < 140 else "#222222"

    # ── Build HTML table ────────────────────────────────────────────────────
    cell_style = "padding:3px 6px;text-align:center;font-size:0.78rem;border:1px solid #eee;"
    head_style = cell_style + "font-weight:600;background:#f5f5f5;"
    day_style  = cell_style + "font-weight:500;background:#fafafa;color:#888;"

    html = ['<table style="border-collapse:collapse;width:100%;">']
    html.append("<tr>" + f'<th style="{head_style}">Date</th>' +
                "".join(f'<th style="{head_style}">{m}</th>' for m in MONTH_NAMES) + "</tr>")

    for d in range(1, 32):
        row = [f'<td style="{day_style}">{d}</td>']
        for m in range(1, 13):
            v = pivot.loc[d, m] if d in pivot.index else np.nan
            if pd.isna(v):
                row.append(f'<td style="{cell_style}"></td>')
            elif v <= 0:
                row.append(f'<td style="{cell_style}"></td>')
            else:
                bg = _rain_color(v)
                fg = _text_color(bg)
                row.append(f'<td style="{cell_style}background:{bg};color:{fg};">{v:.1f}</td>')
        html.append("<tr>" + "".join(row) + "</tr>")

    total_style = cell_style + "font-weight:700;background:#eef3f8;border-top:2px solid #999;"
    avg_style   = cell_style + "font-style:italic;color:#555;background:#f8f8f8;"
    html.append("<tr>" + f'<td style="{total_style}">Total</td>' +
                "".join(f'<td style="{total_style}">{monthly_total[m]:.0f}</td>' for m in range(1, 13)) + "</tr>")
    html.append("<tr>" + f'<td style="{avg_style}">Long-term avg</td>' +
                "".join(f'<td style="{avg_style}">{monthly_avg[m]:.0f}</td>' for m in range(1, 13)) + "</tr>")
    html.append("</table>")

    st.markdown(f"### {station['name']} \u2014 {year}")
    st.markdown("".join(html), unsafe_allow_html=True)
    st.caption(
        f"Record used for the long-term average: {int(hist['year'].min())}\u2013"
        f"{int(hist['year'].max())} ({hist['year'].nunique()} years), excluding {year}."
    )

    # ── Downloads ────────────────────────────────────────────────────────────
    csv_df = pivot.copy()
    csv_df.columns = MONTH_NAMES
    csv_df.index.name = "Date"
    csv_bytes = csv_df.to_csv().encode("utf-8")

    dcol1, dcol2 = st.columns(2)
    with dcol1:
        st.download_button(
            "\U0001F4E5  Download grid (CSV)", data=csv_bytes,
            file_name=f"{station['name'].replace(' ', '_')}_{year}_rainfall_grid.csv",
            mime="text/csv", width="stretch",
        )

    def _build_grid_jpeg():
        fig, ax = plt.subplots(figsize=(13, 9), dpi=130)
        ax.axis("off")
        ax.set_title(f"{station['name']} \u2014 Rainfall (mm) \u2014 {year}", fontsize=13, pad=14)

        n_rows, n_cols = 33, 13  # header + 31 days + total + avg ; date col + 12 months
        cell_w, cell_h = 1.0, 1.0

        def draw_cell(r, c, text, bg="white", fg="#222", bold=False, italic=False, fs=8):
            x, y = c * cell_w, (n_rows - r) * cell_h
            ax.add_patch(plt.Rectangle((x, y - cell_h), cell_w, cell_h,
                                        facecolor=bg, edgecolor="#e5e5e5", linewidth=0.5))
            weight = "bold" if bold else ("normal")
            style  = "italic" if italic else "normal"
            ax.text(x + cell_w / 2, y - cell_h / 2, text, ha="center", va="center",
                     fontsize=fs, color=fg, fontweight=weight, fontstyle=style)

        draw_cell(0, 0, "Date", bg="#f5f5f5", bold=True)
        for ci, m in enumerate(MONTH_NAMES):
            draw_cell(0, ci + 1, m, bg="#f5f5f5", bold=True)

        for d in range(1, 32):
            draw_cell(d, 0, str(d), bg="#fafafa", fg="#888")
            for m in range(1, 13):
                v = pivot.loc[d, m] if d in pivot.index else np.nan
                if pd.isna(v) or v <= 0:
                    draw_cell(d, m, "")
                else:
                    bg = _rain_color(v)
                    draw_cell(d, m, f"{v:.1f}", bg=bg, fg=_text_color(bg))

        draw_cell(32, 0, "Total", bg="#eef3f8", bold=True)
        for m in range(1, 13):
            draw_cell(32, m, f"{monthly_total[m]:.0f}", bg="#eef3f8", bold=True)

        ax.set_xlim(0, n_cols)
        ax.set_ylim(0, n_rows)
        buf = io.BytesIO()
        fig.savefig(buf, format="jpeg", dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        buf.seek(0)
        return buf

    with dcol2:
        with st.spinner("Generating image\u2026"):
            jpeg_buf = _build_grid_jpeg()
        st.download_button(
            "\U0001F5BC\uFE0F  Download grid (JPEG)", data=jpeg_buf,
            file_name=f"{station['name'].replace(' ', '_')}_{year}_rainfall_grid.jpg",
            mime="image/jpeg", width="stretch",
        )

# ═════════════════════════════════════════════════════════════════════════════
# VIEW 2 — single month, wall-calendar layout
# ═════════════════════════════════════════════════════════════════════════════
else:
    c1, c2 = st.columns(2)
    with c1:
        year = st.number_input(
            "Year", min_value=int(available_years[0]), max_value=int(available_years[-1]),
            value=int(today.year), step=1, key="rc_month_year",
        )
    with c2:
        month = st.selectbox("Month", options=list(range(1, 13)),
                              format_func=lambda m: MONTH_NAMES[m - 1],
                              index=today.month - 1, key="rc_month_month")

    dm = df[(df["year"] == year) & (df["month"] == month)]
    rain_by_day = dm.set_index("day")["rain"].to_dict()

    cal = calendar.Calendar(firstweekday=0)  # Monday first
    weeks = cal.monthdayscalendar(year, month)

    def _rain_color(v):
        if v is None or v <= 0:
            return "#ffffff"
        stops = [(0, (255, 255, 255)), (5, (222, 235, 247)), (15, (158, 202, 225)),
                  (30, (66, 146, 198)), (60, (33, 102, 172)), (120, (8, 48, 107))]
        for i in range(len(stops) - 1):
            lo_v, lo_c = stops[i]
            hi_v, hi_c = stops[i + 1]
            if v <= hi_v:
                f = (v - lo_v) / (hi_v - lo_v) if hi_v > lo_v else 1.0
                rgb = tuple(int(lo_c[j] + f * (hi_c[j] - lo_c[j])) for j in range(3))
                return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        return "#08306b"

    def _text_color(bg_hex):
        r, g, b = int(bg_hex[1:3], 16), int(bg_hex[3:5], 16), int(bg_hex[5:7], 16)
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        return "#ffffff" if lum < 140 else "#222222"

    st.markdown(f"### {station['name']} \u2014 {MONTH_NAMES[month - 1]} {year}")

    weekday_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    head_style = "padding:6px;text-align:center;font-size:0.8rem;font-weight:600;background:#f5f5f5;border:1px solid #eee;"
    cell_style = "padding:8px 4px;text-align:center;vertical-align:top;border:1px solid #eee;height:56px;width:14.28%;"

    html = ['<table style="border-collapse:collapse;width:100%;">']
    html.append("<tr>" + "".join(f'<th style="{head_style}">{w}</th>' for w in weekday_labels) + "</tr>")
    is_current_month = (year == today.year and month == today.month)
    for week in weeks:
        row = []
        for d in week:
            if d == 0:
                row.append(f'<td style="{cell_style}background:#fbfbfb;"></td>')
                continue
            v = rain_by_day.get(d)
            bg = _rain_color(v)
            fg = _text_color(bg)
            border = "border:2px solid #e74c3c;" if (is_current_month and d == today.day) else ""
            rain_txt = f'<div style="font-size:0.85rem;margin-top:2px;">{v:.1f}mm</div>' if v and v > 0 else ""
            row.append(
                f'<td style="{cell_style}background:{bg};color:{fg};{border}">'
                f'<div style="font-size:0.75rem;color:#999;">{d}</div>{rain_txt}</td>'
            )
        html.append("<tr>" + "".join(row) + "</tr>")
    html.append("</table>")
    st.markdown("".join(html), unsafe_allow_html=True)

    month_total = float(dm["rain"].sum()) if not dm.empty else 0.0
    st.caption(f"Month total: {month_total:.0f} mm \u00b7 {int((dm['rain'] > 0).sum())} rain days")
