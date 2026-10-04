"""Z3 SMT Solver formal verification test suite for Procore MCP FSM invariants.

Mathematically proves the Zero Unauthorized Commitment Invariant:
For every entity E in {rfi, commitment, change_event, submittal} and for every
reachable state sequence S_0 -> S_1 -> ... -> S_k under MCP transition constraints:
    ∀ i ∈ {0, ..., k}, S_i ∉ FORBIDDEN_MUTATION_STATUSES
"""

import pytest
import z3

from procore_mcp.formal_z3 import (
    Z3FSMModel,
    prove_all_entities_z3,
    prove_zero_terminal_reachability_z3,
)
from procore_mcp.fsm import SUPPORTED_ENTITIES
from procore_mcp.safety import FORBIDDEN_MUTATION_STATUSES


def test_z3_fsm_model_creation() -> None:
    """Test that Z3 FSM model can be initialized for each entity."""
    for entity in SUPPORTED_ENTITIES:
        model = Z3FSMModel(entity)
        assert model.entity_type == entity
        assert len(model.states) > 0
        assert model.state_sort is not None


@pytest.mark.parametrize("entity_type", SUPPORTED_ENTITIES)
def test_z3_proves_zero_terminal_reachability(entity_type: str) -> None:
    """SMT Proof: Assert that finding a reachable forbidden state via MCP is UNSAT.

    If solver.check() == unsat, it is mathematically proven that no agent tool sequence
    can reach any forbidden terminal status (issued, approved, executed, etc.).
    """
    result = prove_zero_terminal_reachability_z3(entity_type, max_depth=10)
    assert result.proven is True
    assert result.solver_status == z3.unsat
    assert result.counterexample is None


def test_z3_proves_all_supported_entities() -> None:
    """Formally prove reachability invariants across all entities in a single batch."""
    results = prove_all_entities_z3(max_depth=10)
    assert len(results) == len(SUPPORTED_ENTITIES)
    for _entity, res in results.items():
        assert res.proven is True
        assert res.solver_status == z3.unsat


def test_z3_unconstrained_system_finds_counterexample() -> None:
    """Sanity Check: Without the MCP safety barrier (is_mcp=False),

    Z3 MUST find a valid counterexample path into terminal states.
    This proves that the invariant check is non-vacuous.
    """
    model = Z3FSMModel("commitment")
    # Solve for reachable terminal states without MCP restriction
    has_counterexample, trace = model.find_path_to_forbidden(is_mcp=False, max_depth=5)
    assert has_counterexample is True
    assert trace is not None
    assert trace[-1] in FORBIDDEN_MUTATION_STATUSES


def test_z3_mcp_constrained_system_has_no_counterexample() -> None:
    """SMT Theorem: With the MCP barrier active (is_mcp=True),

    Z3 proves no path exists to any terminal state from 'draft'.
    """
    model = Z3FSMModel("commitment")
    has_counterexample, trace = model.find_path_to_forbidden(is_mcp=True, max_depth=10)
    assert has_counterexample is False
    assert trace is None


def test_z3_invalid_entity_raises() -> None:
    """Assert invalid entity type raises ValueError."""
    with pytest.raises(ValueError, match="Unknown entity type"):
        Z3FSMModel("unknown_entity_type")
