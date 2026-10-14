"""GA-based solver for the Judo Tournament group creation problem."""

import numpy as np
import pandas as pd
from pydantic import BaseModel

from backend.database.models import Member, members_to_df

from .solver import GroupSolver

_MIN_GROUPS_FOR_BIG_SWAP = 3

# Weight homogeneity: spread is judged relative to the lightest member of a
# group. Up to ``_WEIGHT_REL_TOLERANCE`` is free; beyond it the score decays
# at ``_WEIGHT_PENALTY_RATE`` — the larger the rate, the harsher the penalty.
_WEIGHT_REL_TOLERANCE = 0.15  # 15% spread allowed before any penalty
_WEIGHT_PENALTY_RATE = 8.0

_HEURISTIC_COLUMNS: dict[str, str] = {
    "gender": "gender",
    "weight": "weight",
    "club": "club_id",
}


class GAConfig(BaseModel):
    """Configuration for the GA-based solver."""

    max_group_size: int
    max_additional_groups: int
    small_swaps: int
    big_swaps: int
    population_size: int
    generations: int
    mutation_rate: float
    scores_weights: dict[str, float]


class GAGroupSolver(GroupSolver):
    """GA-based solver for the Judo Tournament group creation problem.

    Represents group assignments as a chromosome: an integer array where
    ``chromosome[i]`` is the group index assigned to participant *i*.
    """

    def __init__(self, config: GAConfig) -> None:
        """Initialise solver from a ``GAConfig``."""
        self.config = config
        self.max_group_size = config.max_group_size
        self.max_additional_groups = config.max_additional_groups
        self.small_swaps = config.small_swaps
        self.big_swaps = config.big_swaps
        self.population_size = config.population_size
        self.generations = config.generations
        self.mutation_rate = config.mutation_rate
        self.scores_weights = config.scores_weights
        self._rng = np.random.default_rng()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def solve(self, members_list: list[Member]) -> dict[str, list[Member]]:
        """Solve the group creation problem for a given list of members."""
        members_df = members_to_df(members_list)
        nb_participants = len(members_df)
        min_nb_groups = max(1, int(np.ceil(nb_participants / self.max_group_size)))
        max_nb_groups = min_nb_groups + self.max_additional_groups

        population = self._init_population(members_df, nb_participants, min_nb_groups, max_nb_groups)
        fitness_scores = np.array([self._fitness(members_df, c) for c in population])

        for _ in range(self.generations):
            population, fitness_scores = self._evolve(population, fitness_scores, members_df)

        return self._extract_result(population, fitness_scores, members_list)

    # ------------------------------------------------------------------
    # Evolution helpers (keep *solve* concise)
    # ------------------------------------------------------------------

    def _init_population(
        self,
        members_df: pd.DataFrame,
        nb_participants: int,
        min_nb_groups: int,
        max_nb_groups: int,
    ) -> list[np.ndarray]:
        """Build the initial population from heuristic + random seeds."""
        population: list[np.ndarray] = []

        for heuristic in _HEURISTIC_COLUMNS:
            for nb_groups in range(min_nb_groups, max_nb_groups + 1):
                chrom = self._create_opt_initial_chromosome(members_df, heuristic, nb_groups)
                population.append(self._repair(chrom))

        while len(population) < self.population_size:
            nb_groups = self._rng.integers(min_nb_groups, max_nb_groups + 1)
            chrom = self._create_random_chromosome(nb_participants, int(nb_groups))
            population.append(self._repair(chrom))

        return population[: self.population_size]

    def _evolve(
        self,
        population: list[np.ndarray],
        fitness_scores: np.ndarray,
        members_df: pd.DataFrame,
    ) -> tuple[list[np.ndarray], np.ndarray]:
        """Run one generation: elitism → selection → crossover → mutation."""
        elite_count = max(1, self.population_size // 10)
        elite_indices = np.argsort(fitness_scores)[-elite_count:]
        new_population = [population[i] for i in elite_indices]

        while len(new_population) < self.population_size:
            parent1 = self._tournament_select(population, fitness_scores)
            parent2 = self._tournament_select(population, fitness_scores)
            child = self._crossover(parent1, parent2)

            if self._rng.random() < self.mutation_rate:
                child = self._mutate(child)

            new_population.append(self._repair(child))

        new_fitness = np.array([self._fitness(members_df, c) for c in new_population])
        return new_population, new_fitness

    def _mutate(self, chromosome: np.ndarray) -> np.ndarray:
        """Apply configured small and big swap mutations."""
        for _ in range(self.small_swaps):
            chromosome = self._swap(chromosome, "small")
        if len(np.unique(chromosome)) >= _MIN_GROUPS_FOR_BIG_SWAP:
            for _ in range(self.big_swaps):
                chromosome = self._swap(chromosome, "big")
        return chromosome

    def _extract_result(
        self,
        population: list[np.ndarray],
        fitness_scores: np.ndarray,
        members_list: list[Member],
    ) -> dict[str, list[Member]]:
        """Convert the best chromosome into the output dict."""
        best_chromosome = population[int(np.argmax(fitness_scores))]
        return {
            f"Pool {idx + 1}": [
                members_list[i]
                for i, g in enumerate(best_chromosome)
                if g == group_id
            ]
            for idx, group_id in enumerate(sorted(np.unique(best_chromosome)))
        }

    # ------------------------------------------------------------------
    # Scoring functions
    # ------------------------------------------------------------------

    def _fitness(self, members_df: pd.DataFrame, group_assignments: np.ndarray) -> float:
        """Weighted sum of all objective scores."""
        scores = {
            "gender": self._gender_score(members_df, group_assignments),
            "weight": self._weight_score(members_df, group_assignments),
            "club": self._club_score(members_df, group_assignments),
            "group_size": self._group_size_score(members_df, group_assignments),
            "nb_groups": self._nb_groups_score(members_df, group_assignments),
        }
        return sum(self.scores_weights[k] * v for k, v in scores.items())

    def _gender_score(self, members_df: pd.DataFrame, group_assignments: np.ndarray) -> float:
        """Average majority-gender proportion of the 3 worst groups.

        Higher -> more gender-homogeneous groups.
        """
        gender_counts = members_df["gender"].groupby(group_assignments).value_counts()
        groups = gender_counts.index.get_level_values(0).unique()
        group_scores = [
            gender_counts[g].max() / gender_counts[g].sum() for g in groups
        ]
        return sum(sorted(group_scores)[:3]) / min(3, len(group_scores))

    def _club_score(self, members_df: pd.DataFrame, group_assignments: np.ndarray) -> float:
        """Gaussian reward centred on ideal club diversity.

        Higher -> clubs are more evenly spread across groups.
        """
        club_counts = members_df["club_id"].groupby(group_assignments).value_counts()
        groups = club_counts.index.get_level_values(0).unique()
        group_scores = [
            (club_counts[g] / club_counts[g].sum()).mean() for g in groups
        ]
        avg = np.mean(group_scores)
        expected_avg = 1 / members_df["club_id"].nunique()
        score = np.exp(-((avg - expected_avg) ** 2) / (2 * 0.1**2))
        return float(score)

    def _weight_score(self, members_df: pd.DataFrame, group_assignments: np.ndarray) -> float:
        """Average within-group weight homogeneity.

        Weight closeness is judged *relatively*: the spread between a group's
        lightest and heaviest member is expressed as a fraction of the lightest
        member's weight. A spread up to ``_WEIGHT_REL_TOLERANCE`` (15%) is
        tolerated with no penalty; beyond that the score decays exponentially
        at ``_WEIGHT_PENALTY_RATE``, so groups mixing very different weights are
        penalised hard. The final score is the mean across all groups.
        """
        grouped = members_df["weight"].groupby(group_assignments)
        group_scores = []
        for group in grouped.groups:
            weights = grouped.get_group(group)
            if len(weights) <= 1:
                group_scores.append(1.0)
                continue
            lightest = weights.min()
            spread = weights.max() - lightest
            rel_spread = spread / lightest if lightest > 0 else 0.0
            excess = max(0.0, rel_spread - _WEIGHT_REL_TOLERANCE)
            group_scores.append(float(np.exp(-_WEIGHT_PENALTY_RATE * excess)))
        return float(np.mean(group_scores))

    def _group_size_score(self, members_df: pd.DataFrame, group_assignments: np.ndarray) -> float:
        """Reward balanced groups that lean towards *max_group_size*."""
        grouped = members_df.groupby(group_assignments)
        sizes = [len(grouped.get_group(g)) for g in grouped.groups]
        return float((np.mean(sizes) - np.std(sizes)) / self.max_group_size)

    def _nb_groups_score(self, members_df: pd.DataFrame, group_assignments: np.ndarray) -> float:
        """Prefer fewer groups; hard-penalise exceeding the allowed range."""
        nb_groups = len(np.unique(group_assignments))
        expected_nb_groups = len(members_df) / self.max_group_size
        if nb_groups > expected_nb_groups + self.max_additional_groups:
            return -1000
        # Guard against max_additional_groups == 0 (an allowed config value).
        slack = max(1, self.max_additional_groups)
        return float(1 - (nb_groups - expected_nb_groups) / slack)

    # ------------------------------------------------------------------
    # GA operators
    # ------------------------------------------------------------------

    def _create_random_chromosome(self, nb_participants: int, nb_groups: int) -> np.ndarray:
        """Random group assignment."""
        return self._rng.integers(0, nb_groups, size=nb_participants)

    def _create_opt_initial_chromosome(
        self, members_df: pd.DataFrame, heuristic: str, nb_groups: int
    ) -> np.ndarray:
        """Round-robin assignment after sorting by *heuristic* column."""
        if heuristic not in _HEURISTIC_COLUMNS:
            msg = f"Invalid heuristic: {heuristic}"
            raise ValueError(msg)

        sorted_df = members_df.sort_values(_HEURISTIC_COLUMNS[heuristic])
        chromosome = np.zeros(len(members_df), dtype=int)
        for i in range(len(members_df)):
            chromosome[sorted_df.index[i]] = i % nb_groups
        return chromosome

    def _tournament_select(
        self, population: list[np.ndarray], fitness_scores: np.ndarray, k: int = 3
    ) -> np.ndarray:
        """Tournament selection: pick *k* random individuals, return the fittest."""
        k = min(k, len(population))
        indices = self._rng.choice(len(population), size=k, replace=False)
        best = indices[np.argmax(fitness_scores[indices])]
        return population[best]

    def _crossover(self, parent1: np.ndarray, parent2: np.ndarray) -> np.ndarray:
        """Uniform crossover: each gene randomly inherited from one parent."""
        mask = self._rng.integers(0, 2, size=len(parent1), dtype=bool)
        return np.where(mask, parent1, parent2)

    def _swap(self, chromosome: np.ndarray, swap_type: str) -> np.ndarray:
        """Mutation operator: swap participants between groups.

        ``"small"``: swap two random participants.
        ``"big"``:   rotate three participants across three distinct groups.
        """
        new = chromosome.copy()
        if swap_type == "small":
            i, j = self._rng.choice(len(new), size=2, replace=False)
            new[i], new[j] = new[j], new[i]
        elif swap_type == "big":
            unique_groups = np.unique(new)
            if len(unique_groups) < _MIN_GROUPS_FOR_BIG_SWAP:
                return new
            g1, g2, g3 = self._rng.choice(unique_groups, size=3, replace=False)
            i = self._rng.choice(np.where(chromosome == g1)[0])
            j = self._rng.choice(np.where(chromosome == g2)[0])
            k = self._rng.choice(np.where(chromosome == g3)[0])
            new[i], new[j], new[k] = new[j], new[k], new[i]
        else:
            msg = f"Invalid swap type: {swap_type}"
            raise ValueError(msg)
        return new

    def _repair(self, chromosome: np.ndarray) -> np.ndarray:
        """Enforce max group size and merge single-person groups."""
        chromosome = chromosome.copy()

        # Phase 1: split oversized groups
        while True:
            unique, counts = np.unique(chromosome, return_counts=True)
            oversized = unique[counts > self.max_group_size]
            if len(oversized) == 0:
                break
            for gid in oversized:
                indices = np.where(chromosome == gid)[0]
                excess = len(indices) - self.max_group_size
                new_gid = chromosome.max() + 1
                to_move = self._rng.choice(indices, size=excess, replace=False)
                chromosome[to_move] = new_gid

        # Phase 2: merge single-person groups (without violating max)
        while True:
            unique, counts = np.unique(chromosome, return_counts=True)
            singles = unique[counts == 1]
            if len(singles) == 0:
                break
            merged = False
            for sg in singles:
                other_mask = unique != sg
                other_counts = counts[other_mask]
                eligible_mask = other_counts < self.max_group_size
                if not eligible_mask.any():
                    continue
                eligible = unique[other_mask][eligible_mask]
                target = eligible[np.argmin(other_counts[eligible_mask])]
                chromosome[np.where(chromosome == sg)[0][0]] = target
                merged = True
                break
            if not merged:
                break

        return chromosome
