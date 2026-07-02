# src/report/generator.py — ReportGenerator com Ollama

import logging
from pathlib import Path
from typing import Any

import httpx
import duckdb

logger = logging.getLogger(__name__)

_TEMPLATE_PATH = Path(__file__).parent / "prompt_template.txt"


class OllamaUnavailableError(Exception):
    pass


class ReportGenerator:
    OLLAMA_URL = "http://localhost:11434/api/generate"
    MODEL = "llama3:8b"
    TIMEOUT = 180

    def __init__(self, conn: duckdb.DuckDBPyConnection, ollama_url: str | None = None) -> None:
        self.conn = conn
        self.ollama_url = ollama_url or self.OLLAMA_URL

    # ------------------------------------------------------------------
    # Context builder
    # ------------------------------------------------------------------

    def _build_context(self, week_start: str) -> dict[str, Any]:
        # Top 5 artistas por trend_score
        top_rows = self.conn.execute(
            """
            SELECT artist_name, trend_score, genre
            FROM gold_rising_artists
            WHERE week_start = ?
            ORDER BY trend_score DESC
            LIMIT 5
            """,
            [week_start],
        ).fetchall()
        top_artists = ", ".join(
            f"{r[0]} ({r[2]}, score={r[1]:.1f})" for r in top_rows
        ) or "N/A"

        # Gênero com maior score médio — tenta gold_genre_heatmap, fallback rising
        top_genre = "N/A"
        try:
            row = self.conn.execute(
                """
                SELECT genre, AVG(avg_trend_score) AS s
                FROM gold_genre_heatmap
                WHERE week_start = ?
                GROUP BY genre
                ORDER BY s DESC
                LIMIT 1
                """,
                [week_start],
            ).fetchone()
            if row:
                top_genre = row[0]
        except Exception:
            # fallback: modo mais frequente em gold_rising_artists
            row = self.conn.execute(
                """
                SELECT genre, AVG(trend_score) AS s
                FROM gold_rising_artists
                WHERE week_start = ?
                GROUP BY genre
                ORDER BY s DESC
                LIMIT 1
                """,
                [week_start],
            ).fetchone()
            if row:
                top_genre = row[0]

        # Anomalia de destaque
        anomaly = "Nenhuma anomalia registrada"
        try:
            row = self.conn.execute(
                """
                SELECT artist_name, anomaly_score, trigger_source
                FROM gold_anomalies
                WHERE week_start = ?
                ORDER BY anomaly_score DESC
                LIMIT 1
                """,
                [week_start],
            ).fetchone()
            if row:
                anomaly = f"{row[0]} (score={row[1]:.2f}, fonte={row[2]})"
        except Exception:
            pass

        # Artista que saiu do radar (estava na semana anterior, não está agora)
        dropped_artist = "Nenhum"
        try:
            from datetime import date, timedelta
            prev_week = (date.fromisoformat(week_start) - timedelta(weeks=1)).isoformat()
            prev_mbids = {
                r[0]
                for r in self.conn.execute(
                    "SELECT artist_mbid FROM gold_rising_artists WHERE week_start = ?",
                    [prev_week],
                ).fetchall()
            }
            curr_mbids = {
                r[0]
                for r in self.conn.execute(
                    "SELECT artist_mbid FROM gold_rising_artists WHERE week_start = ?",
                    [week_start],
                ).fetchall()
            }
            dropped = prev_mbids - curr_mbids
            if dropped:
                mbid = next(iter(dropped))
                name_row = self.conn.execute(
                    "SELECT artist_name FROM gold_rising_artists WHERE artist_mbid = ? LIMIT 1",
                    [mbid],
                ).fetchone()
                dropped_artist = name_row[0] if name_row else mbid
        except Exception:
            pass

        return {
            "week_start":     week_start,
            "top_artists":    top_artists,
            "top_genre":      top_genre,
            "anomaly":        anomaly,
            "dropped_artist": dropped_artist,
        }

    # ------------------------------------------------------------------
    # LLM call
    # ------------------------------------------------------------------

    def generate(self, week_start: str) -> str:
        context = self._build_context(week_start)
        template = _TEMPLATE_PATH.read_text(encoding="utf-8")
        prompt = template.format(**context)

        try:
            response = httpx.post(
                self.ollama_url,
                json={"model": self.MODEL, "prompt": prompt, "stream": False},
                timeout=self.TIMEOUT,
            )
            llm_text = response.json()["response"]
        except httpx.ConnectError as exc:
            raise OllamaUnavailableError(
                f"Ollama não está disponível em {self.ollama_url}. "
                "Verifique se o servidor LLM está rodando."
            ) from exc

        # Monta relatório estruturado com seções obrigatórias
        report = (
            f"## Resumo Executivo\n"
            f"{llm_text}\n\n"
            f"## Top 5 Artistas\n"
            f"{context['top_artists']}\n\n"
            f"## Gênero da Semana\n"
            f"{context['top_genre']}\n\n"
            f"## Destaque de Anomalia\n"
            f"{context['anomaly']}\n"
        )
        logger.info("[ReportGenerator] Relatório gerado para semana %s.", week_start)
        return report

    # ------------------------------------------------------------------
    # Save (Markdown)
    # ------------------------------------------------------------------

    def generate_and_save(
        self,
        week_start: str,
        data_dir: str = "/workspace/data/reports",
    ) -> str:
        report = self.generate(week_start)

        out = Path(data_dir) / f"{week_start}_report.md"
        out.write_text(report, encoding="utf-8")
        logger.info("[ReportGenerator] Relatório salvo em %s.", out)

        try:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS weekly_reports (
                    week_start   VARCHAR PRIMARY KEY,
                    report_text  VARCHAR,
                    generated_at VARCHAR
                )
                """
            )
            self.conn.execute(
                "INSERT OR REPLACE INTO weekly_reports VALUES (?, ?, current_timestamp::VARCHAR)",
                [week_start, report],
            )
        except Exception as exc:
            logger.warning("[ReportGenerator] Não foi possível salvar no DuckDB: %s", exc)

        return report

    # ------------------------------------------------------------------
    # Save (HTML)
    # ------------------------------------------------------------------

    def generate_html_report(
        self,
        week_start: str,
        data_dir: str = "/workspace/data/reports",
    ) -> str:
        """Gera o relatório em HTML a partir do Markdown e salva em disco.

        Requer `pip install markdown`.
        Retorna o caminho do arquivo .html gerado.
        """
        import markdown as md_lib

        md_report = self.generate(week_start)
        html_body = md_lib.markdown(
            md_report,
            extensions=["tables", "fenced_code"],
        )

        html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Trend Radar — Semana de {week_start}</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      max-width: 800px;
      margin: 40px auto;
      padding: 0 20px;
      color: #1f2937;
    }}
    h1 {{ color: #0D5C3A; border-bottom: 3px solid #1A8C59; padding-bottom: 8px; }}
    h2 {{ color: #0B7B6B; margin-top: 32px; }}
    p  {{ line-height: 1.7; }}
    .badge {{
      background: #D6F0E3;
      color: #0D5C3A;
      padding: 4px 12px;
      border-radius: 20px;
      font-size: 0.85em;
      display: inline-block;
      margin-bottom: 24px;
    }}
    footer {{ margin-top: 40px; color: #9CA3AF; font-size: 0.8em; }}
  </style>
</head>
<body>
  <div class="badge">Semana de {week_start}</div>
  {html_body}
  <footer>
    Trend Radar Musical BR — Gerado por IA local (Llama 3 8B)
  </footer>
</body>
</html>"""

        html_path = Path(data_dir) / f"{week_start}_report.html"
        html_path.write_text(html, encoding="utf-8")
        logger.info("[ReportGenerator] HTML salvo em %s.", html_path)
        return str(html_path)
