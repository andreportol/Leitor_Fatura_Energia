"""Processamento específico para faturas da CPFL."""

from typing import Any, Dict

from app.core.services import processamento_energisa as processamento
from app.core.calculos.padrao import PoliticaPadrao
from app.core.models import Cliente
from app.core.parsers.cpfl import CPFLParser


def processar(pdf_file: Any, cliente: Cliente, texto: str | None = None) -> Dict[str, Any]:
    """
    Processa a fatura CPFL usando o parser dedicado e aplica a política de cálculo do cliente.
    """
    texto = texto or processamento.extrair_texto(pdf_file)
    dados = CPFLParser().extract(texto) or {}

    calculado = PoliticaPadrao().calcular(dados) or {}

    template_fatura = getattr(cliente, "template_fatura", "") or "energisa_padrao.html"
    return {
        "cliente": cliente,
        "concessionaria": "CPFL",
        "dados": {**dados, **calculado},
        "template_fatura": template_fatura,
        "texto": texto,
    }
