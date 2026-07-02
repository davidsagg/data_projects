"""Dashboard page for MusicDNA AI Streamlit app."""

import glob
import os

import requests
import streamlit as st

from src.ui.helpers import parse_health


def render(api_base: str) -> None:
    """Renders the Dashboard — Status do Sistema page.

    Args:
        api_base: Base URL of the MusicDNA AI API.
    """
    st.title("Dashboard - Status do Sistema")

    if st.button("Atualizar Status"):
        st.rerun()

    # Status da API:
    try:
        r = requests.get(f"{api_base}/health", timeout=5)
        health = parse_health(r.json()) if r.status_code == 200 else parse_health({})
    except Exception:
        health = parse_health({})

    col1, col2 = st.columns(2)
    col1.metric(
        "API FastAPI", health["api_label"], delta="Porta 8000", delta_color="normal"
    )
    col2.metric(
        "Ollama llama3",
        health["ollama_label"],
        delta="Porta 11434",
        delta_color="normal",
    )

    st.divider()

    # Metricas do ChromaDB e DuckDB:
    try:
        from src.matching.catalog_store import CatalogStore
        from src.matching.vector_store import VectorStore

        vs = VectorStore(persist_dir="/workspace/data/embeddings/chroma")
        cat = CatalogStore(db_path="/workspace/data/catalog.duckdb")
        total_tracks = vs.count()
        genre_data = cat.db.execute(
            "SELECT genre, COUNT(*) FROM catalog GROUP BY genre ORDER BY COUNT(*) DESC"
        ).fetchall()
    except Exception:
        total_tracks = 0
        genre_data = []

    try:
        sessions = glob.glob("/workspace/data/sessions/*.mid")
        total_sessions = len(sessions)
    except Exception:
        total_sessions = 0

    col3, col4 = st.columns(2)
    col3.metric("Faixas Indexadas", total_tracks)
    col4.metric("Sessoes Jam Geradas", total_sessions)

    if genre_data:
        st.subheader("Faixas por Genero")
        import pandas as pd

        df = pd.DataFrame(genre_data, columns=["Genero", "Total"])
        st.bar_chart(df.set_index("Genero"))

    st.divider()
    st.subheader("Ultimas 10 Faixas Indexadas")
    try:
        rows = cat.db.execute(
            "SELECT job_id, title, artist, genre, bpm, mood, created_at"
            " FROM catalog ORDER BY created_at DESC LIMIT 10"
        ).fetchall()
        if rows:
            import pandas as pd

            cols = ["job_id", "Titulo", "Artista", "Genero", "BPM", "Mood", "Criado em"]
            df = pd.DataFrame(rows, columns=cols)
            df["job_id"] = df["job_id"].str[:8] + "..."
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Nenhuma faixa indexada ainda.")
    except Exception:
        st.info("Catalogo nao disponivel.")
