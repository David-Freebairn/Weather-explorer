"""
Menu.py — Weather Explorer entrypoint
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Thin router. All it does is set global page config once, then hand off
to the page picked in the sidebar via st.navigation/st.Page — see
core/nav.py for the page list, and home.py for the actual Menu content.

Run locally with:  streamlit run Menu.py
Deploy main file:   Menu.py
"""

from pathlib import Path
import streamlit as st

_ICON_PATH = Path(__file__).resolve().parent / "assets" / "we_icon.png"

st.set_page_config(
    page_title="Weather Explorer",
    page_icon=str(_ICON_PATH) if _ICON_PATH.exists() else "\U0001F326\uFE0F",
    layout="wide",
)

from core.nav import SECTIONS  # noqa: E402  (must follow set_page_config)

# Built-in sectioned sidebar nav is hidden and rebuilt manually below as a
# flat, always-visible list — the built-in one renders section headers as
# collapsible/expandable, which added an extra click to get to pages and
# wasn't wanted here.
pg = st.navigation(SECTIONS, position="hidden")

with st.sidebar:
    for section_label, pages in SECTIONS.items():
        if section_label:
            st.markdown(f"**{section_label}**")
        for p in pages:
            st.page_link(p)
        st.write("")

pg.run()
