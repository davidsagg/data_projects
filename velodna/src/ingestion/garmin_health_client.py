from dataclasses import dataclass
from datetime import date
from typing import Optional


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
    source: str = 'garmin_connect'


class GarminHealthClient:
    def __init__(self, email: str, password: str) -> None:
        from garminconnect import Garmin
        self._api = Garmin(email, password)
        self._api.login()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_health_daily(self, target_date: date) -> HealthDaily:
        """Retorna métricas de saúde consolidadas para um único dia."""
        date_str   = target_date.isoformat()
        sleep_data = self._fetch_sleep(date_str)
        hrv_data   = self._fetch_hrv(date_str)
        return self._build_health_daily(target_date, sleep_data, hrv_data)

    def get_health_range(self, start: date, end: date) -> list:
        """Retorna lista de HealthDaily para cada dia do intervalo [start, end]."""
        from datetime import timedelta
        results = []
        current = start
        while current <= end:
            results.append(self.get_health_daily(current))
            current += timedelta(days=1)
        return results

    # ------------------------------------------------------------------
    # Fetch primitives (patchable em testes)
    # ------------------------------------------------------------------

    def _fetch_sleep(self, date_str: str) -> dict:
        return self._api.get_sleep_data(date_str)

    def _fetch_hrv(self, date_str: str) -> dict:
        return self._api.get_hrv_data(date_str)

    # ------------------------------------------------------------------
    # Builder privado
    # ------------------------------------------------------------------

    @staticmethod
    def _build_health_daily(
        target_date: date,
        sleep_data: dict,
        hrv_data: dict,
    ) -> HealthDaily:
        sleep_dto    = sleep_data.get("dailySleepDTO") or {}
        sleep_secs   = sleep_dto.get("sleepTimeSeconds") or 0
        sleep_scores = sleep_dto.get("sleepScores") or {}
        overall      = sleep_scores.get("overall") or {}
        deep_secs    = sleep_dto.get("deepSleepSeconds") or 0
        rem_secs     = sleep_dto.get("remSleepSeconds")  or 0

        last_night   = hrv_data.get("lastNight") or {}

        return HealthDaily(
            date=target_date,
            sleep_duration_h=round(sleep_secs / 3600, 2) if sleep_secs else None,
            sleep_score=overall.get("value"),
            deep_sleep_min=int(deep_secs / 60) if deep_secs else None,
            rem_sleep_min=int(rem_secs / 60)   if rem_secs  else None,
            hrv_rmssd_ms=last_night.get("rmssd"),
            hrv_status=last_night.get("status"),
        )
