# src/report/alerts.py — AlertEngine do Trend Radar

import json
import logging
from pathlib import Path
from typing import Any

import duckdb

logger = logging.getLogger(__name__)


class AlertEngine:
    def __init__(
        self,
        conn: duckdb.DuckDBPyConnection,
        threshold: float = 65.0,
        output_path: Path | str | None = None,
    ) -> None:
        self.conn = conn
        self.threshold = threshold
        self.output_path = Path(output_path) if output_path else None

    def run(self, week_start: str) -> list[dict[str, Any]]:
        """Gera alertas para artistas que cruzaram o threshold nesta semana.

        Lógica:
        - threshold_crossed: score atual >= threshold E score semana anterior < threshold
          (artista que acabou de entrar na zona quente)
        - Artistas acima do threshold há 2+ semanas consecutivas NÃO geram alerta.
        """
        from datetime import date, timedelta

        prev_week = (
            date.fromisoformat(week_start) - timedelta(weeks=1)
        ).isoformat()

        # Artistas com score >= threshold na semana atual
        current_rows = self.conn.execute(
            """
            SELECT artist_mbid, artist_name, trend_score
            FROM gold_trend_scores
            WHERE week_start = ?
              AND trend_score >= ?
            """,
            [week_start, self.threshold],
        ).fetchall()

        alerts: list[dict[str, Any]] = []
        for mbid, name, current_score in current_rows:
            # Verifica score na semana anterior
            prev_row = self.conn.execute(
                """
                SELECT trend_score
                FROM gold_trend_scores
                WHERE artist_mbid = ? AND week_start = ?
                """,
                [mbid, prev_week],
            ).fetchone()

            prev_score = float(prev_row[0]) if prev_row and prev_row[0] is not None else None

            # Cruzamento: estava abaixo (ou ausente) e agora está acima
            if prev_score is None or prev_score < self.threshold:
                alerts.append(
                    {
                        "artist_mbid":   mbid,
                        "artist_name":   name,
                        "type":          "threshold_crossed",
                        "week_start":    week_start,
                        "trend_score":   current_score,
                        "prev_score":    prev_score,
                        "threshold":     self.threshold,
                    }
                )
                logger.info(
                    "[AlertEngine] threshold_crossed — %s (score=%.1f)", name, current_score
                )

        if alerts and self.output_path is not None:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            self.output_path.write_text(
                json.dumps(alerts, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            logger.info("[AlertEngine] %d alertas salvos em %s.", len(alerts), self.output_path)

        return alerts
