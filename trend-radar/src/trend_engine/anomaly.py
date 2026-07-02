# src/trend_engine/anomaly.py — Detecção de anomalias via Z-score

import logging
from datetime import datetime, timezone

import duckdb

logger = logging.getLogger(__name__)

_SOURCE_COL = {
    "lastfm":  "lastfm_plays",
    "youtube": "youtube_views",
    "deezer":  "deezer_fans",
}

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS gold_anomalies (
    artist_mbid     VARCHAR     NOT NULL,
    artist_name     VARCHAR     NOT NULL,
    week_start      DATE        NOT NULL,
    anomaly_score   DOUBLE      NOT NULL,
    trigger_source  VARCHAR     NOT NULL,
    detected_at     TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (artist_mbid, week_start)
);
"""


class AnomalyDetector:
    def __init__(self, conn: duckdb.DuckDBPyConnection, threshold: float = 2.5) -> None:
        self.conn = conn
        self.threshold = threshold

    def _ensure_table(self) -> None:
        self.conn.execute(_CREATE_TABLE_SQL)

    def _calculate_zscore(self, artist_mbid: str, source: str, week_start: str) -> float:
        """Z-score do valor atual vs média das 7 semanas anteriores.

        Busca as 8 semanas mais recentes (≤ week_start), usa a mais recente como
        valor atual e as 7 restantes como histórico.
        Retorna 0.0 se dados insuficientes.
        Quando std == 0 e valor atual != média usa max(std, 1.0) como divisor,
        preservando o sinal da anomalia.
        """
        col = _SOURCE_COL[source]
        rows = self.conn.execute(
            f"SELECT {col} FROM silver_weekly_plays "
            "WHERE artist_mbid = ? AND week_start <= ? "
            "ORDER BY week_start DESC LIMIT 8",
            [artist_mbid, week_start],
        ).fetchall()

        if len(rows) < 2:
            return 0.0

        current = float(rows[0][0] or 0)
        historical = [float(r[0] or 0) for r in rows[1:]]

        n = len(historical)
        mean = sum(historical) / n
        # população std (divisor n)
        variance = sum((x - mean) ** 2 for x in historical) / n
        std = variance ** 0.5

        return (current - mean) / max(std, 1.0)

    def run(self, week_start: str) -> int:
        """Detecta anomalias para todos os artistas da semana informada.

        Para cada artista calcula o Z-score nas três fontes. Se algum ultrapassar
        o threshold, insere (ou ignora se já existir) em gold_anomalies.

        Returns:
            Número de registros inseridos (0 em re-execuções idempotentes).
        """
        self._ensure_table()

        # Tenta query direta (schema de testes inclui artist_name em silver_weekly_plays).
        # Em produção (dbt real) o nome vem de silver_artists via JOIN.
        try:
            artists = self.conn.execute(
                "SELECT artist_mbid, artist_name FROM silver_weekly_plays WHERE week_start = ?",
                [week_start],
            ).fetchall()
        except Exception:
            artists = self.conn.execute(
                """
                SELECT swp.artist_mbid, COALESCE(sa.name, swp.artist_mbid)
                FROM silver_weekly_plays swp
                LEFT JOIN silver_artists sa ON sa.mbid = swp.artist_mbid
                WHERE swp.week_start = ?
                """,
                [week_start],
            ).fetchall()

        inserted = 0
        detected_at = datetime.now(tz=timezone.utc).isoformat()

        for artist_mbid, artist_name in artists:
            z_scores: dict[str, float] = {}
            for source in _SOURCE_COL:
                z_scores[source] = self._calculate_zscore(artist_mbid, source, week_start)

            above = {s: z for s, z in z_scores.items() if z > self.threshold}
            if not above:
                continue

            trigger_source = "multi" if len(above) >= 2 else next(iter(
                sorted(above, key=above.__getitem__, reverse=True)
            ))
            anomaly_score = max(z_scores.values())

            # Verifica se já existe antes de tentar inserir
            exists = self.conn.execute(
                "SELECT 1 FROM gold_anomalies WHERE artist_mbid = ? AND week_start = ?",
                [artist_mbid, week_start],
            ).fetchone()

            if exists:
                continue

            self.conn.execute(
                "INSERT INTO gold_anomalies "
                "(artist_mbid, artist_name, week_start, anomaly_score, trigger_source, detected_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [artist_mbid, artist_name, week_start, anomaly_score, trigger_source, detected_at],
            )
            inserted += 1
            logger.info(
                "[AnomalyDetector] Anomalia: %s (%s) semana %s | score=%.2f | fonte=%s",
                artist_name, artist_mbid, week_start, anomaly_score, trigger_source,
            )

        logger.info(
            "[AnomalyDetector] %d anomalias inseridas para semana %s.", inserted, week_start
        )
        return inserted
