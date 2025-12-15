"""Detector for Enel concessionaria."""

from .base import BaseDetector


class EnelDetector(BaseDetector):
    """Minimal Enel detector stub."""

    name = "ENEL"

    def score(self, text: str) -> float:
        """Return a minimal score placeholder."""
        return 0.0
