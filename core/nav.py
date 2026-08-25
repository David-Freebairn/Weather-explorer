"""
core/nav.py
============
Central definition of Weather Explorer's pages as StreamlitPage objects.

Both the entrypoint (Menu.py) and every page script import these same
objects, so cross-page links use st.page_link(PAGE_OBJECT, ...) instead
of a filename string. Filename-string matching in st.page_link/
st.switch_page is known to be fragile — it depends on exactly how and
from where `streamlit run` was invoked, and has a history of
`StreamlitPageNotFoundError`s across different OSes/working directories
(see streamlit/streamlit#8070 and related issues). Object references
sidestep that whole class of bug.

Pages are grouped into two sidebar sections (see SECTIONS below):
  - "Current weather, future odds" — in-season, act-on-it-now pages.
  - "History"                       — historical/climatological context.
"""

import streamlit as st

HOME     = st.Page("home.py", title="Menu", icon="\U0001F3E0", default=True)
RAINFALL = st.Page("pages/1_Rainfall_chart.py", title="Rainfall chart")
MONTHLY  = st.Page("pages/2_Monthly_averages.py", title="Climate by month")
SNAPSHOT = st.Page("pages/3_Snapshot.py", title="Snapshot")
SEASON   = st.Page("pages/4_Season.py", title="Season?")
ODDS     = st.Page("pages/5_Odds.py", title="What chance?")
HOWWET   = st.Page("pages/6_Howwet.py", title="Howwet +N")
TREND    = st.Page("pages/7_Trend.py", title="Trend vs variability")

ALL_PAGES = [HOME, SEASON, HOWWET, ODDS, SNAPSHOT, TREND, RAINFALL, MONTHLY]

SECTIONS = {
    "": [HOME],
    "Current weather, future odds": [SEASON, HOWWET, ODDS],
    "History":                      [SNAPSHOT, TREND, RAINFALL, MONTHLY],
}
