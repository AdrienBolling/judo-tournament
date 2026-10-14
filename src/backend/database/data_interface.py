"""ABC for all data interfaces."""

from abc import ABC, abstractmethod


class DataInterface(ABC):
    """Abstract base class for all data interfaces.

    All data interfaces must implement this interface to ensure consistency across different database implementations.
    """

    # Technically base API

    @abstractmethod
    def get_data(self, query: str) -> dict:
        """Get data from the database based on the query."""
        ...

    @abstractmethod
    def save_data(self, data: dict) -> None:
        """Save data to the database."""
        ...

    # --- Judo-specific API