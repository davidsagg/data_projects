"""
Cliente do Garmin Connect para métricas diárias de saúde.

O Garmin limita requisições por IP de forma agressiva (HTTP 429), então a
sessão é persistida em disco: relogar a cada execução é o caminho mais rápido
para ser bloqueado. Um backfill longo precisa de pausa entre os dias.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

DEFAULT_TOKEN_STORE = Path.home() / ".garminconnect"

# Pausa entre dias num backfill. O Garmin devolve 429 bem antes do que a
# documentação sugere; um segundo por dia mantém o lote estável.
BACKFILL_DELAY_S = 1.0


@dataclass
class HealthDaily:
    date: date
    sleep_duration_h: Optional[float] = None
    sleep_score: Optional[int] = None
    deep_sleep_min: Optional[int] = None
    rem_sleep_min: Optional[int] = None
    hrv_rmssd_ms: Optional[float] = None
    hrv_status: Optional[str] = None
    resting_hr_bpm: Optional[int] = None
    stress_avg: Optional[int] = None
    body_battery_max: Optional[int] = None
    body_battery_min: Optional[int] = None
    vo2max_estimated: Optional[float] = None
    steps: Optional[int] = None
    weight_kg: Optional[float] = None
    source: str = "garmin_connect"

    @property
    def is_empty(self) -> bool:
        """Indica se o dia não trouxe nenhuma métrica útil."""
        return all(
            getattr(self, field) is None
            for field in (
                "sleep_duration_h", "sleep_score", "hrv_rmssd_ms",
                "resting_hr_bpm", "stress_avg", "body_battery_max", "steps",
            )
        )


class GarminHealthClient:
    """Acesso somente-leitura às métricas diárias do Garmin Connect."""

    def __init__(
        self,
        email: str,
        password: str,
        token_store: Path | str | None = None,
    ) -> None:
        """Args:
            email: e-mail da conta Garmin.
            password: senha da conta.
            token_store: diretório onde a sessão é persistida entre execuções.
        """
        from garminconnect import Garmin

        self._token_store = Path(token_store or DEFAULT_TOKEN_STORE)
        self._api = Garmin(email, password)
        self._login()

    def _login(self) -> None:
        """Autentica reaproveitando a sessão em disco quando possível."""
        try:
            self._api.login(str(self._token_store))
            return
        except Exception:
            # Sessão ausente ou expirada: cai para login completo.
            pass

        self._api.login()
        try:
            self._api.garth.dump(str(self._token_store))
        except Exception:
            # Persistir a sessão é otimização, não requisito.
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_health_daily(self, target_date: date) -> HealthDaily:
        """Retorna as métricas consolidadas de um dia.

        Args:
            target_date: dia a consultar.

        Returns:
            HealthDaily com os campos que a conta tiver disponíveis.
        """
        date_str = target_date.isoformat()
        return self._build_health_daily(
            target_date,
            self._fetch_sleep(date_str),
            self._fetch_hrv(date_str),
            self._fetch_stats(date_str),
        )

    def get_health_range(
        self,
        start: date,
        end: date,
        delay_s: float = BACKFILL_DELAY_S,
        on_progress=None,
    ) -> list[HealthDaily]:
        """Retorna as métricas de cada dia do intervalo.

        Args:
            start: primeiro dia, inclusive.
            end: último dia, inclusive.
            delay_s: pausa entre requisições, para não tomar 429.
            on_progress: callback opcional recebendo cada `HealthDaily`.

        Returns:
            Lista de HealthDaily em ordem cronológica, incluindo dias vazios.
        """
        results: list[HealthDaily] = []
        current = start
        while current <= end:
            daily = self.get_health_daily(current)
            results.append(daily)
            if on_progress:
                on_progress(daily)
            current += timedelta(days=1)
            if delay_s and current <= end:
                time.sleep(delay_s)
        return results

    def get_weigh_ins(self, start: date, end: date) -> dict[date, float]:
        """Pesagens registradas no intervalo, em kg, uma por dia.

        O peso **não** vem em `get_stats` — o campo que o builder diário procura
        nunca chega preenchido. Ele mora na composição corporal: cada pesagem
        (balança conectada ou lançamento manual no app) é uma entrada de
        `dateWeightList`. Uma requisição cobre o intervalo inteiro.

        Args:
            start: primeiro dia, inclusive.
            end: último dia, inclusive.

        Returns:
            Dicionário {data: kg}; vazio se a conta não tem pesagens.
        """
        payload = self._safe(
            lambda: self._api.get_body_composition(start.isoformat(), end.isoformat())
        )
        return parse_weigh_ins(payload)

    # ------------------------------------------------------------------
    # Fetch primitives (patchable em testes)
    # ------------------------------------------------------------------

    def _fetch_sleep(self, date_str: str) -> dict:
        return self._safe(lambda: self._api.get_sleep_data(date_str))

    def _fetch_hrv(self, date_str: str) -> dict:
        return self._safe(lambda: self._api.get_hrv_data(date_str))

    def _fetch_stats(self, date_str: str) -> dict:
        return self._safe(lambda: self._api.get_stats(date_str))

    @staticmethod
    def _safe(call) -> dict:
        """Executa uma chamada tolerando dias sem dado.

        Args:
            call: função sem argumentos que faz a requisição.

        Returns:
            O payload, ou dicionário vazio quando o dia não tem registro.
        """
        try:
            return call() or {}
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Builder privado
    # ------------------------------------------------------------------

    @staticmethod
    def _build_health_daily(
        target_date: date,
        sleep_data: dict,
        hrv_data: dict,
        stats: dict,
    ) -> HealthDaily:
        """Traduz os três payloads do Garmin para o modelo interno.

        Args:
            target_date: dia consultado.
            sleep_data: retorno de `get_sleep_data`.
            hrv_data: retorno de `get_hrv_data`.
            stats: retorno de `get_stats`.

        Returns:
            HealthDaily preenchido com o que estiver disponível.
        """
        sleep_dto = sleep_data.get("dailySleepDTO") or {}
        sleep_secs = sleep_dto.get("sleepTimeSeconds") or 0
        overall = (sleep_dto.get("sleepScores") or {}).get("overall") or {}
        deep_secs = sleep_dto.get("deepSleepSeconds") or 0
        rem_secs = sleep_dto.get("remSleepSeconds") or 0

        # A API atual entrega o HRV em `hrvSummary`; versões antigas usavam
        # `lastNight`. Aceitar os dois evita quebrar com atualização do Garmin.
        summary = hrv_data.get("hrvSummary") or hrv_data.get("lastNight") or {}
        rmssd = summary.get("lastNightAvg") or summary.get("rmssd")

        # `sleepingSeconds` de stats cobre dias em que o detalhe de sono falta.
        if not sleep_secs:
            sleep_secs = stats.get("sleepingSeconds") or 0

        return HealthDaily(
            date=target_date,
            sleep_duration_h=round(sleep_secs / 3600, 2) if sleep_secs else None,
            sleep_score=overall.get("value"),
            deep_sleep_min=int(deep_secs / 60) if deep_secs else None,
            rem_sleep_min=int(rem_secs / 60) if rem_secs else None,
            hrv_rmssd_ms=float(rmssd) if rmssd is not None else None,
            hrv_status=summary.get("status"),
            resting_hr_bpm=stats.get("restingHeartRate"),
            stress_avg=stats.get("averageStressLevel"),
            body_battery_max=stats.get("bodyBatteryHighestValue"),
            body_battery_min=stats.get("bodyBatteryLowestValue"),
            vo2max_estimated=stats.get("vo2MaxValue"),
            steps=stats.get("totalSteps"),
            weight_kg=(
                round(stats["weight"] / 1000, 2)
                if stats.get("weight") else None
            ),
        )


def parse_weigh_ins(payload: dict) -> dict[date, float]:
    """Extrai as pesagens de um retorno de `get_body_composition`.

    Duas pesagens no mesmo dia: vale a mais recente (maior `date`, em ms) —
    quem se pesa de manhã e de noite quer o último registro, não a média.

    Args:
        payload: resposta do Garmin, com `dateWeightList` em gramas.

    Returns:
        Dicionário {data: kg}.
    """
    latest: dict[date, tuple[int, float]] = {}
    for entry in (payload or {}).get("dateWeightList") or []:
        grams = entry.get("weight")
        raw_day = entry.get("calendarDate")
        if not grams or not raw_day:
            continue
        day = date.fromisoformat(raw_day)
        stamp = entry.get("date") or 0
        if day not in latest or stamp >= latest[day][0]:
            latest[day] = (stamp, round(grams / 1000, 2))
    return {day: kg for day, (_, kg) in latest.items()}


def resolve_credentials() -> tuple[str, str] | None:
    """Lê as credenciais do ambiente.

    Returns:
        Par (email, senha), ou None se alguma não está configurada.
    """
    email = os.getenv("GARMIN_EMAIL", "").strip()
    password = os.getenv("GARMIN_PASSWORD", "").strip()
    if not email or not password or email == "your@email.com":
        return None
    return email, password
