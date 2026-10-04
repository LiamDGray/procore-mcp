"""Finite State Machine (FSM) formal lifecycle verifier for Procore MCP.

Formally defines lifecycle state models, transition rules, and mathematical reachability
theorems proving that terminal/authoritative states are 100% unreachable via MCP.
"""

import re
from enum import Enum
from typing import Final

from procore_mcp.safety import (
    FORBIDDEN_MUTATION_STATUSES,
    SafetyInvariantViolation,
    normalize_status_string,
)


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal or unsupported lifecycle state transition is attempted."""


class RFILifecycle(str, Enum):
    """Lifecycle states for Procore Requests for Information (RFI)."""

    DRAFT = "draft"
    OPEN = "open"
    PENDING = "pending"
    ISSUED = "issued"
    CLOSED = "closed"


class CommitmentLifecycle(str, Enum):
    """Lifecycle states for Procore Commitments (Subcontracts and Purchase Orders)."""

    DRAFT = "draft"
    OUT_FOR_BID = "out_for_bid"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    EXECUTED = "executed"
    CLOSED = "closed"


class ChangeEventLifecycle(str, Enum):
    """Lifecycle states for Procore Change Events."""

    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    VOID = "void"


class SubmittalLifecycle(str, Enum):
    """Lifecycle states for Procore Submittals."""

    DRAFT = "draft"
    OPEN = "open"
    PENDING = "pending"
    APPROVED = "approved"
    CLOSED = "closed"


SUPPORTED_ENTITIES: Final[tuple[str, ...]] = (
    "rfi",
    "commitment",
    "change_event",
    "submittal",
)

RFI_TRANSITIONS: Final[dict[str, set[str]]] = {
    RFILifecycle.DRAFT.value: {
        RFILifecycle.OPEN.value,
        RFILifecycle.PENDING.value,
        RFILifecycle.CLOSED.value,
    },
    RFILifecycle.OPEN.value: {
        RFILifecycle.PENDING.value,
        RFILifecycle.ISSUED.value,
        RFILifecycle.CLOSED.value,
    },
    RFILifecycle.PENDING.value: {
        RFILifecycle.OPEN.value,
        RFILifecycle.ISSUED.value,
        RFILifecycle.CLOSED.value,
    },
    RFILifecycle.ISSUED.value: {
        RFILifecycle.CLOSED.value,
    },
    RFILifecycle.CLOSED.value: set(),
}

COMMITMENT_TRANSITIONS: Final[dict[str, set[str]]] = {
    CommitmentLifecycle.DRAFT.value: {
        CommitmentLifecycle.OUT_FOR_BID.value,
        CommitmentLifecycle.PENDING_REVIEW.value,
        CommitmentLifecycle.CLOSED.value,
    },
    CommitmentLifecycle.OUT_FOR_BID.value: {
        CommitmentLifecycle.DRAFT.value,
        CommitmentLifecycle.PENDING_REVIEW.value,
        CommitmentLifecycle.CLOSED.value,
    },
    CommitmentLifecycle.PENDING_REVIEW.value: {
        CommitmentLifecycle.DRAFT.value,
        CommitmentLifecycle.OUT_FOR_BID.value,
        CommitmentLifecycle.APPROVED.value,
        CommitmentLifecycle.CLOSED.value,
    },
    CommitmentLifecycle.APPROVED.value: {
        CommitmentLifecycle.EXECUTED.value,
        CommitmentLifecycle.CLOSED.value,
    },
    CommitmentLifecycle.EXECUTED.value: {
        CommitmentLifecycle.CLOSED.value,
    },
    CommitmentLifecycle.CLOSED.value: set(),
}

CHANGE_EVENT_TRANSITIONS: Final[dict[str, set[str]]] = {
    ChangeEventLifecycle.DRAFT.value: {
        ChangeEventLifecycle.UNDER_REVIEW.value,
        ChangeEventLifecycle.VOID.value,
    },
    ChangeEventLifecycle.UNDER_REVIEW.value: {
        ChangeEventLifecycle.DRAFT.value,
        ChangeEventLifecycle.APPROVED.value,
        ChangeEventLifecycle.REJECTED.value,
        ChangeEventLifecycle.VOID.value,
    },
    ChangeEventLifecycle.APPROVED.value: {
        ChangeEventLifecycle.VOID.value,
    },
    ChangeEventLifecycle.REJECTED.value: {
        ChangeEventLifecycle.DRAFT.value,
        ChangeEventLifecycle.VOID.value,
    },
    ChangeEventLifecycle.VOID.value: set(),
}

SUBMITTAL_TRANSITIONS: Final[dict[str, set[str]]] = {
    SubmittalLifecycle.DRAFT.value: {
        SubmittalLifecycle.OPEN.value,
        SubmittalLifecycle.PENDING.value,
        SubmittalLifecycle.CLOSED.value,
    },
    SubmittalLifecycle.OPEN.value: {
        SubmittalLifecycle.PENDING.value,
        SubmittalLifecycle.APPROVED.value,
        SubmittalLifecycle.CLOSED.value,
    },
    SubmittalLifecycle.PENDING.value: {
        SubmittalLifecycle.OPEN.value,
        SubmittalLifecycle.APPROVED.value,
        SubmittalLifecycle.CLOSED.value,
    },
    SubmittalLifecycle.APPROVED.value: {
        SubmittalLifecycle.CLOSED.value,
    },
    SubmittalLifecycle.CLOSED.value: set(),
}

LIFECYCLE_TRANSITIONS: Final[dict[str, dict[str, set[str]]]] = {
    "rfi": RFI_TRANSITIONS,
    "commitment": COMMITMENT_TRANSITIONS,
    "change_event": CHANGE_EVENT_TRANSITIONS,
    "submittal": SUBMITTAL_TRANSITIONS,
}

LIFECYCLE_STATES: Final[dict[str, frozenset[str]]] = {
    "rfi": frozenset(s.value for s in RFILifecycle),
    "commitment": frozenset(s.value for s in CommitmentLifecycle),
    "change_event": frozenset(s.value for s in ChangeEventLifecycle),
    "submittal": frozenset(s.value for s in SubmittalLifecycle),
}


def normalize_state(state: str | Enum) -> str:
    """Normalize state representation to lowercase canonical identifier with underscores."""
    val = state.value if isinstance(state, Enum) else str(state)
    normalized = normalize_status_string(val)
    return re.sub(r"[\s\-]+", "_", normalized)


def _resolve_entity_type(entity_type: str) -> str:
    """Resolve an entity type string to its canonical registered name."""
    norm = normalize_status_string(entity_type)
    norm = re.sub(r"[\s\-]+", "_", norm)

    mapping: dict[str, str] = {
        "rfi": "rfi",
        "rfis": "rfi",
        "rfilifecycle": "rfi",
        "commitment": "commitment",
        "commitments": "commitment",
        "commitmentlifecycle": "commitment",
        "change_event": "change_event",
        "change_events": "change_event",
        "changeevent": "change_event",
        "changeeventlifecycle": "change_event",
        "submittal": "submittal",
        "submittals": "submittal",
        "submittallifecycle": "submittal",
    }
    canonical = mapping.get(norm)
    if canonical is None:
        supported = ", ".join(f"'{e}'" for e in SUPPORTED_ENTITIES)
        raise ValueError(f"Unknown entity type: '{entity_type}'. Supported entities: {supported}.")
    return canonical


def validate_transition(
    entity_type: str,
    from_state: str | Enum,
    to_state: str | Enum,
    is_mcp: bool = True,
) -> None:
    """Validate a lifecycle state transition.

    Enforces both underlying Procore FSM rules and strict MCP safety invariants.

    Args:
        entity_type: Construction entity type (e.g. 'rfi', 'commitment', etc.).
        from_state: Current state of the entity.
        to_state: Target state to transition to.
        is_mcp: Whether this transition is initiated via MCP (defaults to True).

    Raises:
        ValueError: If entity_type is unrecognized.
        InvalidStateTransitionError: If the transition is illegal in Procore.
        SafetyInvariantViolation: If is_mcp=True and to_state is terminal/authoritative.
    """
    canonical_entity = _resolve_entity_type(entity_type)
    transitions = LIFECYCLE_TRANSITIONS[canonical_entity]
    valid_states = LIFECYCLE_STATES[canonical_entity]

    norm_from = normalize_state(from_state)
    norm_to = normalize_state(to_state)

    if norm_from not in valid_states:
        raise InvalidStateTransitionError(
            f"State '{from_state}' is not a valid state for entity '{canonical_entity}'."
        )

    if norm_to not in valid_states:
        raise InvalidStateTransitionError(
            f"State '{to_state}' is not a valid state for entity '{canonical_entity}'."
        )

    allowed_destinations = transitions.get(norm_from, set())
    if norm_to not in allowed_destinations:
        raise InvalidStateTransitionError(
            f"Illegal transition for '{canonical_entity}' from '{norm_from}' to '{norm_to}'. "
            f"Allowed transitions from '{norm_from}': {sorted(allowed_destinations)}."
        )

    if is_mcp and norm_to in FORBIDDEN_MUTATION_STATUSES:
        statuses_str = ", ".join(sorted(FORBIDDEN_MUTATION_STATUSES))
        raise SafetyInvariantViolation(
            f"MCP attempted transition of '{canonical_entity}' from '{norm_from}' to "
            f"forbidden terminal/authoritative status '{norm_to}'. "
            f"Terminal statuses ({statuses_str}) cannot be set via MCP."
        )


def compute_reachable_states(
    entity_type: str,
    start_state: str | Enum = "draft",
    is_mcp: bool = True,
) -> set[str]:
    """Compute the set of all reachable states from a starting state using BFS.

    Args:
        entity_type: Construction entity type.
        start_state: Initial state to begin exploration from (default: "draft").
        is_mcp: If True, blocks all transitions into forbidden terminal states.

    Returns:
        Set of reachable state names.

    Raises:
        ValueError: If entity_type is unrecognized.
        InvalidStateTransitionError: If start_state is invalid for the entity.
    """
    canonical_entity = _resolve_entity_type(entity_type)
    transitions = LIFECYCLE_TRANSITIONS[canonical_entity]
    valid_states = LIFECYCLE_STATES[canonical_entity]

    norm_start = normalize_state(start_state)
    if norm_start not in valid_states:
        raise InvalidStateTransitionError(
            f"Starting state '{start_state}' is not valid for entity '{canonical_entity}'."
        )

    reachable: set[str] = {norm_start}
    queue: list[str] = [norm_start]

    while queue:
        current = queue.pop(0)
        for next_state in transitions.get(current, set()):
            if is_mcp and next_state in FORBIDDEN_MUTATION_STATUSES:
                continue
            if next_state not in reachable:
                reachable.add(next_state)
                queue.append(next_state)

    return reachable


def verify_zero_terminal_reachability(
    entity_type: str,
    start_state: str | Enum = "draft",
) -> bool:
    """Formally verify that terminal/authoritative states are 100% unreachable via MCP.

    Evaluates the reachability theorem:
    ∀ s ∈ Reachable(entity, start=draft, is_mcp=True): s ∉ FORBIDDEN_MUTATION_STATUSES

    Args:
        entity_type: Construction entity type to verify.
        start_state: Initial state (default: "draft").

    Returns:
        True if the invariant theorem holds.

    Raises:
        AssertionError: If any forbidden terminal state is reachable via MCP.
    """
    reachable = compute_reachable_states(entity_type, start_state=start_state, is_mcp=True)
    forbidden_intersection = reachable & FORBIDDEN_MUTATION_STATUSES
    if forbidden_intersection:
        raise AssertionError(
            f"Formal reachability theorem violated for '{entity_type}': "
            f"terminal states {forbidden_intersection} are reachable from '{start_state}' via MCP!"
        )
    return True


def verify_all_lifecycles(start_state: str = "draft") -> dict[str, bool]:
    """Verify zero terminal reachability across all registered construction entities."""
    return {
        entity: verify_zero_terminal_reachability(entity, start_state=start_state)
        for entity in SUPPORTED_ENTITIES
    }
