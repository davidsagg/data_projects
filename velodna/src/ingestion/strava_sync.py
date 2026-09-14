"""
Sincronização Strava → catálogo VeloDNA.

O acervo já tem 591 atividades vindas dos arquivos `.fit`, e o Strava devolve
exatamente as mesmas pedaladas. Importar sem casar duplicaria tudo e envenenaria
o PMC — o TSS de cada dia contaria em dobro. Por isso o fluxo aqui é sempre
"procurar antes de inserir", em três níveis: pelo `strava_id` já vinculado, pelo
horário de início próximo a uma atividade existente, e só então como novidade.

As métricas derivadas (NP, IF, VI, TSS) **não** vêm do Strava. O
`weighted_average_watts` deles é uma NP calculada com regra própria, que ignora
as pausas do jeito que este projeto não ignora. Deixar os campos vazios e rodar
`scripts/recompute_metrics.py` depois mantém o acervo inteiro calculado pelo
mesmo critério.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import islice
from datetime import datetime, timezone

from storage.catalog_store import CatalogStore
from storage.models import Activity, ActivityStream

# Nomes de esporte do Strava para o enum do Garmin já usado no catálogo
# (`cycling`, `running`, ...), que veio do campo `sport` dos arquivos `.fit`.
SPORT_MAP = {
    "Ride": "cycling",
    "VirtualRide": "cycling",
    "GravelRide": "cycling",
    "MountainBikeRide": "cycling",
    "EBikeRide": "cycling",
    "Handcycle": "cycling",
    "Velomobile": "cycling",
    "Run": "running",
    "TrailRun": "running",
    "VirtualRun": "running",
    "Swim": "swimming",
    "Walk": "walking",
    "Hike": "walking",
    "WeightTraining": "training",
    "Workout": "training",
    "Crossfit": "training",
    "Elliptical": "training",
    "StairStepper": "training",
    "Yoga": "training",
}

# Janela para considerar que uma atividade do Strava e uma do catálogo são o
# mesmo treino. Garmin e Strava registram o mesmo início e divergem por
# segundos; cinco minutos é folgado sem correr risco de casar treinos vizinhos.
MATCH_TOLERANCE_S = 300


@dataclass
class SyncReport:
    """Resultado de uma execução da sincronização."""

    fetched: int = 0
    inserted: int = 0
    linked: int = 0
    skipped: int = 0
    streams_added: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Resumo de uma linha, para log e saída de terminal."""
        return (
            f"{self.fetched} do Strava · {self.inserted} novas · "
            f"{self.linked} vinculadas a atividades existentes · "
            f"{self.skipped} já sincronizadas · {self.streams_added} com streams"
        )


def normalize_sport(strava_sport: str | None) -> str:
    """Converte o esporte do Strava para o vocabulário do catálogo.

    Args:
        strava_sport: valor de `sport_type` (ou `type`) devolvido pelo Strava.

    Returns:
        Nome canônico do esporte; `unknown` quando não há correspondência.
    """
    if not strava_sport:
        return "unknown"
    return SPORT_MAP.get(strava_sport, strava_sport.lower())


def parse_start(raw: str) -> datetime:
    """Interpreta o `start_date` do Strava, que vem em UTC com sufixo `Z`.

    Args:
        raw: timestamp ISO-8601, por exemplo `2026-09-01T10:24:31Z`.

    Returns:
        datetime ciente de fuso, em UTC.
    """
    return datetime.fromisoformat(raw).astimezone(timezone.utc)


def activity_from_strava(summary: dict) -> Activity:
    """Converte o resumo de atividade do Strava para o modelo de domínio.

    NP, IF, VI e TSS ficam vazios de propósito — são responsabilidade da camada
    de analytics, que os recalcula para todo o acervo sob o mesmo critério.

    Args:
        summary: atividade resumida devolvida por `/athlete/activities`.

    Returns:
        Activity pronta para persistência, ainda sem streams.
    """
    return Activity(
        source="strava",
        sport_type=normalize_sport(summary.get("sport_type") or summary.get("type")),
        started_at=parse_start(summary["start_date"]),
        elapsed_time_s=int(summary.get("elapsed_time") or 0),
        moving_time_s=_maybe_int(summary.get("moving_time")),
        strava_id=int(summary["id"]),
        distance_m=_maybe_float(summary.get("distance")),
        elevation_gain_m=_maybe_float(summary.get("total_elevation_gain")),
        avg_power_w=_maybe_float(summary.get("average_watts")),
        max_power_w=_maybe_float(summary.get("max_watts")),
        avg_hr_bpm=_maybe_float(summary.get("average_heartrate")),
        max_hr_bpm=_maybe_int(summary.get("max_heartrate")),
        avg_cadence_rpm=_maybe_float(summary.get("average_cadence")),
        avg_speed_ms=_maybe_float(summary.get("average_speed")),
    )


def streams_from_strava(payload: dict) -> list[ActivityStream]:
    """Converte os streams do Strava para o modelo de domínio.

    O Strava entrega cada canal como uma lista paralela à de `time`, que já vem
    em segundos relativos ao início — a mesma convenção de `ActivityStream`. As
    coordenadas chegam como pares `[lat, lon]` num único canal `latlng`.

    Args:
        payload: resposta de `/activities/{id}/streams` com `key_by_type=true`.

    Returns:
        Lista de pontos; vazia se não houver canal de tempo.
    """
    times = _channel(payload, "time")
    if not times:
        return []

    watts = _channel(payload, "watts")
    heartrate = _channel(payload, "heartrate")
    cadence = _channel(payload, "cadence")
    velocity = _channel(payload, "velocity_smooth")
    altitude = _channel(payload, "altitude")
    distance = _channel(payload, "distance")
    latlng = _channel(payload, "latlng")
    temp = _channel(payload, "temp")

    points: list[ActivityStream] = []
    for index, time_s in enumerate(times):
        position = _at(latlng, index)
        points.append(
            ActivityStream(
                time_s=int(time_s),
                lat=position[0] if isinstance(position, (list, tuple)) else None,
                lon=position[1] if isinstance(position, (list, tuple)) else None,
                altitude_m=_at(altitude, index),
                distance_m=_at(distance, index),
                power_w=_at(watts, index),
                hr_bpm=_at(heartrate, index),
                cadence_rpm=_at(cadence, index),
                speed_ms=_at(velocity, index),
                temperature_c=_at(temp, index),
            )
        )
    return points


class StravaSync:
    """Traz atividades do Strava para o catálogo sem duplicar o que já existe."""

    def __init__(self, client, store: CatalogStore) -> None:
        """Args:
            client: instância de `StravaClient` (ou equivalente para teste).
            store: catálogo de destino.
        """
        self._client = client
        self._store = store

    def sync(
        self,
        after: datetime | None = None,
        before: datetime | None = None,
        limit: int | None = None,
        with_streams: bool = True,
        athlete_id: str | None = None,
    ) -> SyncReport:
        """Sincroniza as atividades do período.

        Args:
            after: só atividades iniciadas depois deste instante.
            before: só atividades iniciadas antes deste instante.
            limit: número máximo de atividades a processar.
            with_streams: busca a série temporal de cada atividade nova.
            athlete_id: dono das atividades; resolvido automaticamente se omitido.

        Returns:
            SyncReport com a contagem de cada desfecho.
        """
        summaries = self._client.iter_activities(after=after, before=before)
        if limit is not None:
            summaries = islice(summaries, limit)
        return self.sync_summaries(list(summaries), with_streams, athlete_id)

    def sync_summaries(
        self,
        summaries: list[dict],
        with_streams: bool = True,
        athlete_id: str | None = None,
        report: SyncReport | None = None,
    ) -> SyncReport:
        """Persiste uma lista de atividades já baixada do Strava.

        Separar a busca da gravação é o que permite ao script processar em
        lotes: o DuckDB aceita um único escritor, e segurar a conexão durante um
        backfill inteiro — que é sobretudo espera de rede — bloquearia a API
        local por minutos a fio.

        Args:
            summaries: atividades resumidas, como devolvidas pelo Strava.
            with_streams: busca a série temporal de cada atividade nova.
            athlete_id: dono das atividades; resolvido automaticamente se omitido.
            report: relatório a acumular; um novo é criado se omitido.

        Returns:
            O relatório, com as contagens deste lote somadas.
        """
        athlete_id = athlete_id or self._store.resolve_athlete_id()
        report = report or SyncReport()

        for summary in summaries:
            report.fetched += 1
            try:
                self._sync_one(summary, athlete_id, with_streams, report)
            except Exception as error:  # noqa: BLE001 — um treino ruim não derruba o lote
                report.errors.append(f"atividade {summary.get('id')}: {error}")

        return report

    def _sync_one(
        self,
        summary: dict,
        athlete_id: str,
        with_streams: bool,
        report: SyncReport,
    ) -> None:
        """Processa uma atividade: já existe, casa com uma local, ou é nova."""
        strava_id = int(summary["id"])

        if self._store.find_activity_by_strava_id(strava_id):
            report.skipped += 1
            return

        activity = activity_from_strava(summary)

        # A mesma pedalada já pode estar no catálogo, vinda de um `.fit`.
        # Nesse caso o registro local é mais rico (tem os streams originais do
        # Garmin) — anota-se o `strava_id` nele e não se insere nada.
        twin = self._store.find_activity_near(
            athlete_id, activity.started_at, MATCH_TOLERANCE_S
        )
        if twin:
            self._store.attach_strava_id(twin, strava_id)
            report.linked += 1
            if with_streams and self._store.count_streams(twin) == 0:
                report.streams_added += self._fetch_streams(twin, strava_id)
            return

        activity_id = self._store.upsert_activity(activity, athlete_id)
        report.inserted += 1
        if with_streams:
            report.streams_added += self._fetch_streams(activity_id, strava_id)

    def _fetch_streams(self, activity_id: str, strava_id: int) -> int:
        """Busca e persiste os streams de uma atividade. Devolve 1 se gravou."""
        points = streams_from_strava(self._client.get_activity_streams(strava_id))
        if not points:
            return 0
        self._store.insert_streams(activity_id, points)
        return 1


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def _channel(payload: dict, name: str) -> list:
    """Extrai a lista de dados de um canal, tolerando canal ausente."""
    channel = payload.get(name)
    if isinstance(channel, dict):
        return channel.get("data") or []
    return channel or []


def _at(values: list, index: int):
    """Devolve o valor do índice, ou None quando o canal é mais curto."""
    return values[index] if index < len(values) else None


def _maybe_float(value) -> float | None:
    return float(value) if value is not None else None


def _maybe_int(value) -> int | None:
    return int(value) if value is not None else None
