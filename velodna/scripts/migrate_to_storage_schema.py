"""
Migração do schema legado (`src/ingestion/catalog_store.py`) para o schema
canônico (`src/storage/catalog_store.py`).

O banco legado guarda streams com timestamp absoluto e nomes de campo do
protocolo Garmin; o canônico usa tempo relativo ao início da atividade, UUID
tipado e tabelas de atleta/zonas/segmentos.

Estratégia: cria um banco novo com o DDL canônico, faz ATTACH do legado em
modo somente-leitura e copia os dados com INSERT ... SELECT. O arquivo legado
nunca é modificado — a troca é feita por rename, no final, pelo operador.

Uso:
    python scripts/migrate_to_storage_schema.py [--legacy PATH] [--target PATH]
"""
from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from storage.catalog_store import CatalogStore  # noqa: E402

DEFAULT_LEGACY = Path("data/velodna.duckdb")
DEFAULT_TARGET = Path("data/velodna_v2.duckdb")

# Velocidade mínima para considerar o atleta em movimento (m/s).
# 0,5 m/s = 1,8 km/h — abaixo disso é semáforo, foto ou café.
MOVING_SPEED_THRESHOLD_MS = 0.5


def build_athlete(conn: duckdb.DuckDBPyConnection, name: str) -> str:
    """Cria o registro do atleta dono de todo o histórico migrado.

    Args:
        conn: conexão com o banco de destino.
        name: nome do atleta.

    Returns:
        UUID do atleta criado.
    """
    athlete_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO athletes (id, name) VALUES (?, ?)",
        [athlete_id, name],
    )
    return athlete_id


def migrate_activities(conn: duckdb.DuckDBPyConnection, athlete_id: str) -> int:
    """Copia as atividades do banco legado, derivando métricas de movimento.

    `moving_time_s`, `avg_cadence_rpm` e `avg_speed_ms` não existem no schema
    legado e são calculados a partir dos streams. As métricas de carga (TSS,
    NP, IF, VI) são deixadas nulas de propósito: os valores legados foram
    calculados com FTP fixo de 200 W e serão recomputados pela analytics.

    Args:
        conn: conexão com o banco de destino, com o legado já anexado.
        athlete_id: UUID do atleta dono das atividades.

    Returns:
        Número de atividades migradas.
    """
    conn.execute(
        """
        INSERT INTO activities (
            id, athlete_id, garmin_id, strava_id, source, sport_type, started_at,
            elapsed_time_s, moving_time_s, distance_m, elevation_gain_m,
            avg_power_w, max_power_w, normalized_power_w, avg_hr_bpm, max_hr_bpm,
            avg_cadence_rpm, avg_speed_ms, tss, intensity_factor,
            variability_index, raw_file_path
        )
        SELECT
            CAST(a.activity_id AS UUID),
            CAST(? AS UUID),
            a.garmin_id,
            a.strava_id,
            'fit',
            a.sport_type,
            a.start_time,
            a.duration_s,
            m.moving_time_s,
            a.distance_m,
            a.elevation_m,
            a.avg_power_w,
            a.max_power_w,
            NULL,               -- normalized_power_w: recomputado pela analytics
            a.avg_hr_bpm,
            a.max_hr_bpm,
            m.avg_cadence_rpm,
            m.avg_speed_ms,
            NULL,               -- tss: legado usava FTP fixo de 200 W
            NULL,               -- intensity_factor
            NULL,               -- variability_index
            a.fit_file_path
        FROM legacy.activities a
        LEFT JOIN (
            SELECT
                activity_id,
                COUNT(*) FILTER (WHERE speed_ms > ?)            AS moving_time_s,
                AVG(cadence_rpm) FILTER (WHERE cadence_rpm > 0) AS avg_cadence_rpm,
                AVG(speed_ms) FILTER (WHERE speed_ms > ?)       AS avg_speed_ms
            FROM legacy.activity_streams
            GROUP BY activity_id
        ) m ON m.activity_id = a.activity_id
        """,
        [athlete_id, MOVING_SPEED_THRESHOLD_MS, MOVING_SPEED_THRESHOLD_MS],
    )
    return conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0]


def migrate_streams(conn: duckdb.DuckDBPyConnection) -> int:
    """Copia os streams convertendo timestamp absoluto em tempo relativo.

    Pontos anteriores ao `start_time` da atividade (artefato de gravação em
    alguns arquivos) são fixados em t=0 em vez de gerarem tempo negativo.

    Args:
        conn: conexão com o banco de destino, com o legado já anexado.

    Returns:
        Número de pontos migrados.
    """
    conn.execute(
        """
        INSERT INTO activity_streams (
            activity_id, time_s, lat, lon, altitude_m, distance_m,
            power_w, hr_bpm, cadence_rpm, speed_ms, temperature_c,
            left_right_balance
        )
        SELECT
            CAST(s.activity_id AS UUID),
            GREATEST(DATE_DIFF('second', a.start_time, s.timestamp), 0),
            s.lat, s.lon, s.altitude_m, s.distance_m,
            s.power_w, s.heart_rate_bpm, s.cadence_rpm, s.speed_ms,
            s.temperature_c,
            NULL                -- left_right_balance: não capturado pelo parser
        FROM legacy.activity_streams s
        JOIN legacy.activities a ON a.activity_id = s.activity_id
        """
    )
    return conn.execute("SELECT COUNT(*) FROM activity_streams").fetchone()[0]


def migrate_training_load(conn: duckdb.DuckDBPyConnection, athlete_id: str) -> int:
    """Copia a série histórica de CTL/ATL/TSB do legado.

    Os valores são preservados apenas como referência para comparação: serão
    recalculados, já que a série legada omite dias de descanso e sobrescreve
    atividades do mesmo dia.

    Args:
        conn: conexão com o banco de destino, com o legado já anexado.
        athlete_id: UUID do atleta.

    Returns:
        Número de registros migrados.
    """
    conn.execute(
        """
        INSERT INTO training_load (id, athlete_id, date, ctl, atl, tsb, daily_tss)
        SELECT uuid(), CAST(? AS UUID), m.date, m.ctl, m.atl, m.tsb, NULL
        FROM legacy.athlete_metrics m
        """,
        [athlete_id],
    )
    return conn.execute("SELECT COUNT(*) FROM training_load").fetchone()[0]


def verify(conn: duckdb.DuckDBPyConnection) -> list[str]:
    """Compara destino e legado, devolvendo as divergências encontradas.

    Args:
        conn: conexão com o banco de destino, com o legado já anexado.

    Returns:
        Lista de mensagens de erro; vazia se a migração está consistente.
    """
    problems: list[str] = []

    checks = [
        ("atividades", "SELECT COUNT(*) FROM activities",
         "SELECT COUNT(*) FROM legacy.activities"),
        ("streams", "SELECT COUNT(*) FROM activity_streams",
         "SELECT COUNT(*) FROM legacy.activity_streams"),
        ("training_load", "SELECT COUNT(*) FROM training_load",
         "SELECT COUNT(*) FROM legacy.athlete_metrics"),
    ]
    for label, target_sql, legacy_sql in checks:
        got = conn.execute(target_sql).fetchone()[0]
        want = conn.execute(legacy_sql).fetchone()[0]
        if got != want:
            problems.append(f"{label}: destino {got:,} != legado {want:,}")

    negative = conn.execute(
        "SELECT COUNT(*) FROM activity_streams WHERE time_s < 0"
    ).fetchone()[0]
    if negative:
        problems.append(f"{negative:,} streams com time_s negativo")

    orphans = conn.execute(
        """
        SELECT COUNT(*) FROM activity_streams s
        LEFT JOIN activities a ON a.id = s.activity_id
        WHERE a.id IS NULL
        """
    ).fetchone()[0]
    if orphans:
        problems.append(f"{orphans:,} streams órfãos")

    distance = conn.execute(
        """
        SELECT ABS(
            (SELECT COALESCE(SUM(distance_m), 0) FROM activities)
          - (SELECT COALESCE(SUM(distance_m), 0) FROM legacy.activities)
        )
        """
    ).fetchone()[0]
    if distance > 1000:
        problems.append(f"distância total diverge em {distance:,.0f} m")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy", type=Path, default=DEFAULT_LEGACY)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--athlete-name", default="David Saggioro")
    args = parser.parse_args()

    if not args.legacy.exists():
        print(f"ERRO: banco legado não encontrado em {args.legacy}")
        return 1
    if args.target.exists():
        print(f"ERRO: {args.target} já existe — remova antes de migrar")
        return 1

    print(f"Legado : {args.legacy}")
    print(f"Destino: {args.target}\n")

    store = CatalogStore.open(str(args.target))
    conn = store._conn
    conn.execute(f"ATTACH '{args.legacy}' AS legacy (READ_ONLY)")

    athlete_id = build_athlete(conn, args.athlete_name)
    print(f"Atleta criado: {athlete_id}")

    n = migrate_activities(conn, athlete_id)
    print(f"Atividades migradas: {n:,}")

    n = migrate_streams(conn)
    print(f"Streams migrados:    {n:,}")

    n = migrate_training_load(conn, athlete_id)
    print(f"Training load:       {n:,}")

    print("\nVerificando integridade...")
    problems = verify(conn)
    conn.execute("DETACH legacy")
    conn.close()

    if problems:
        print("\nFALHAS:")
        for p in problems:
            print(f"  - {p}")
        return 1

    print("OK — contagens, distância e integridade referencial conferem.")
    print(f"\nAtleta: {athlete_id}")
    print("Grave esse UUID no .env como VELODNA_ATHLETE_ID.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
