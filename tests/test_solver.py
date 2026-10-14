"""Tests for backend.solver.ga_solver — scoring functions, GA operators, end-to-end."""

import uuid
from datetime import date

import numpy as np
import pytest

from backend.database.models import Member, members_to_df
from backend.solver.ga_solver import GAConfig, GAGroupSolver


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_config(**overrides) -> GAConfig:
    defaults = dict(
        max_group_size=4,
        max_additional_groups=2,
        small_swaps=2,
        big_swaps=1,
        population_size=20,
        generations=10,
        mutation_rate=0.3,
        scores_weights={
            "gender": 1.0,
            "weight": 1.0,
            "club": 1.0,
            "group_size": 0.5,
            "nb_groups": 0.5,
        },
    )
    defaults.update(overrides)
    return GAConfig(**defaults)


def _make_members(n: int, clubs: int = 2) -> list[Member]:
    """Create *n* members spread across *clubs* clubs."""
    club_ids = [uuid.uuid4() for _ in range(clubs)]
    members = []
    for i in range(n):
        members.append(
            Member(
                first_name=f"First{i}",
                last_name=f"Last{i}",
                date_of_birth=date(2000, 1, 1),
                weight=60.0 + i * 2.0,
                gender="M" if i % 2 == 0 else "F",
                club_id=club_ids[i % clubs],
            )
        )
    return members


def _solver(**config_overrides) -> GAGroupSolver:
    return GAGroupSolver(_default_config(**config_overrides))


# ---------------------------------------------------------------------------
# Repair
# ---------------------------------------------------------------------------

class TestRepair:
    def test_merges_single_person_groups(self):
        solver = _solver()
        # 5 participants, each in their own group → singles everywhere
        chrom = np.array([0, 1, 2, 3, 4])
        repaired = solver._repair(chrom)
        _, counts = np.unique(repaired, return_counts=True)
        assert all(c >= 2 for c in counts)

    def test_noop_on_valid_chromosome(self):
        solver = _solver()
        chrom = np.array([0, 0, 1, 1, 2, 2])
        repaired = solver._repair(chrom)
        np.testing.assert_array_equal(repaired, chrom)

    def test_single_participant(self):
        solver = _solver()
        chrom = np.array([0])
        repaired = solver._repair(chrom)
        assert len(repaired) == 1


# ---------------------------------------------------------------------------
# Swap operators
# ---------------------------------------------------------------------------

class TestSwap:
    def test_small_swap_preserves_counts(self):
        solver = _solver()
        chrom = np.array([0, 0, 0, 1, 1, 2, 2, 2])
        swapped = solver._swap(chrom, "small")
        assert sorted(swapped) == sorted(chrom)

    def test_small_swap_changes_something(self):
        """With 8 elements across 3 groups a swap *usually* changes the array.
        Run a few times to be safe against the rare identity-swap."""
        solver = _solver()
        chrom = np.array([0, 0, 0, 1, 1, 2, 2, 2])
        changed = any(
            not np.array_equal(solver._swap(chrom, "small"), chrom)
            for _ in range(20)
        )
        assert changed

    def test_big_swap_requires_3_groups(self):
        solver = _solver()
        chrom = np.array([0, 0, 1, 1])
        result = solver._swap(chrom, "big")
        np.testing.assert_array_equal(result, chrom)

    def test_big_swap_preserves_counts(self):
        solver = _solver()
        chrom = np.array([0, 0, 1, 1, 2, 2])
        swapped = solver._swap(chrom, "big")
        assert sorted(swapped) == sorted(chrom)

    def test_invalid_swap_type(self):
        solver = _solver()
        with pytest.raises(ValueError, match="Invalid swap type"):
            solver._swap(np.array([0, 1]), "unknown")


# ---------------------------------------------------------------------------
# Crossover
# ---------------------------------------------------------------------------

class TestCrossover:
    def test_child_length(self):
        solver = _solver()
        p1 = np.array([0, 0, 1, 1])
        p2 = np.array([1, 1, 0, 0])
        child = solver._crossover(p1, p2)
        assert len(child) == 4

    def test_child_values_from_parents(self):
        solver = _solver()
        p1 = np.zeros(100, dtype=int)
        p2 = np.ones(100, dtype=int)
        child = solver._crossover(p1, p2)
        assert set(child).issubset({0, 1})


# ---------------------------------------------------------------------------
# Chromosome creation
# ---------------------------------------------------------------------------

class TestChromosomeCreation:
    def test_random_chromosome_size_and_range(self):
        solver = _solver()
        chrom = solver._create_random_chromosome(10, 3)
        assert len(chrom) == 10
        assert all(0 <= g < 3 for g in chrom)

    def test_opt_chromosome_round_robin(self):
        solver = _solver()
        members = _make_members(9, clubs=1)
        df = members_to_df(members)
        chrom = solver._create_opt_initial_chromosome(df, "weight", 3)
        assert len(chrom) == 9
        _, counts = np.unique(chrom, return_counts=True)
        assert list(counts) == [3, 3, 3]

    def test_opt_chromosome_invalid_heuristic(self):
        solver = _solver()
        members = _make_members(6)
        df = members_to_df(members)
        with pytest.raises(ValueError, match="Invalid heuristic"):
            solver._create_opt_initial_chromosome(df, "invalid", 2)


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

class TestScoring:
    def test_gender_score_all_same(self):
        """All-male groups → perfect gender score (1.0)."""
        solver = _solver()
        members = _make_members(6, clubs=1)
        for m in members:
            m.gender = "M"
        df = members_to_df(members)
        assignments = np.array([0, 0, 0, 1, 1, 1])
        assert solver._gender_score(df, assignments) == pytest.approx(1.0)

    def test_weight_score_identical_weights(self):
        """Identical weights → perfect score (1.0)."""
        solver = _solver()
        members = _make_members(6, clubs=1)
        for m in members:
            m.weight = 70.0
        df = members_to_df(members)
        assignments = np.array([0, 0, 0, 1, 1, 1])
        assert solver._weight_score(df, assignments) == pytest.approx(1.0)

    def test_weight_score_within_15pct_tolerance(self):
        """A spread under 15% of the lightest member incurs no penalty."""
        solver = _solver()
        members = _make_members(2, clubs=1)
        members[0].weight = 100.0
        members[1].weight = 114.0  # 14% heavier → within tolerance
        df = members_to_df(members)
        assignments = np.array([0, 0])
        assert solver._weight_score(df, assignments) == pytest.approx(1.0)

    def test_weight_score_penalised_above_15pct(self):
        """A spread above 15% is penalised — score well below 1.0."""
        solver = _solver()
        members = _make_members(2, clubs=1)
        members[0].weight = 100.0
        members[1].weight = 130.0  # 30% heavier → 15% excess
        df = members_to_df(members)
        assignments = np.array([0, 0])
        score = solver._weight_score(df, assignments)
        # exp(-8 * 0.15) ≈ 0.30
        assert score == pytest.approx(0.301, abs=0.01)
        assert score < 0.4

    def test_nb_groups_penalty(self):
        """Too many groups → hard penalty."""
        solver = _solver(max_group_size=4, max_additional_groups=1)
        members = _make_members(8, clubs=1)
        df = members_to_df(members)
        # 8 participants / 4 max = 2 expected, +1 allowed = 3 max
        # Assign to 5 groups → exceeds limit
        assignments = np.array([0, 1, 2, 3, 4, 0, 1, 2])
        assert solver._nb_groups_score(df, assignments) == -1000

    def test_nb_groups_within_range(self):
        """Groups within allowed range → positive score."""
        solver = _solver(max_group_size=4, max_additional_groups=2)
        members = _make_members(8, clubs=1)
        df = members_to_df(members)
        assignments = np.array([0, 0, 0, 0, 1, 1, 1, 1])
        score = solver._nb_groups_score(df, assignments)
        assert score > 0

    def test_group_size_score_balanced(self):
        """Perfectly balanced groups → no std penalty."""
        solver = _solver(max_group_size=3)
        members = _make_members(6, clubs=1)
        df = members_to_df(members)
        assignments = np.array([0, 0, 0, 1, 1, 1])
        score = solver._group_size_score(df, assignments)
        # mean=3, std=0 → 3/3 = 1.0
        assert score == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# End-to-end solve
# ---------------------------------------------------------------------------

class TestSolveEndToEnd:
    def test_all_members_assigned(self):
        members = _make_members(12, clubs=3)
        solver = _solver(
            max_group_size=4,
            max_additional_groups=2,
            population_size=30,
            generations=20,
        )
        result = solver.solve(members)
        assigned = [m for pool in result.values() for m in pool]
        assert len(assigned) == 12

    def test_no_empty_pools(self):
        members = _make_members(10, clubs=2)
        solver = _solver(population_size=30, generations=20)
        result = solver.solve(members)
        assert all(len(pool) >= 2 for pool in result.values())

    def test_pool_names_sequential(self):
        members = _make_members(8, clubs=2)
        solver = _solver(population_size=20, generations=10)
        result = solver.solve(members)
        for i, name in enumerate(result.keys()):
            assert name == f"Pool {i + 1}"

    def test_deterministic_with_seed(self):
        """Same RNG seed → same result."""
        members = _make_members(12, clubs=3)
        config = _default_config(population_size=30, generations=20)

        solver1 = GAGroupSolver(config)
        solver1._rng = np.random.default_rng(42)
        r1 = solver1.solve(members)

        solver2 = GAGroupSolver(config)
        solver2._rng = np.random.default_rng(42)
        r2 = solver2.solve(members)

        for key in r1:
            assert [m.first_name for m in r1[key]] == [m.first_name for m in r2[key]]
