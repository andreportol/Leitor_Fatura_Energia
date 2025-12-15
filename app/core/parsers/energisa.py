"""Parser for Energisa invoices using existing extraction helpers."""

from app.core.services import processamento_energisa as processamento

from .base import BaseParser


class EnergisaParser(BaseParser):
    """Parser that reuses existing Energisa regex logic."""

    def extract(self, text: str) -> dict:
        """Extract normalized energy bill data."""
        texto = text or ""

        consumo = processamento.extrair_consumo_kwh(texto)
        preco_unitario = processamento.extrair_preco_unitario(texto)

        valor_float = processamento.extrair_energia_injetada_valor(texto)
        energia_injetada_valor = (
            processamento.float_to_br(valor_float) if valor_float > 0 else ""
        )

        energia_injetada_kwh = ""
        preco_float = processamento.br_to_float(preco_unitario)
        if valor_float > 0 and preco_float > 0:
            energia_injetada_kwh = processamento.float_to_br(
                valor_float / preco_float
            )

        return {
            "energia_injetada_kwh": energia_injetada_kwh,
            "energia_injetada_valor": energia_injetada_valor,
            "consumo_kwh": consumo,
            "preco_unitario": preco_unitario,
        }
