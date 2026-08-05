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
"""

import streamlit as st

HOME     = st.Page("home.py", title="Menu", icon="\U0001F3E0", default=True)
RAINFALL = st.Page("pages/1_Rainfall_chart.py", title="Rainfall chart")
MONTHLY  = st.Page("pages/2_Monthly_averages.py", title="Monthly averages")
SNAPSHOT = st.Page("pages/3_Snapshot.py", title="Snapshot")

ALL_PAGES = [HOME, RAINFALL, MONTHLY, SNAPSHOT]
