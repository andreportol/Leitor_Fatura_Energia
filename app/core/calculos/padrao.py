"""Default calculation policy (30% economy, 70% payable)."""

from app.core.services import processamento_energisa as processamento

from .base import PoliticaCalculo


class PoliticaPadrao(PoliticaCalculo):
    """Applies standard economy and payable split."""

    def calcular(self, dados: dict) -> dict:
        """Return economia and valor_a_pagar."""
        dados = dados or {}
        base_valor = processamento.br_to_float(dados.get("energia_injetada_valor", ""))

        if base_valor <= 0:
            return {"economia": "", "valor_a_pagar": ""}

        economia = base_valor * 0.3
        pagar = base_valor * 0.7

        return {
            "economia": processamento.float_to_br(economia),
            "valor_a_pagar": processamento.float_to_br(pagar),
        }
