"""Parser base class for extracting normalized bill data."""


class BaseParser:
    """Base parser with an extraction interface."""

    def extract(self, text: str) -> dict:
        """Extract normalized energy bill data."""
        raise NotImplementedError
