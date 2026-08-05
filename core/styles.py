"""
core/styles.py
===============
Small shared helpers for Weather Explorer:
  - apply_styles(): light global CSS tweaks
  - save_station()/load_station(): station selection shared across pages
    via st.session_state (Streamlit keeps session_state alive across
    multipage navigation within the same browser session, so no on-disk
    hand-off file is needed here, unlike RiskAware/Howwet+).
"""

import streamlit as st

_CSS = """
<style>
.section-title {
    font-weight: 600;
    font-size: 0.95rem;
    color: #333;
    margin-bottom: 0.4rem;
}
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 10px;
}

/* Analysis cards on the Menu page (scoped to we_card_1 / _2 / _3 containers) */
[class*="st-key-we_card_"] {
    text-align: center;
}
[class*="st-key-we_card_"] [data-testid="stPageLink"] {
    display: flex;
    justify-content: center;
    margin-top: 0.8rem;
    padding-top: 0.6rem;
    border-top: 1px solid #eee;
}
[class*="st-key-we_card_"] [data-testid="stPageLink"] p {
    font-weight: 600;
    font-size: 1rem;
    color: #1a5276;
    margin: 0;
}
[class*="st-key-we_card_"] [data-testid="stPageLink"]:hover {
    background: #f5f8fa;
}
</style>
"""


def apply_styles():
    st.markdown(_CSS, unsafe_allow_html=True)


def save_station(station: dict | None) -> None:
    """Store the selected station in session_state, shared by all pages."""
    st.session_state["we_station"] = station


def load_station() -> dict | None:
    """Retrieve the currently selected station, if any."""
    return st.session_state.get("we_station")
