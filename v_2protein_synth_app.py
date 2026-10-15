"""
Data Sonification — Bradley Lab
© 2026 University of Kentucky

The whole app (sequence viewer, mutation tools, Tone.js audio) lives in
index.html so it can also be served as a static page on GitHub Pages.
This file embeds that page in Streamlit.

Run with: streamlit run v_2protein_synth_app.py
"""

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Data Sonification · Bradley Lab",
    page_icon="🧬",
    layout="wide",
)

# Let the embedded page use the full window
st.markdown(
    """
<style>
header[data-testid="stHeader"], footer { display: none; }
.block-container { padding: 0 !important; max-width: 100% !important; }
</style>
""",
    unsafe_allow_html=True,
)

APP_HTML = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")
components.html(APP_HTML, height=1700, scrolling=True)
