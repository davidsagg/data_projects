"""
Segment Classifier — classifica segmentos de rota por tipo e categoria de subida.

Tipos: climb (≥ 2%), flat (entre -2% e 2%), descent (≤ -2%).
Categorias de subida: HC, Cat1–Cat4 baseadas no score de dificuldade.
"""
from __future__ import annotations

from src.routes.gpx_analyzer import AnalyzedSegment


class SegmentClassifier:
    """Classifica segmentos de rota por tipo (climb/flat/descent) e categoria."""

    def classify(self, segments: list[AnalyzedSegment]) -> list[AnalyzedSegment]:
        """Atribui segment_type e category a cada segmento.

        Args:
            segments: lista de AnalyzedSegment com avg_gradient_pct preenchido

        Returns:
            A mesma lista com segment_type e category atualizados in-place.
        """
        for s in segments:
            if s.avg_gradient_pct >= 2:
                s.segment_type = "climb"
                s.category = self._category(s)
            elif s.avg_gradient_pct <= -2:
                s.segment_type = "descent"
            else:
                s.segment_type = "flat"
        return segments

    def _category(self, s: AnalyzedSegment) -> str:
        """Calcula a categoria de uma subida baseada no score de dificuldade.

        Score = elevation_delta_m × (avg_gradient_pct / 100) × (length_m / 1000)

        Args:
            s: segmento classificado como climb

        Returns:
            Categoria: "HC", "Cat1", "Cat2", "Cat3" ou "Cat4".
        """
        score = s.elevation_delta_m * (s.avg_gradient_pct / 100) * (s.length_m / 1000)
        if score >= 800:
            return "HC"
        elif score >= 400:
            return "Cat1"
        elif score >= 200:
            return "Cat2"
        elif score >= 100:
            return "Cat3"
        else:
            return "Cat4"
