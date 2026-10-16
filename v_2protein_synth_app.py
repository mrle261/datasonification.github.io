"""
Data Sonification — Bradley Lab
© 2026 University of Kentucky

The whole app (sequence viewer, mutation tools, Tone.js audio) lives in
index.html so it can also be served as a static page on GitHub Pages.
This file embeds that page in Streamlit as a component; the page reports
its own height, so the frame always fits the content.

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
[data-testid="stVerticalBlock"] { gap: 0 !important; }
iframe { display: block; }
</style>
""",
    unsafe_allow_html=True,
)

# Serves index.html from this folder; height comes from the page itself
data_sonification = components.declare_component(
    "data_sonification", path=str(Path(__file__).parent)
)
data_sonification(default=None)
