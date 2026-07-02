"""UI helper functions for MusicDNA AI — Module M12.

Utilities for formatting API responses for Streamlit display.
"""

from __future__ import annotations


def format_match_results(results: list[dict]) -> list[dict]:
    """Formata resultados do /match para exibicao em st.dataframe.

    Args:
        results: Lista de dicts retornados pelo endpoint POST /match,
            contendo ``similarity_score``, ``title``, ``artist``, etc.

    Returns:
        Lista de dicts com chaves em portugues prontas para ``st.dataframe``.
    """
    formatted = []
    for r in results:
        formatted.append(
            {
                "Faixa": r.get("title", ""),
                "Artista": r.get("artist", ""),
                "Score (%)": round(r["similarity_score"] * 100, 1),
                "Genero": r.get("genre", ""),
                "BPM": r.get("bpm", 0),
                "Mood": r.get("mood", ""),
                "Justificativa": r.get("justification", ""),
                "job_id": r.get("job_id", ""),
            }
        )
    return formatted


def format_progression(progression: list[dict]) -> list[dict]:
    """Formata progressao harmonica para exibicao em st.table.

    Args:
        progression: Lista de dicts com ``chord_name`` e ``midi_notes``.

    Returns:
        Lista de dicts com ``'Compasso'`` (1-indexed), ``'Acorde'`` e
        ``'Notas MIDI'`` (string).
    """
    return [
        {
            "Compasso": i + 1,
            "Acorde": chord["chord_name"],
            "Notas MIDI": str(chord["midi_notes"]),
        }
        for i, chord in enumerate(progression)
    ]


def build_ingest_payload(form_data: dict) -> dict:
    """Converte dados do formulario Streamlit para payload do /ingest.

    Args:
        form_data: Dict do formulario com chaves ``title``, ``artist``,
            ``genre``, ``bpm`` e ``mood``.

    Returns:
        Dict com ``bpm_manual`` (float) pronto para o endpoint POST /ingest.
    """
    return {
        "title": form_data.get("title", ""),
        "artist": form_data.get("artist", ""),
        "genre": form_data.get("genre", ""),
        "bpm": float(form_data.get("bpm", 0)),
        "mood": form_data.get("mood", ""),
    }


def parse_health(response: dict) -> dict:
    """Parseia resposta do /health para exibicao na UI.

    Args:
        response: Dict retornado pelo endpoint GET /health com chaves
            ``status`` e ``ollama``.

    Returns:
        Dict com flags booleanas ``api_ok`` / ``ollama_ok`` e labels
        em portugues ``api_label`` / ``ollama_label``.
    """
    api_ok = response.get("status") == "ok"
    ollama_ok = response.get("ollama") == "reachable"
    return {
        "api_ok": api_ok,
        "ollama_ok": ollama_ok,
        "api_label": "Online" if api_ok else "Offline",
        "ollama_label": "Conectado" if ollama_ok else "Desconectado",
    }


def score_display(score: float) -> dict:
    """Converte similarity_score em percentual e cor para a UI.

    Args:
        score: Similaridade em [0, 1].

    Returns:
        Dict com ``percentage`` (float), ``label`` (e.g. ``'87%'``) e
        ``color`` (``'green'`` >= 0.7, ``'orange'`` >= 0.4, ``'red'`` < 0.4).
    """
    pct = round(score * 100, 1)
    if score >= 0.7:
        color = "green"
    elif score >= 0.4:
        color = "orange"
    else:
        color = "red"
    return {"percentage": pct, "label": f"{int(pct)}%", "color": color}
