import os
import requests
import streamlit as st
import plotly.express as px

from src.db.connection import get_optimized_connection
from src.trend_engine.genre_heatmap import GenreHeatmap

DB_PATH = os.environ.get("TREND_RADAR_DB", "/workspace/data/trend_radar.duckdb")
API_BASE = os.environ.get("TREND_RADAR_API", "http://localhost:8000")

st.set_page_config(
    page_title="Trend Radar Musical BR",
    page_icon="📡",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Dados compartilhados
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def build_ranking_df(db_path: str):
    """Carrega gold_rising_artists com todas as colunas necessárias."""
    conn = get_optimized_connection(db_path, read_only=True)
    df = conn.execute(
        """
        SELECT artist_mbid,
               name            AS artist_name,
               genres,
               country,
               trend_score,
               trending_direction,
               weeks_above_threshold,
               week_start
        FROM gold_rising_artists
        ORDER BY trend_score DESC
        """
    ).df()
    conn.close()
    return df


@st.cache_data(ttl=60)
def get_last_update(db_path: str) -> str:
    """Retorna string com a semana mais recente em gold_rising_artists."""
    conn = get_optimized_connection(db_path, read_only=True)
    row = conn.execute(
        "SELECT MAX(week_start) AS last_week FROM gold_rising_artists"
    ).fetchone()
    conn.close()
    last_week = row[0] if row and row[0] else "sem dados"
    return f"Última atualização: semana de {last_week}"


# ---------------------------------------------------------------------------
# Helpers de UI
# ---------------------------------------------------------------------------

def color_trend_score(val):
    """Barra colorida por faixas de score."""
    try:
        v = float(val)
    except (TypeError, ValueError):
        return ""
    if v >= 65:
        color = "#16a34a"   # verde
    elif v >= 40:
        color = "#d97706"   # âmbar
    else:
        color = "#dc2626"   # vermelho
    width = int(v)
    return f"background: linear-gradient(to right, {color} {width}%, #f3f4f6 {width}%)"


def _genres_list(df):
    """Extrai lista plana de gêneros do DataFrame (suporta array e scalar)."""
    genres = []
    for val in df["genres"].dropna():
        if isinstance(val, list):
            genres.extend(val)
        else:
            genres.append(str(val))
    return genres


# ---------------------------------------------------------------------------
# Página 1: Ranking Semanal
# ---------------------------------------------------------------------------

def page_ranking():
    st.title("📡 Trend Radar Musical BR")
    st.subheader("Artistas em Ascensão — Semana Atual")

    df = build_ranking_df(DB_PATH)

    if df.empty:
        st.warning("Nenhum dado disponível. Execute a pipeline de ingestão primeiro.")
        return

    # --- Melhoria 3: KPIs ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Artistas em Ascensão", len(df))
    col2.metric("Score Médio", f"{df['trend_score'].mean():.1f}")

    all_genres = _genres_list(df)
    import pandas as pd
    top_genre = pd.Series(all_genres).mode()[0] if all_genres else "—"
    col3.metric("Top Gênero", top_genre)

    top_country = df["country"].mode()[0] if not df["country"].isna().all() else "—"
    col4.metric("Top País", top_country)

    st.divider()

    # --- Filtros ---
    unique_genres = sorted(set(all_genres))
    genres_sel = st.multiselect("Gênero", options=unique_genres)
    countries_sel = st.multiselect(
        "País", options=sorted(df["country"].dropna().unique())
    )

    df_filtered = df.copy()
    if genres_sel:
        def has_genre(val):
            if isinstance(val, list):
                return any(g in val for g in genres_sel)
            return val in genres_sel
        df_filtered = df_filtered[df_filtered["genres"].apply(has_genre)]
    if countries_sel:
        df_filtered = df_filtered[df_filtered["country"].isin(countries_sel)]

    # --- Melhoria 2: barra colorida de trend_score ---
    display_cols = ["artist_name", "trend_score", "trending_direction",
                    "country", "weeks_above_threshold", "week_start"]
    styled = df_filtered[display_cols].style.map(
        color_trend_score, subset=["trend_score"]
    )
    st.dataframe(styled, use_container_width=True)

    st.download_button(
        "⬇ Download CSV",
        df_filtered.to_csv(index=False),
        "trending_artists.csv",
        "text/csv",
    )

    # --- Melhoria 4: histórico do artista via API ---
    st.divider()
    st.subheader("Histórico de Trend Score")
    name_to_mbid = dict(zip(df["artist_name"], df["artist_mbid"]))
    selected_name = st.selectbox("Ver histórico de:", [""] + list(df["artist_name"]))

    if selected_name:
        mbid = name_to_mbid.get(selected_name)
        try:
            resp = requests.get(
                f"{API_BASE}/api/v1/artists/{mbid}/history?weeks=12",
                timeout=5,
            )
            resp.raise_for_status()
            history = resp.json().get("history", [])
            if history:
                fig = px.line(
                    history,
                    x="week_start",
                    y="trend_score",
                    markers=True,
                    title=f"Trend Score — {selected_name} (últimas 12 semanas)",
                )
                fig.add_hline(
                    y=65,
                    line_dash="dash",
                    line_color="green",
                    annotation_text="Threshold de ascensão",
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Histórico insuficiente para este artista.")
        except Exception as exc:
            st.warning(
                f"API indisponível ({exc}). "
                "Inicie o servidor com: `uvicorn src.api.main:app --reload`"
            )


# ---------------------------------------------------------------------------
# Página 2: Heatmap de Gêneros
# ---------------------------------------------------------------------------

def page_heatmap():
    st.title("🎼 Heatmap de Gêneros")

    conn = get_optimized_connection(DB_PATH, read_only=True)
    heatmap = GenreHeatmap(conn)
    df_pivot = heatmap.to_dataframe(weeks=12)
    conn.close()

    if df_pivot.empty:
        st.warning("Nenhum dado disponível para o heatmap.")
        return

    fig = px.imshow(
        df_pivot,
        color_continuous_scale="RdYlGn",
        labels={"color": "Trend Score"},
        title="Score Médio por Gênero — Últimas 12 Semanas",
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Página 3: Relatório Semanal
# ---------------------------------------------------------------------------

def page_report():
    st.title("📝 Relatório Semanal")

    try:
        conn = get_optimized_connection(DB_PATH, read_only=True)
        reports = conn.execute(
            """
            SELECT week_start, report_text
            FROM weekly_reports
            ORDER BY week_start DESC
            LIMIT 4
            """
        ).fetchall()
        conn.close()
    except Exception:
        st.info(
            "Nenhum relatório disponível ainda. "
            "Execute `ReportGenerator.generate_and_save()` para gerar o primeiro relatório."
        )
        return

    if not reports:
        st.info("Nenhum relatório gerado ainda.")
        return

    for week, text in reports:
        with st.expander(f"Semana de {week}"):
            st.markdown(text or "_Relatório vazio._")


# ---------------------------------------------------------------------------
# Sidebar + navegação
# ---------------------------------------------------------------------------

# Melhoria 1: indicador de última atualização
st.sidebar.info(get_last_update(DB_PATH))

pages = {
    "Ranking Semanal":   page_ranking,
    "Heatmap de Gêneros": page_heatmap,
    "Relatório Semanal": page_report,
}
selection = st.sidebar.radio("Navegação", list(pages.keys()))
pages[selection]()
