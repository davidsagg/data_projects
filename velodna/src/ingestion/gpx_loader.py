from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RouteWaypoint:
    lat: float
    lon: float
    altitude_m: Optional[float] = None
    distance_m: Optional[float] = None


@dataclass
class Route:
    name: str
    source: str
    gpx_file_path: str
    distance_m: float
    elevation_gain_m: float
    elevation_loss_m: float
    waypoints: list = field(default_factory=list)


class GPXParseError(Exception):
    pass


import math


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi   = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class GPXLoader:
    def load(self, path, name: str | None = None, source: str = "manual_upload") -> Route:
        from pathlib import Path
        import gpxpy

        path = Path(path)
        if not path.exists():
            raise GPXParseError(f"File not found: {path}")

        try:
            with open(path) as fh:
                gpx = gpxpy.parse(fh)
        except Exception as exc:
            raise GPXParseError(f"Cannot parse GPX {path.name}: {exc}") from exc

        # Collect all points from tracks and route elements
        raw_points: list = []
        for track in gpx.tracks:
            for segment in track.segments:
                raw_points.extend(segment.points)
        for route in gpx.routes:
            raw_points.extend(route.points)

        if not raw_points:
            raise GPXParseError(f"No waypoints found in {path.name}")

        total_distance = 0.0
        gain = 0.0
        loss = 0.0
        waypoints: list[RouteWaypoint] = []

        for i, pt in enumerate(raw_points):
            if i == 0:
                d_from_start = 0.0
            else:
                prev = raw_points[i - 1]
                seg_dist = _haversine(prev.latitude, prev.longitude, pt.latitude, pt.longitude)
                total_distance += seg_dist
                d_from_start = total_distance

                if prev.elevation is not None and pt.elevation is not None:
                    delta = pt.elevation - prev.elevation
                    if delta > 0:
                        gain += delta
                    else:
                        loss += abs(delta)

            waypoints.append(RouteWaypoint(
                lat=pt.latitude,
                lon=pt.longitude,
                altitude_m=pt.elevation,
                distance_m=d_from_start,
            ))

        route_name = name or gpx.name or path.stem

        return Route(
            name=route_name,
            source=source,
            gpx_file_path=str(path),
            distance_m=total_distance,
            elevation_gain_m=gain,
            elevation_loss_m=loss,
            waypoints=waypoints,
        )
