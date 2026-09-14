"""
GPX Analyzer — análise de perfil de elevação e segmentos de rotas.

GPXAnalyzer: processa waypoints de uma Route e retorna ElevationProfile
             com segmentos de 500 m, gradientes e métricas de elevação.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional

from ingestion.gpx_loader import Route


@dataclass
class AnalyzedSegment:
    """Segmento de 500 m de uma rota com métricas de elevação e gradiente."""

    start_d: float
    end_d: float
    length_m: float
    elevation_delta_m: float
    avg_gradient_pct: float
    segment_type: str = "flat"
    category: Optional[str] = None
    recommended_power_w: Optional[float] = None


@dataclass
class ElevationProfile:
    """Perfil de elevação completo de uma rota."""

    total_gain_m: float
    total_loss_m: float
    max_gradient_pct: float
    segments: list = field(default_factory=list)


class GPXAnalyzer:
    """Analisa o perfil de elevação de uma rota GPX em segmentos de 500 m."""

    SEG_LEN = 500  # metros por segmento

    def analyze(self, route: Route) -> ElevationProfile:
        """Calcula o perfil de elevação e divide a rota em segmentos.

        Args:
            route: objeto Route com lista de RouteWaypoint

        Returns:
            ElevationProfile com métricas de elevação e lista de AnalyzedSegment.
        """
        wps = route.waypoints
        if len(wps) < 2:
            return ElevationProfile(0, 0, 0, [])

        gain = loss = 0.0
        segs = []
        cumulative_dist = 0.0
        current_alt = wps[0].altitude_m or 0
        seg_start_dist = 0.0
        prev_wp = wps[0]

        for wp in wps[1:]:
            # Acumula ganho/perda de elevação
            if prev_wp.altitude_m is not None and wp.altitude_m is not None:
                delta = wp.altitude_m - prev_wp.altitude_m
                if delta > 0:
                    gain += delta
                else:
                    loss += abs(delta)

            step = (wp.distance_m or 0) - (prev_wp.distance_m or 0)
            cumulative_dist += step

            # Fecha segmento quando atinge SEG_LEN ou é o último waypoint
            if cumulative_dist >= self.SEG_LEN or wp is wps[-1]:
                end_alt = wp.altitude_m or current_alt
                elev_delta = end_alt - current_alt
                grad = (elev_delta / cumulative_dist * 100) if cumulative_dist > 0 else 0.0
                segs.append(AnalyzedSegment(
                    start_d=seg_start_dist,
                    end_d=wp.distance_m or 0,
                    length_m=cumulative_dist,
                    elevation_delta_m=elev_delta,
                    avg_gradient_pct=round(grad, 2),
                ))
                seg_start_dist = wp.distance_m or 0
                current_alt = end_alt
                cumulative_dist = 0.0

            prev_wp = wp

        max_grad = max((abs(s.avg_gradient_pct) for s in segs), default=0)
        return ElevationProfile(gain, loss, max_grad, segs)

    def analyze_and_store(
        self, route: Route, store, athlete_id: str | None = None
    ) -> ElevationProfile:
        """Analisa a rota e persiste resultado no DuckDB via CatalogStore.

        Args:
            route: objeto Route com waypoints
            store: instância de CatalogStore
            athlete_id: dono da rota; resolvido do catálogo quando omitido

        Returns:
            ElevationProfile calculado.
        """
        if athlete_id is None:
            athlete_id = store.resolve_athlete_id()
        profile = self.analyze(route)

        segments = [
            {
                "segment_type": s.segment_type,
                "length_m": s.length_m,
                "elevation_delta_m": s.elevation_delta_m,
                "avg_gradient_pct": s.avg_gradient_pct,
            }
            for s in profile.segments
        ]
        waypoints = [
            {
                "lat": wp.lat,
                "lon": wp.lon,
                "altitude_m": wp.altitude_m,
                "distance_from_start_m": wp.distance_m,
            }
            for wp in route.waypoints
        ]

        store.insert_route(
            athlete_id,
            route.name,
            waypoints,
            segments=segments,
            source_file_path=route.gpx_file_path,
            distance_m=route.distance_m,
            elevation_gain_m=profile.total_gain_m,
        )
        return profile
