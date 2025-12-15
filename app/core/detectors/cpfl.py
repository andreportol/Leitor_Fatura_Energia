"""Detector for CPFL concessionaria."""

from .base import BaseDetector


class CPFLDetector(BaseDetector):
    """Minimal CPFL detector stub."""

    name = "CPFL"

    def score(self, text: str) -> float:
        """Return a minimal score placeholder."""
        return 0.0
