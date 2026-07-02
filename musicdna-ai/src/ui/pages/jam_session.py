"""Jam Session Simulator page for MusicDNA AI Streamlit app."""

import os

import requests
import streamlit as st

from src.ui.helpers import format_progression


def render(api_base: str) -> None:
    """Renders the Jam Session Simulator page.

    Args:
        api_base: Base URL of the MusicDNA AI API.
    """
    st.title("Jam Session Simulator")
    st.markdown("Configure uma sessao e deixe a IA improvisar com voce.")

    col1, col2 = st.columns(2)
    with col1:
        style = st.selectbox("Estilo", ["jazz", "mpb"])
        key = st.selectbox(
            "Tonalidade", ["C", "D", "E", "F", "G", "A", "B", "C#", "Bb", "Eb"]
        )
        bpm = st.slider("BPM", min_value=40, max_value=240, value=120, step=5)
    with col2:
        mood = st.selectbox(
            "Mood", ["relaxado", "animado", "melancolico", "energetico"]
        )
        bars = st.slider(
            "Duracao (compassos)", min_value=2, max_value=32, value=8, step=2
        )
        st.markdown("")
        gerar = st.button("Gerar Jam Session", type="primary", use_container_width=True)

    if gerar:
        with st.spinner("Gerando progressao e consultando Ollama (aguarde)..."):
            try:
                payload = {
                    "style": style,
                    "key": key,
                    "bpm": bpm,
                    "mood": mood,
                    "bars": bars,
                }
                r = requests.post(f"{api_base}/jam/session", json=payload, timeout=120)
                if r.status_code == 200:
                    data = r.json()
                    st.session_state["last_jam"] = data
                    st.success("Sessao gerada!")
                else:
                    st.error(f"Erro: {r.text}")
                    return
            except requests.exceptions.ConnectionError:
                st.error("API nao acessivel.")
                return

    # Exibir resultado da ultima sessao:
    if "last_jam" in st.session_state:
        data = st.session_state["last_jam"]
        st.divider()
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Estilo", data.get("style", "").upper())
        col_b.metric("Tonalidade", data.get("key", ""))
        col_c.metric("BPM", data.get("bpm", ""))

        st.subheader("Progressao Harmonica")
        # Reconstruir progression para o helper:
        chords = data.get("chord_sequence", [])
        progression_display = [{"chord_name": c, "midi_notes": []} for c in chords]
        prog_table = format_progression(progression_display)
        # Simplificar para exibicao:
        simple_table = [
            {"Compasso": p["Compasso"], "Acorde": p["Acorde"]} for p in prog_table
        ]
        st.table(simple_table)

        st.subheader("Sugestao de Improvisacao")
        st.info(data.get("suggestion", ""))

        st.subheader("Arquivo MIDI")
        midi_path = data.get("midi_path", "")
        if midi_path and os.path.exists(midi_path):
            with open(midi_path, "rb") as f:
                st.download_button(
                    label="Baixar MIDI",
                    data=f.read(),
                    file_name=f"{data['session_id'][:8]}.mid",
                    mime="audio/midi",
                )
        st.info(
            "Para ouvir: abra o MIDI no GarageBand ou use: "
            "fluidsynth -F out.wav soundfont.sf2 arquivo.mid"
        )
