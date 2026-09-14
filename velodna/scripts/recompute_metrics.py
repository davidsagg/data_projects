"""
Recomputa as métricas derivadas de stream para todo o histórico.

Etapas, na ordem em que dependem umas das outras:

  1. curva de potência por atividade (MMP)
  2. NP, VI, EF e decoupling  — não dependem de FTP
  3. histórico de eFTP        — derivado da curva de potência
  4. IF e TSS                 — dependem do FTP vigente na data
  5. HRSS                     — para as atividades sem potência
  6. CTL/ATL/TSB              — a partir da série diária de TSS

Uso:
    .venv/bin/python scripts/recompute_metrics.py --stage curves,metrics
    .venv/bin/python scripts/recompute_metrics.py            # todas as etapas
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from analytics.hr_metrics import HeartRateProfile, compute_hrss, decoupling_pct  # noqa: E402
from analytics.pmc_calculator import PMCCalculator  # noqa: E402
from analytics.power_curve_engine import PowerCurveEngine  # noqa: E402
from analytics.power_metrics import compute_power_metrics  # noqa: E402
from analytics.timeseries import load_series  # noqa: E402
from storage.catalog_store import CatalogStore  # noqa: E402

DB_PATH = os.getenv("DB_PATH", "data/velodna.duckdb")
ALL_STAGES = ("curves", "metrics", "ftp", "load", "calibrate", "zones", "pmc")


def _activities(conn, athlete_id: str) -> list[tuple]:
    """Lista as atividades do atleta em ordem cronológica.

    Args:
        conn: conexão DuckDB.
        athlete_id: UUID do atleta.

    Returns:
        Tuplas (id, data).
    """
    return conn.execute(
        """
        SELECT id, CAST(started_at AS DATE)
        FROM activities WHERE athlete_id = ?
        ORDER BY started_at
        """,
        [athlete_id],
    ).fetchall()


def stage_curves(store: CatalogStore, athlete_id: str) -> None:
    """Recalcula e persiste a curva de potência de cada atividade."""
    engine = PowerCurveEngine()
    activities = _activities(store.conn, athlete_id)
    done = 0

    for index, (activity_id, activity_date) in enumerate(activities, start=1):
        series = load_series(store.conn, str(activity_id))
        curve = engine.compute(series)
        if curve:
            store.save_power_curve(str(activity_id), activity_date, curve)
            done += 1
        if index % 200 == 0:
            print(f"    {index}/{len(activities)} atividades...")

    print(f"  curvas persistidas: {done} de {len(activities)} atividades")


def stage_metrics(store: CatalogStore, athlete_id: str) -> None:
    """Calcula NP, VI, EF e decoupling — tudo que independe do FTP."""
    activities = _activities(store.conn, athlete_id)
    updated = 0

    for index, (activity_id, _) in enumerate(activities, start=1):
        series = load_series(store.conn, str(activity_id))
        if not series.segments:
            continue

        metrics = compute_power_metrics(series, ftp_w=None)
        store.conn.execute(
            """
            UPDATE activities SET
                normalized_power_w = ?, variability_index = ?,
                efficiency_factor = ?, decoupling_pct = ?,
                avg_power_w = COALESCE(?, avg_power_w),
                max_power_w = COALESCE(?, max_power_w),
                moving_time_s = ?
            WHERE id = ?
            """,
            [
                metrics.normalized_power_w, metrics.variability_index,
                metrics.efficiency_factor, decoupling_pct(series),
                metrics.avg_power_w, metrics.max_power_w,
                series.moving_time_s, activity_id,
            ],
        )
        updated += 1
        if index % 200 == 0:
            print(f"    {index}/{len(activities)} atividades...")

    print(f"  métricas atualizadas em {updated} atividades")


def stage_ftp(store: CatalogStore, athlete_id: str) -> None:
    """Deriva o histórico de eFTP a partir da curva de potência."""
    from analytics.ftp_history import rebuild_ftp_history

    entries = rebuild_ftp_history(store, athlete_id)
    print(f"  {len(entries)} ponto(s) de FTP no histórico")


def stage_load(store: CatalogStore, athlete_id: str, profile: HeartRateProfile) -> None:
    """Calcula IF/TSS com o FTP da época e HRSS onde não há potência."""
    from analytics.ftp_history import ftp_on

    activities = _activities(store.conn, athlete_id)
    by_power = by_hr = skipped = 0

    for index, (activity_id, activity_date) in enumerate(activities, start=1):
        series = load_series(store.conn, str(activity_id))
        if not series.segments:
            skipped += 1
            continue

        ftp = ftp_on(store, athlete_id, activity_date)
        metrics = compute_power_metrics(series, ftp_w=ftp)
        hrss = compute_hrss(series, profile)

        if metrics.tss is not None:
            tss, source = metrics.tss, "power"
            by_power += 1
        elif hrss is not None:
            tss, source = hrss, "hr"
            by_hr += 1
        else:
            tss, source = None, None
            skipped += 1

        store.conn.execute(
            """
            UPDATE activities SET
                tss = ?, tss_source = ?, hrss = ?,
                intensity_factor = ?, ftp_w_at_time = ?
            WHERE id = ?
            """,
            [tss, source, hrss, metrics.intensity_factor, ftp, activity_id],
        )
        if index % 200 == 0:
            print(f"    {index}/{len(activities)} atividades...")

    print(f"  TSS por potência: {by_power} | por FC: {by_hr} | sem carga: {skipped}")


def stage_calibrate(
    store: CatalogStore, athlete_id: str, profile: HeartRateProfile
) -> HeartRateProfile:
    """Ajusta a âncora de limiar comparando HRSS com o TSS de potência.

    Args:
        store: CatalogStore com conexão ativa.
        athlete_id: UUID do atleta.
        profile: perfil usado no cálculo corrente de HRSS.

    Returns:
        Perfil calibrado, ou o original se não houve pares suficientes.
    """
    from analytics.hr_metrics import calibrate_threshold_ratio

    # O HRSS é recalculado aqui em memória, com o perfil corrente, em vez de
    # lido da tabela: o valor gravado veio de uma execução anterior e de outro
    # perfil, o que tornaria a calibração dependente da ordem das etapas.
    rows = store.conn.execute(
        """
        SELECT id, tss FROM activities
        WHERE athlete_id = ? AND tss_source = 'power' AND tss IS NOT NULL
        """,
        [athlete_id],
    ).fetchall()

    pairs: list[tuple[float, float]] = []
    for activity_id, tss in rows:
        series = load_series(store.conn, str(activity_id))
        hrss = compute_hrss(series, profile)
        if hrss is not None:
            pairs.append((float(tss), hrss))

    ratio = calibrate_threshold_ratio(pairs, profile)
    if ratio is None:
        print("  pares insuficientes para calibrar — perfil mantido")
        return profile

    reserve = profile.max_hr_bpm - profile.resting_hr_bpm
    threshold_hr = profile.resting_hr_bpm + ratio * reserve
    print(
        f"  âncora de limiar: {profile.threshold_reserve_ratio:.3f} → {ratio:.3f} "
        f"da reserva (FC de limiar ≈ {threshold_hr:.0f} bpm)"
    )

    # As zonas de FC são ancoradas no limiar, então ele precisa ficar no
    # cadastro — senão a API não consegue montá-las.
    store.conn.execute(
        "UPDATE athletes SET threshold_hr_bpm = ? WHERE id = ?",
        [round(threshold_hr), athlete_id],
    )

    return HeartRateProfile(
        max_hr_bpm=profile.max_hr_bpm,
        resting_hr_bpm=profile.resting_hr_bpm,
        threshold_hr_bpm=threshold_hr,
    )


def stage_zones(store: CatalogStore, athlete_id: str) -> None:
    """Materializa as zonas vigentes em cada mudança de limiar.

    As zonas são deriváveis do FTP a qualquer momento, mas gravá-las por data
    permite responder "em que zona eu estava naquele treino" sem recalcular o
    histórico de FTP inteiro — e deixa o registro auditável.

    Args:
        store: CatalogStore com conexão ativa.
        athlete_id: UUID do atleta.
    """
    from analytics.zones import build_hr_zones, build_power_zones, persist_zones

    threshold_hr = store.conn.execute(
        "SELECT threshold_hr_bpm FROM athletes WHERE id = ?", [athlete_id]
    ).fetchone()
    hr_zones = (
        build_hr_zones(float(threshold_hr[0]))
        if threshold_hr and threshold_hr[0]
        else None
    )

    points = store.conn.execute(
        """
        SELECT effective_from, ftp_w FROM ftp_history
        WHERE athlete_id = ? ORDER BY effective_from
        """,
        [athlete_id],
    ).fetchall()

    for effective_from, ftp_w in points:
        persist_zones(
            store,
            athlete_id,
            effective_from,
            power_zones=build_power_zones(float(ftp_w)),
            # As zonas de FC não mudam com o FTP; grava-se apenas no ponto mais
            # recente para não duplicar a mesma tabela em cada data.
            hr_zones=hr_zones if (effective_from, ftp_w) == points[-1] else None,
        )

    print(f"  zonas gravadas para {len(points)} ponto(s) de FTP")


def stage_pmc(
    store: CatalogStore,
    athlete_id: str,
    seed_ctl: float = 0.0,
    seed_atl: float = 0.0,
) -> None:
    """Recalcula a série diária de CTL/ATL/TSB.

    Args:
        store: CatalogStore com conexão ativa.
        athlete_id: UUID do atleta.
        seed_ctl: CTL na véspera da primeira atividade, para históricos truncados.
        seed_atl: ATL na véspera da primeira atividade.
    """
    PMCCalculator().run_and_store(
        store, date.today(), athlete_id, seed_ctl=seed_ctl, seed_atl=seed_atl
    )
    row = store.conn.execute(
        "SELECT COUNT(*), MIN(date), MAX(date) FROM training_load WHERE athlete_id = ?",
        [athlete_id],
    ).fetchone()
    print(f"  {row[0]} dias de carga, de {row[1]} a {row[2]}")


def build_hr_profile(conn, athlete_id: str) -> HeartRateProfile:
    """Monta o perfil cardíaco do atleta, do cadastro ou estimado dos dados.

    Args:
        conn: conexão DuckDB.
        athlete_id: UUID do atleta.

    Returns:
        HeartRateProfile pronto para o cálculo de HRSS.
    """
    row = conn.execute(
        "SELECT max_hr_bpm, resting_hr_bpm, threshold_hr_bpm FROM athletes WHERE id = ?",
        [athlete_id],
    ).fetchone()
    max_hr = float(row[0]) if row and row[0] else None
    profile_resting = float(row[1]) if row and row[1] else None
    threshold_hr = float(row[2]) if row and row[2] else None

    if max_hr is None:
        # Percentil sobre o máximo de cada atividade, não sobre todas as
        # amostras: a maior parte do tempo de pedal é fácil, então o percentil
        # bruto mede FC de passeio, não FC máxima. O p99 dos picos por sessão
        # descarta o artefato isolado sem subestimar o teto real.
        estimated = conn.execute(
            """
            WITH per_activity AS (
                SELECT MAX(s.hr_bpm) AS peak
                FROM activity_streams s
                JOIN activities a ON a.id = s.activity_id
                WHERE a.athlete_id = ? AND s.hr_bpm BETWEEN 25 AND 220
                GROUP BY s.activity_id
            )
            SELECT quantile_cont(peak, 0.99) FROM per_activity
            """,
            [athlete_id],
        ).fetchone()
        max_hr = float(estimated[0]) if estimated and estimated[0] else 190.0
        print(f"  FC máxima estimada dos picos por sessão: {max_hr:.0f} bpm")

    if profile_resting is None:
        measured = conn.execute(
            """
            SELECT AVG(resting_hr_bpm) FROM health_metrics
            WHERE athlete_id = ? AND resting_hr_bpm IS NOT NULL
            """,
            [athlete_id],
        ).fetchone()
        profile_resting = float(measured[0]) if measured and measured[0] else 55.0
        print(f"  FC de repouso não cadastrada — usando {profile_resting:.0f} bpm")

    return HeartRateProfile(
        max_hr_bpm=max_hr,
        resting_hr_bpm=profile_resting,
        threshold_hr_bpm=threshold_hr,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        default=",".join(ALL_STAGES),
        help=f"etapas separadas por vírgula: {', '.join(ALL_STAGES)}",
    )
    parser.add_argument(
        "--seed-ctl",
        type=float,
        default=0.0,
        help="CTL na véspera da primeira atividade (histórico truncado)",
    )
    parser.add_argument(
        "--seed-atl", type=float, default=0.0, help="ATL na véspera da primeira atividade"
    )
    args = parser.parse_args()
    stages = [s.strip() for s in args.stage.split(",") if s.strip()]

    unknown = set(stages) - set(ALL_STAGES)
    if unknown:
        print(f"ERRO: etapa(s) desconhecida(s): {', '.join(sorted(unknown))}")
        return 1

    conn = duckdb.connect(DB_PATH)
    store = CatalogStore(conn)
    store.initialize_schema()
    athlete_id = store.resolve_athlete_id()

    profile = build_hr_profile(conn, athlete_id)
    print(
        f"Perfil cardíaco: FCmax {profile.max_hr_bpm:.0f} | "
        f"repouso {profile.resting_hr_bpm:.0f}\n"
    )

    for stage in stages:
        print(f"[{stage}]")
        if stage == "curves":
            stage_curves(store, athlete_id)
        elif stage == "metrics":
            stage_metrics(store, athlete_id)
        elif stage == "ftp":
            stage_ftp(store, athlete_id)
        elif stage == "load":
            stage_load(store, athlete_id, profile)
        elif stage == "calibrate":
            # Calibra a partir do HRSS já gravado e reprocessa a carga com a
            # âncora corrigida, para que as duas fontes fiquem na mesma escala.
            calibrated = stage_calibrate(store, athlete_id, profile)
            if calibrated is not profile:
                profile = calibrated
                stage_load(store, athlete_id, profile)
        elif stage == "zones":
            stage_zones(store, athlete_id)
        elif stage == "pmc":
            stage_pmc(store, athlete_id, args.seed_ctl, args.seed_atl)
        print()

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
