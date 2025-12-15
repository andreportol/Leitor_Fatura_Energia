"""Serviço de orquestração do processamento de faturas por concessionária."""

from typing import Any, Dict

from app.core.detectors.service import detect_concessionaria
from app.core.models import Cliente
from app.core.services import processamento_cpfl, processamento_enel, processamento_energisa


def processar_fatura(pdf_file: Any, cliente: Cliente) -> Dict[str, Any]:
    """
    Orquestra detecção da concessionária e delega para o módulo específico.
    - Energisa: mantém o pipeline completo em processamento_energisa.py (regex + IA).
    - ENEL/CPFL: usam parsers dedicados e política de cálculo.
    """
    from app.core.services import processamento_energisa as processamento  # import local para evitar dependência circular

    texto = processamento.extrair_texto(pdf_file)
    concessionaria = detect_concessionaria(texto)

    processadores = {
        "ENERGISA": processamento_energisa.processar,
        "ENEL": processamento_enel.processar,
        "CPFL": processamento_cpfl.processar,
    }
    processar = processadores.get(concessionaria, processamento_energisa.processar)
    contexto = processar(pdf_file, cliente, texto=texto) or {}
    contexto.setdefault("concessionaria", concessionaria)
    return contexto
