"""VIP calculation policy (0% economy, 100% payable)."""

from app.core.services import processamento_energisa as processamento

from .base import PoliticaCalculo


class PoliticaVIP(PoliticaCalculo):
    """Applies VIP policy with full payable value."""

    def calcular(self, dados: dict) -> dict:
        """Return economia and valor_a_pagar."""
        dados = dados or {}
        base_valor = processamento.br_to_float(dados.get("energia_injetada_valor", ""))

        if base_valor <= 0:
            return {"economia": "", "valor_a_pagar": ""}

        return {
            "economia": processamento.float_to_br(0),
            "valor_a_pagar": processamento.float_to_br(base_valor),
        }
