"""Base classes for calculation policies."""


class PoliticaCalculo:
    """Interface for calculation policies."""

    def calcular(self, dados: dict) -> dict:
        """Return economia and valor_a_pagar."""
        raise NotImplementedError
