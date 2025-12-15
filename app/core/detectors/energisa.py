"""Detector for Energisa concessionaria."""

import re

from .base import BaseDetector


class EnergisaDetector(BaseDetector):
    """Heuristic-based detector for Energisa invoices."""

    name = "ENERGISA"

    def score(self, text: str) -> float:
        """Return a cumulative score based on Energisa-specific signals."""
        normalized = (text or "").upper()
        total_score = 0.0

        if "ENERGISA" in normalized:
            total_score += 0.4

        if "DANF3E" in normalized:
            total_score += 0.25

        if "ENERGIA ATV INJETADA" in normalized:
            total_score += 0.2

        if re.search(r"10/\d{8}-\d", normalized):
            total_score += 0.25

        return min(1.0, total_score)
