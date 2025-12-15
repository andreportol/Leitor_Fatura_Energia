"""Service for detecting concessionaria based on extracted text."""

from typing import List

from .base import BaseDetector
from .cpfl import CPFLDetector
from .enel import EnelDetector
from .energisa import EnergisaDetector


def detect_concessionaria(text: str) -> str:
    """Run all detectors and return the best matched concessionaria name."""
    detectors: List[BaseDetector] = [
        EnergisaDetector(),
        EnelDetector(),
        CPFLDetector(),
    ]

    best_name = "ENERGISA"
    best_score = 0.0
    for detector in detectors:
        score = detector.score(text)
        if score > best_score:
            best_name = detector.name or best_name
            best_score = score

    return best_name
