"""
Menu.py — Weather Explorer entrypoint
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Thin router. All it does is set global page config once, then hand off
to the page picked in the sidebar via st.navigation/st.Page — see
core/nav.py for the page list, and home.py for the actual Menu content.

Run locally with:  streamlit run Menu.py
Deploy main file:   Menu.py
"""

import streamlit as st

st.set_page_config(page_title="Weather Explorer", layout="wide")

from core.nav import ALL_PAGES  # noqa: E402  (must follow set_page_config)

pg = st.navigation(ALL_PAGES)
pg.run()
