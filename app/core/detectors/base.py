"""Detector base class for concessionaria identification."""


class BaseDetector:
    """Base detector with a scoring interface."""

    name: str = ""

    def score(self, text: str) -> float:
        """Return a score between 0.0 and 1.0."""
        raise NotImplementedError
