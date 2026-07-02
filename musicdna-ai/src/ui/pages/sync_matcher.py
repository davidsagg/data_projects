"""Sync Licensing Matcher page for MusicDNA AI Streamlit app."""

import requests
import streamlit as st

from src.ui.helpers import build_ingest_payload, format_match_results, score_display


def render(api_base: str) -> None:
    """Renders the Sync Licensing Matcher page.

    Args:
        api_base: Base URL of the MusicDNA AI API.
    """
    st.title("Sync Licensing Matcher")
    st.markdown("Indexe faixas e encontre matches para seu projeto.")

    # --- SECAO: Indexar faixa ---
    with st.expander("Indexar nova faixa", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            audio_file = st.file_uploader(
                "Arquivo de audio", type=["wav", "mp3", "flac"]
            )
            title = st.text_input("Titulo")
            artist = st.text_input("Artista")
        with col2:
            genre = st.selectbox(
                "Genero",
                ["jazz", "mpb", "rock", "electronic", "ambient", "classical", "other"],
            )
            bpm = st.number_input("BPM", min_value=40, max_value=240, value=120)
            mood = st.selectbox(
                "Mood",
                [
                    "relaxado",
                    "animado",
                    "melancolico",
                    "energetico",
                    "alegre",
                    "triste",
                ],
            )

        if st.button("Indexar Faixa", type="primary"):
            if audio_file is None:
                st.error("Selecione um arquivo de audio.")
            else:
                with st.spinner("Processando audio..."):
                    try:
                        payload = build_ingest_payload(
                            {
                                "title": title,
                                "artist": artist,
                                "genre": genre,
                                "bpm": bpm,
                                "mood": mood,
                            }
                        )
                        files = {
                            "audio_file": (
                                audio_file.name,
                                audio_file.getvalue(),
                                "audio/wav",
                            )
                        }
                        r = requests.post(
                            f"{api_base}/ingest",
                            files=files,
                            data=payload,
                            timeout=120,
                        )
                        if r.status_code == 200:
                            st.success(
                                f"Faixa indexada! job_id: {r.json()['job_id'][:8]}..."
                            )
                        else:
                            st.error(f"Erro: {r.text}")
                    except requests.exceptions.ConnectionError:
                        st.error(
                            "API nao acessivel. Certifique-se de que o servidor esta rodando."
                        )

    st.divider()

    # --- SECAO: Buscar matches ---
    st.subheader("Buscar Matches")
    query = st.text_area(
        "Descreva o contexto de licenciamento",
        height=80,
        placeholder="Ex: musica jazz suave para cena romantica em serie brasileira",
    )
    col3, col4 = st.columns([1, 3])
    with col3:
        top_k = st.slider("Numero de resultados", 1, 10, 5)
    with col4:
        genre_filter = st.multiselect(
            "Filtrar por genero (opcional)",
            ["jazz", "mpb", "rock", "electronic", "ambient"],
        )

    if st.button("Buscar Matches", type="primary"):
        if not query.strip():
            st.warning("Digite uma descricao para buscar.")
        else:
            with st.spinner("Buscando e gerando justificativas (aguarde 15-30s)..."):
                try:
                    payload = {"query": query, "top_k": top_k}
                    if genre_filter:
                        payload["filters"] = {"genre": genre_filter[0]}
                    r = requests.post(f"{api_base}/match", json=payload, timeout=120)
                    if r.status_code == 200:
                        results = r.json()["results"]
                        if not results:
                            st.info(
                                "Nenhuma faixa encontrada. Indexe algumas faixas primeiro."
                            )
                        else:
                            st.success(f"{len(results)} faixa(s) encontrada(s)")
                            for res in results:
                                sd = score_display(res["similarity_score"])
                                with st.expander(
                                    f"{res['title']} - {res['artist']} | Score: {sd['label']}"
                                ):
                                    c1, c2, c3, c4 = st.columns(4)
                                    c1.metric("Score", sd["label"])
                                    c2.metric("Genero", res.get("genre", ""))
                                    c3.metric("BPM", res.get("bpm", ""))
                                    c4.metric("Mood", res.get("mood", ""))
                                    st.progress(res["similarity_score"])
                                    st.markdown(
                                        f"**Justificativa:** {res['justification']}"
                                    )
                    else:
                        st.error(f"Erro: {r.text}")
                except requests.exceptions.ConnectionError:
                    st.error("API nao acessivel.")
