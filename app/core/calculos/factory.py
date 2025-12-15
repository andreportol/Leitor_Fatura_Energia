"""Factory for calculation policies."""

from .padrao import PoliticaPadrao
from .vip import PoliticaVIP


def get_politica(nome: str):
    """Return a calculation policy instance by name."""
    if isinstance(nome, str) and nome.strip().upper() == "VIP":
        return PoliticaVIP()
    return PoliticaPadrao()
