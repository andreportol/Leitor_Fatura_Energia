"""Parser stub for Enel invoices."""

from .base import BaseParser


class EnelParser(BaseParser):
    """Minimal Enel parser placeholder."""

    def extract(self, text: str) -> dict:
        """Extract normalized energy bill data."""
        return {
            "energia_injetada_kwh": "",
            "energia_injetada_valor": "",
            "consumo_kwh": "",
            "preco_unitario": "",
        }
