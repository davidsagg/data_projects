"""Streamlit entry point for MusicDNA AI."""

import os

import streamlit as st

# Configuracao da pagina:
st.set_page_config(
    page_title="MusicDNA AI",
    page_icon=":musical_note:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Constante da URL da API (lida do ambiente):
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

# Sidebar com navegacao:
st.sidebar.title("MusicDNA AI")
st.sidebar.markdown("---")
pagina = st.sidebar.radio(
    "Navegar para:",
    ["Sync Licensing Matcher", "Jam Session Simulator", "Dashboard"],
    index=0,
)

# Roteamento de paginas:
if pagina == "Sync Licensing Matcher":
    from src.ui.pages.sync_matcher import render

    render(API_BASE)
elif pagina == "Jam Session Simulator":
    from src.ui.pages.jam_session import render

    render(API_BASE)
elif pagina == "Dashboard":
    from src.ui.pages.dashboard import render

    render(API_BASE)
