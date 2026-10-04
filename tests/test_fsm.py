"""Tests for Procore FSM formal lifecycle verifier and safety invariants."""

import pytest

import procore_mcp
from procore_mcp.fsm import (
    ChangeEventLifecycle,
    CommitmentLifecycle,
    InvalidStateTransitionError,
    RFILifecycle,
    SubmittalLifecycle,
    compute_reachable_states,
    validate_transition,
    verify_zero_terminal_reachability,
)
from procore_mcp.safety import FORBIDDEN_MUTATION_STATUSES, SafetyInvariantViolation

# =============================================================================
# 1. State Models for Construction Entities
# =============================================================================


class TestFSMStateModels:
    """Test FSM state models and enum members for Procore construction entities."""

    def test_rfi_lifecycle_states(self) -> None:
        """RFI lifecycle states must match Draft, Open, Pending, Issued, Closed."""
        expected = {"draft", "open", "pending", "issued", "closed"}
        actual = {state.value for state in RFILifecycle}
        assert actual == expected
        assert RFILifecycle.DRAFT.value == "draft"
        assert RFILifecycle.OPEN.value == "open"
        assert RFILifecycle.PENDING.value == "pending"
        assert RFILifecycle.ISSUED.value == "issued"
        assert RFILifecycle.CLOSED.value == "closed"

    def test_commitment_lifecycle_states(self) -> None:
        """Commitment lifecycle states must match Draft, Out For Bid,
        Pending Review, Approved, Executed, Closed.
        """
        expected = {
            "draft",
            "out_for_bid",
            "pending_review",
            "approved",
            "executed",
            "closed",
        }
        actual = {state.value for state in CommitmentLifecycle}
        assert actual == expected
        assert CommitmentLifecycle.DRAFT.value == "draft"
        assert CommitmentLifecycle.OUT_FOR_BID.value == "out_for_bid"
        assert CommitmentLifecycle.PENDING_REVIEW.value == "pending_review"
        assert CommitmentLifecycle.APPROVED.value == "approved"
        assert CommitmentLifecycle.EXECUTED.value == "executed"
        assert CommitmentLifecycle.CLOSED.value == "closed"

    def test_change_event_lifecycle_states(self) -> None:
        """Change Event lifecycle states must match Draft, Under Review,
        Approved, Rejected, Void.
        """
        expected = {"draft", "under_review", "approved", "rejected", "void"}
        actual = {state.value for state in ChangeEventLifecycle}
        assert actual == expected
        assert ChangeEventLifecycle.DRAFT.value == "draft"
        assert ChangeEventLifecycle.UNDER_REVIEW.value == "under_review"
        assert ChangeEventLifecycle.APPROVED.value == "approved"
        assert ChangeEventLifecycle.REJECTED.value == "rejected"
        assert ChangeEventLifecycle.VOID.value == "void"

    def test_submittal_lifecycle_states(self) -> None:
        """Submittal lifecycle states must match Draft, Open, Pending, Approved, Closed."""
        expected = {"draft", "open", "pending", "approved", "closed"}
        actual = {state.value for state in SubmittalLifecycle}
        assert actual == expected
        assert SubmittalLifecycle.DRAFT.value == "draft"
        assert SubmittalLifecycle.OPEN.value == "open"
        assert SubmittalLifecycle.PENDING.value == "pending"
        assert SubmittalLifecycle.APPROVED.value == "approved"
        assert SubmittalLifecycle.CLOSED.value == "closed"


# =============================================================================
# 2. Transition Validation
# =============================================================================


class TestTransitionValidation:
    """Test validate_transition enforcement of Procore rules and MCP invariants."""

    @pytest.mark.parametrize(
        ("entity", "from_state", "to_state"),
        [
            ("rfi", "draft", "open"),
            ("rfi", "draft", "pending"),
            ("rfi", "open", "pending"),
            ("rfi", "pending", "open"),
            ("commitment", "draft", "out_for_bid"),
            ("commitment", "draft", "pending_review"),
            ("commitment", "out_for_bid", "pending_review"),
            ("commitment", "out_for_bid", "draft"),
            ("commitment", "pending_review", "draft"),
            ("commitment", "pending_review", "out_for_bid"),
            ("change_event", "draft", "under_review"),
            ("change_event", "under_review", "draft"),
            ("change_event", "under_review", "rejected"),
            ("change_event", "rejected", "draft"),
            ("submittal", "draft", "open"),
            ("submittal", "draft", "pending"),
            ("submittal", "open", "pending"),
            ("submittal", "pending", "open"),
        ],
    )
    def test_legal_safe_transitions_pass_under_mcp(
        self, entity: str, from_state: str, to_state: str
    ) -> None:
        """Legal, non-terminal transitions pass cleanly when is_mcp=True."""
        validate_transition(entity, from_state, to_state, is_mcp=True)

    @pytest.mark.parametrize(
        ("entity", "from_state", "to_state"),
        [
            # RFI terminal states: issued, closed
            ("rfi", "open", "issued"),
            ("rfi", "pending", "issued"),
            ("rfi", "open", "closed"),
            ("rfi", "pending", "closed"),
            ("rfi", "draft", "closed"),
            # Commitment terminal states: approved, executed, closed
            ("commitment", "pending_review", "approved"),
            ("commitment", "approved", "executed"),
            ("commitment", "approved", "closed"),
            ("commitment", "executed", "closed"),
            ("commitment", "draft", "closed"),
            # Change Event terminal state in forbidden set: approved
            ("change_event", "under_review", "approved"),
            # Submittal terminal states: approved, closed
            ("submittal", "open", "approved"),
            ("submittal", "pending", "approved"),
            ("submittal", "open", "closed"),
            ("submittal", "approved", "closed"),
            ("submittal", "draft", "closed"),
        ],
    )
    def test_mcp_blocks_terminal_authoritative_transitions(
        self, entity: str, from_state: str, to_state: str
    ) -> None:
        """is_mcp=True raises SafetyInvariantViolation on transitions to
        forbidden terminal states.
        """
        with pytest.raises(SafetyInvariantViolation) as exc_info:
            validate_transition(entity, from_state, to_state, is_mcp=True)

        assert (
            "terminal" in str(exc_info.value).lower()
            or "forbidden" in str(exc_info.value).lower()
            or "authoritative" in str(exc_info.value).lower()
        )

    @pytest.mark.parametrize(
        ("entity", "from_state", "to_state"),
        [
            ("rfi", "open", "issued"),
            ("rfi", "open", "closed"),
            ("commitment", "pending_review", "approved"),
            ("commitment", "approved", "executed"),
            ("change_event", "under_review", "approved"),
            ("submittal", "open", "approved"),
            ("submittal", "open", "closed"),
        ],
    )
    def test_non_mcp_allows_authoritative_transitions(
        self, entity: str, from_state: str, to_state: str
    ) -> None:
        """When is_mcp=False (human/Procore direct UI), valid authoritative transitions pass."""
        validate_transition(entity, from_state, to_state, is_mcp=False)

    @pytest.mark.parametrize(
        ("entity", "from_state", "to_state"),
        [
            # Closed -> Draft is illegal in Procore
            ("rfi", "closed", "draft"),
            ("rfi", "closed", "open"),
            ("commitment", "closed", "draft"),
            ("commitment", "closed", "approved"),
            ("submittal", "closed", "draft"),
            # Executed -> Draft is illegal
            ("commitment", "executed", "draft"),
            # Void -> Draft / Under Review is illegal
            ("change_event", "void", "draft"),
            ("change_event", "void", "under_review"),
            # Invalid cross-state jumps
            ("rfi", "draft", "issued"),
            ("commitment", "draft", "executed"),
            ("change_event", "draft", "approved"),
        ],
    )
    def test_illegal_procore_transitions_raise_error(
        self, entity: str, from_state: str, to_state: str
    ) -> None:
        """Illegal Procore transitions raise InvalidStateTransitionError regardless of is_mcp."""
        with pytest.raises(InvalidStateTransitionError):
            validate_transition(entity, from_state, to_state, is_mcp=True)

        with pytest.raises(InvalidStateTransitionError):
            validate_transition(entity, from_state, to_state, is_mcp=False)

    def test_unknown_entity_raises_value_error(self) -> None:
        """Unknown entity type raises ValueError."""
        with pytest.raises(ValueError, match=r"Unknown entity"):
            validate_transition("spaceship", "draft", "open")

    def test_unknown_state_raises_invalid_transition(self) -> None:
        """Unknown state raises InvalidStateTransitionError."""
        with pytest.raises(InvalidStateTransitionError):
            validate_transition("rfi", "draft", "nonexistent_status")

        with pytest.raises(InvalidStateTransitionError):
            validate_transition("rfi", "nonexistent_status", "open")

    def test_case_and_string_normalization_resilience(self) -> None:
        """Status strings should be resilient to casing, whitespace, and formatting."""
        validate_transition("RFI", "Draft", "Open", is_mcp=True)
        validate_transition("Commitment", "  draft  ", "Pending Review", is_mcp=True)
        validate_transition("Commitment", "Draft", "out for bid", is_mcp=True)
        validate_transition("Commitment", "Draft", "OUT_FOR_BID", is_mcp=True)
        validate_transition("Change_Event", "draft", "Under Review", is_mcp=True)

        with pytest.raises(SafetyInvariantViolation):
            validate_transition("RFI", "Open", "ISSUED", is_mcp=True)

        with pytest.raises(SafetyInvariantViolation):
            validate_transition("Commitment", "Pending Review", "Approved", is_mcp=True)


# =============================================================================
# 3. Mathematical Reachability Theorem
# =============================================================================


class TestMathematicalReachabilityTheorem:
    """Formal verification: prove 0 terminal reachability through MCP."""

    @pytest.mark.parametrize(
        "entity",
        ["rfi", "commitment", "change_event", "submittal"],
    )
    def test_reachability_theorem_zero_terminal_reachability(self, entity: str) -> None:
        """Theorem: For every construction entity, MCP reachable states from draft
        have an empty intersection with FORBIDDEN_MUTATION_STATUSES.

        ∀ e ∈ Entities: Reachable(e, start=draft, is_mcp=True) ∩ Forbidden = ∅
        """
        reachable = compute_reachable_states(entity, start_state="draft", is_mcp=True)
        assert isinstance(reachable, set)
        assert len(reachable) > 0
        assert "draft" in reachable

        # Mathematical reachability invariant
        forbidden_intersection = reachable & FORBIDDEN_MUTATION_STATUSES
        assert forbidden_intersection == set(), (
            f"Entity '{entity}' violated zero terminal reachability: found {forbidden_intersection}"
        )

        # Explicit terminal states check
        assert "issued" not in reachable
        assert "approved" not in reachable
        assert "executed" not in reachable
        assert "closed" not in reachable

    @pytest.mark.parametrize(
        "entity",
        ["rfi", "commitment", "change_event", "submittal"],
    )
    def test_non_mcp_reachability_reaches_terminal_states(self, entity: str) -> None:
        """Under human/direct Procore authority (is_mcp=False), terminal states ARE reachable.
        This verifies that the FSM lifecycle graph is complete and connected.
        """
        reachable_procore = compute_reachable_states(entity, start_state="draft", is_mcp=False)
        assert len(reachable_procore & FORBIDDEN_MUTATION_STATUSES) > 0, (
            f"Entity '{entity}' with is_mcp=False should be able to reach "
            "authoritative terminal states."
        )

    @pytest.mark.parametrize(
        "entity",
        ["rfi", "commitment", "change_event", "submittal"],
    )
    def test_formal_verification_helper_function(self, entity: str) -> None:
        """The verify_zero_terminal_reachability function returns True for all entities."""
        assert verify_zero_terminal_reachability(entity, start_state="draft") is True

    def test_package_exports(self) -> None:
        """All FSM symbols must be exported from package root."""
        assert hasattr(procore_mcp, "RFILifecycle")
        assert hasattr(procore_mcp, "CommitmentLifecycle")
        assert hasattr(procore_mcp, "ChangeEventLifecycle")
        assert hasattr(procore_mcp, "SubmittalLifecycle")
        assert hasattr(procore_mcp, "InvalidStateTransitionError")
        assert hasattr(procore_mcp, "validate_transition")
        assert hasattr(procore_mcp, "compute_reachable_states")
        assert hasattr(procore_mcp, "verify_zero_terminal_reachability")
