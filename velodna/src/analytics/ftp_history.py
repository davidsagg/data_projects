"""
Histórico de FTP — evolução do limiar funcional ao longo do tempo.

Calcular TSS de 13 anos com um FTP fixo mistura duas coisas: o esforço da
sessão e a forma do atleta na época. Um treino de 2015 avaliado contra o FTP de
2026 aparece como mais fácil do que foi, e o CTL histórico fica sem sentido.

O eFTP é estimado por janela móvel a partir dos melhores esforços da curva de
potência. Para cada janela, toma-se o maior valor entre as estimativas
disponíveis — o melhor esforço de 20 min vale 95%, o de 60 min vale 100%.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta

# Janela retrospectiva usada em cada ponto do histórico. 90 dias é longo o
# bastante para capturar um teste de limiar e curto o bastante para acompanhar
# ganhos de forma dentro de uma temporada.
LOOKBACK_DAYS = 90

# Passo entre pontos do histórico.
STEP_DAYS = 30

# Fração do melhor esforço de cada duração que estima o FTP.
FTP_FACTOR_BY_DURATION = {
    1200: 0.95,   # teste clássico de 20 min
    1800: 0.98,   # 30 min
    2700: 0.99,   # 45 min
    3600: 1.00,   # uma hora no limiar, por definição
}

# Abaixo disso a estimativa vem de esforço curto demais para refletir o limiar.
MIN_DURATION_S = 1200

# Potência de corrida (Stryd e similares) não é comparável à de ciclismo: um
# esforço de 266 W correndo não diz nada sobre o FTP na bike. Toda estimativa
# de limiar considera apenas atividades de ciclismo.
POWER_SPORTS = ("cycling",)

# Quantidade mínima de atividades na janela para emitir uma estimativa. Sem
# isso, o primeiro ponto do histórico é calculado sobre uma janela que contém
# um único treino e produz um FTP artificialmente baixo.
MIN_ACTIVITIES_IN_WINDOW = 5

# Piso de plausibilidade. Atividades gravadas com potência zerada (sensor
# ausente mas campo presente) produziriam um "FTP" de 0 W.
MIN_PLAUSIBLE_FTP_W = 60.0

# Queda máxima do FTP por semana sem esforço que o confirme. O limiar sobe assim
# que aparece um esforço melhor, mas não desmorona só porque o atleta passou um
# trimestre sem testar — perda real de forma fica na casa de 1% a 2% por semana.
WEEKLY_DECAY = 0.985

# O destreino não é ilimitado: mesmo após uma longa parada, quem já construiu
# base não volta ao nível de um sedentário. O decaimento para neste piso,
# expresso como fração do melhor FTP já estimado.
DECAY_FLOOR_RATIO = 0.65


@dataclass(frozen=True)
class FTPPoint:
    """Uma estimativa de FTP válida a partir de uma data."""

    effective_from: date
    ftp_w: float
    method: str


def estimate_ftp_from_curve(curve: dict[int, float]) -> tuple[float, str] | None:
    """Estima o FTP a partir de uma curva de melhores esforços.

    Args:
        curve: {duração_s: melhor_potência_w} do período.

    Returns:
        Par (ftp_w, método), ou None se não há esforço longo o bastante.
    """
    candidates = [
        (power * factor, duration)
        for duration, factor in FTP_FACTOR_BY_DURATION.items()
        if (power := curve.get(duration)) is not None and duration >= MIN_DURATION_S
    ]
    candidates = [c for c in candidates if c[0] >= MIN_PLAUSIBLE_FTP_W]
    if not candidates:
        return None

    ftp_w, duration = max(candidates)
    return round(ftp_w, 1), f"best_{duration // 60}min"


def rebuild_ftp_history(store, athlete_id: str) -> list[FTPPoint]:
    """Reconstrói o histórico de FTP do atleta e o persiste.

    Args:
        store: CatalogStore com conexão ativa.
        athlete_id: UUID do atleta.

    Returns:
        Pontos de FTP gravados, em ordem cronológica.
    """
    placeholders = ", ".join("?" for _ in POWER_SPORTS)
    bounds = store.conn.execute(
        f"""
        SELECT MIN(date), MAX(date) FROM power_curves pc
        JOIN activities a ON a.id = pc.activity_id
        WHERE a.athlete_id = ? AND a.sport_type IN ({placeholders})
        """,
        [athlete_id, *POWER_SPORTS],
    ).fetchone()

    if not bounds or bounds[0] is None:
        return []

    first, last = bounds
    points: list[FTPPoint] = []
    previous: float | None = None

    peak = 0.0
    for current in _evaluation_dates(first, last):
        window_start = current - timedelta(days=LOOKBACK_DAYS)

        # Sem treino na janela não há o que estimar nem o que decair: manter o
        # decaimento rodando sobre um período sem dados inventaria uma queda de
        # forma que ninguém mediu.
        activity_count = _count_activities_between(
            store, athlete_id, window_start, current
        )
        if activity_count == 0:
            continue

        # Janela rala ainda não sustenta uma estimativa: só decai o valor
        # anterior, se houver, em vez de cravar um FTP sobre um único treino.
        if activity_count < MIN_ACTIVITIES_IN_WINDOW and previous is None:
            continue

        curve = _best_curve_between(store, athlete_id, window_start, current)
        estimate = estimate_ftp_from_curve(curve)

        floor = peak * DECAY_FLOOR_RATIO if peak else None
        ftp_w, method = _apply_decay(estimate, previous, floor)
        if ftp_w is None:
            continue

        if previous is None or abs(ftp_w - previous) >= 1.0:
            points.append(FTPPoint(current, round(ftp_w, 1), method))
        previous = ftp_w
        peak = max(peak, ftp_w)

    _persist(store, athlete_id, points)
    return points


def _evaluation_dates(first: date, last: date) -> list[date]:
    """Datas em que o FTP é reavaliado.

    A última data entra sempre, mesmo que não caia no passo regular: sem isso,
    um histórico mais curto que `STEP_DAYS` nunca chegaria a ser avaliado.

    Args:
        first: primeira data com curva de potência.
        last: última data com curva de potência.

    Returns:
        Datas em ordem crescente, sem repetição.
    """
    dates: list[date] = []
    current = first
    while current <= last:
        dates.append(current)
        current += timedelta(days=STEP_DAYS)

    if not dates or dates[-1] != last:
        dates.append(last)
    return dates


def _apply_decay(
    estimate: tuple[float, str] | None,
    previous: float | None,
    hard_floor: float | None = None,
) -> tuple[float | None, str]:
    """Combina a estimativa da janela com o FTP anterior, limitando a queda.

    Um esforço melhor eleva o FTP imediatamente. Na ausência de esforço que
    confirme o valor, o FTP cai no máximo `WEEKLY_DECAY` por semana em vez de
    seguir o máximo da janela para baixo — e nunca abaixo de `hard_floor`.

    Args:
        estimate: par (ftp_w, método) da janela, se houver.
        previous: FTP do ponto anterior do histórico.
        hard_floor: piso absoluto de destreino.

    Returns:
        Par (ftp_w, método); ftp_w é None quando não há base alguma.
    """
    decayed = None
    if previous is not None:
        decayed = previous * (WEEKLY_DECAY ** (STEP_DAYS / 7))
        if hard_floor is not None:
            decayed = max(decayed, hard_floor)

    if estimate is None:
        return (decayed, "decayed") if decayed is not None else (None, "")

    ftp_w, method = estimate
    if decayed is not None and decayed > ftp_w:
        return decayed, "decayed"
    return ftp_w, method


def _count_activities_between(store, athlete_id: str, start: date, end: date) -> int:
    """Conta as atividades do atleta num intervalo.

    Args:
        store: CatalogStore com conexão ativa.
        athlete_id: UUID do atleta.
        start: início do intervalo, inclusive.
        end: fim do intervalo, inclusive.

    Returns:
        Número de atividades no período.
    """
    return store.conn.execute(
        """
        SELECT COUNT(*) FROM activities
        WHERE athlete_id = ? AND CAST(started_at AS DATE) BETWEEN ? AND ?
        """,
        [athlete_id, start, end],
    ).fetchone()[0]


def ftp_on(store, athlete_id: str, target: date) -> float | None:
    """Retorna o FTP vigente numa data.

    Um valor medido — teste de campo ou informado pelo atleta — é a referência
    e funciona como piso a partir da sua data. Estimativas posteriores só o
    revisam **para cima**: um esforço melhor prova ganho de forma, mas a
    ausência de esforço máximo não prova perda. Sem isso, quem passa meses
    treinando em base vê o FTP cair sem ter perdido nada.

    Args:
        store: CatalogStore com conexão ativa.
        athlete_id: UUID do atleta.
        target: data de interesse.

    Returns:
        FTP em watts, ou None se o histórico está vazio.
    """
    measured = store.conn.execute(
        """
        SELECT ftp_w, effective_from FROM ftp_history
        WHERE athlete_id = ? AND effective_from <= ? AND source IN ('test', 'manual')
        ORDER BY effective_from DESC LIMIT 1
        """,
        [athlete_id, target],
    ).fetchone()

    if measured:
        ftp_w, measured_on = float(measured[0]), measured[1]
        higher = store.conn.execute(
            """
            SELECT MAX(ftp_w) FROM ftp_history
            WHERE athlete_id = ? AND source = 'estimated'
              AND effective_from > ? AND effective_from <= ?
            """,
            [athlete_id, measured_on, target],
        ).fetchone()
        if higher and higher[0] is not None:
            ftp_w = max(ftp_w, float(higher[0]))
        return ftp_w

    estimated = store.conn.execute(
        """
        SELECT ftp_w FROM ftp_history
        WHERE athlete_id = ? AND effective_from <= ?
        ORDER BY effective_from DESC LIMIT 1
        """,
        [athlete_id, target],
    ).fetchone()
    if estimated:
        return float(estimated[0])

    earliest = store.conn.execute(
        """
        SELECT ftp_w FROM ftp_history
        WHERE athlete_id = ? ORDER BY effective_from ASC LIMIT 1
        """,
        [athlete_id],
    ).fetchone()
    return float(earliest[0]) if earliest else None


def _best_curve_between(
    store, athlete_id: str, start: date, end: date
) -> dict[int, float]:
    """Melhores esforços do atleta num intervalo de datas.

    Args:
        store: CatalogStore com conexão ativa.
        athlete_id: UUID do atleta.
        start: início do intervalo, inclusive.
        end: fim do intervalo, inclusive.

    Returns:
        Dicionário {duração_s: melhor_potência_w}.
    """
    placeholders = ", ".join("?" for _ in POWER_SPORTS)
    rows = store.conn.execute(
        f"""
        SELECT pc.duration_s, MAX(pc.power_w)
        FROM power_curves pc
        JOIN activities a ON a.id = pc.activity_id
        WHERE a.athlete_id = ? AND pc.date BETWEEN ? AND ?
          AND a.sport_type IN ({placeholders})
        GROUP BY pc.duration_s
        """,
        [athlete_id, start, end, *POWER_SPORTS],
    ).fetchall()
    return {int(r[0]): float(r[1]) for r in rows}


def _persist(store, athlete_id: str, points: list[FTPPoint]) -> None:
    """Substitui o histórico de FTP do atleta.

    Args:
        store: CatalogStore com conexão ativa.
        athlete_id: UUID do atleta.
        points: pontos a gravar.
    """
    store.conn.execute(
        "DELETE FROM ftp_history WHERE athlete_id = ? AND source = 'estimated'",
        [athlete_id],
    )
    if not points:
        return

    store.conn.executemany(
        """
        INSERT INTO ftp_history (id, athlete_id, effective_from, ftp_w, method, source)
        VALUES (?, ?, ?, ?, ?, 'estimated')
        ON CONFLICT (athlete_id, effective_from) DO UPDATE SET
            ftp_w = EXCLUDED.ftp_w, method = EXCLUDED.method
        """,
        [
            (str(uuid.uuid4()), athlete_id, p.effective_from, p.ftp_w, p.method)
            for p in points
        ],
    )
