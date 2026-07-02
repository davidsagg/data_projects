from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ActivityStream:
    timestamp: datetime
    power_w: Optional[int] = None
    heart_rate_bpm: Optional[int] = None
    cadence_rpm: Optional[int] = None
    speed_ms: Optional[float] = None
    altitude_m: Optional[float] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    distance_m: Optional[float] = None
    temperature_c: Optional[float] = None


@dataclass
class Activity:
    garmin_id: str
    sport_type: str
    start_time: datetime
    duration_s: int
    distance_m: float
    elevation_m: float
    avg_power_w: Optional[float] = None
    max_power_w: Optional[float] = None
    avg_hr_bpm: Optional[float] = None
    max_hr_bpm: Optional[int] = None
    fit_file_path: Optional[str] = None
    streams: list = field(default_factory=list)


class FITParseError(Exception):
    pass


_SEMICIRCLE_TO_DEG = 180.0 / 2**31


class FITParser:
    def parse(self, path) -> Activity:
        from pathlib import Path
        import fitparse

        path = Path(path)
        try:
            fit = fitparse.FitFile(str(path))
            # force full parse so corrupt files raise immediately
            sessions = list(fit.get_messages("session"))
        except Exception as exc:
            raise FITParseError(f"Cannot parse {path.name}: {exc}") from exc

        if not sessions:
            raise FITParseError(f"No session data in {path.name}")

        s = sessions[0]

        start_time = s.get_value("start_time")
        if start_time is None:
            raise FITParseError(f"Missing start_time in {path.name}")

        elapsed  = s.get_value("total_elapsed_time") or 0
        distance = s.get_value("total_distance")     or 0.0
        sport    = s.get_value("sport")              or "unknown"
        ascent   = s.get_value("total_ascent")       or 0.0

        garmin_id = start_time.strftime("%Y%m%d_%H%M%S")

        streams: list[ActivityStream] = []
        for record in fit.get_messages("record"):
            ts = record.get_value("timestamp")
            if ts is None:
                continue
            lat_sc = record.get_value("position_lat")
            lon_sc = record.get_value("position_long")
            streams.append(ActivityStream(
                timestamp=ts,
                power_w=record.get_value("power"),
                heart_rate_bpm=record.get_value("heart_rate"),
                cadence_rpm=record.get_value("cadence"),
                speed_ms=record.get_value("speed"),
                altitude_m=record.get_value("altitude"),
                lat=lat_sc * _SEMICIRCLE_TO_DEG if lat_sc is not None else None,
                lon=lon_sc * _SEMICIRCLE_TO_DEG if lon_sc is not None else None,
                distance_m=record.get_value("distance"),
                temperature_c=record.get_value("temperature"),
            ))

        return Activity(
            garmin_id=garmin_id,
            sport_type=str(sport),
            start_time=start_time,
            duration_s=int(elapsed),
            distance_m=float(distance),
            elevation_m=float(ascent),
            avg_power_w=s.get_value("avg_power"),
            max_power_w=s.get_value("max_power"),
            avg_hr_bpm=s.get_value("avg_heart_rate"),
            max_hr_bpm=s.get_value("max_heart_rate"),
            fit_file_path=str(path),
            streams=streams,
        )
