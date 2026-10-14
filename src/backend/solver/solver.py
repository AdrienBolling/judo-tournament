"""Base interface for group creation solvers."""

from abc import ABC, abstractmethod

from backend.database.models import Member

class GroupSolver(ABC):

    @abstractmethod
    def solve(self, members_list: list[Member]) -> dict[str, list[Member]]:
        """Solve the group creation problem for a given tournament."""
        ...
