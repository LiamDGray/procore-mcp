"""Adversarial property-based fuzzing tests for safety invariants using Hypothesis."""

import unicodedata
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from procore_mcp.safety import (
    FORBIDDEN_MUTATION_STATUSES,
    SAFE_MUTATION_STATUSES,
    SafetyInvariantViolation,
    assert_write_permitted,
)

# Base terminal and authoritative statuses that must be blocked
FORBIDDEN_BASE_STATUSES: list[str] = sorted(FORBIDDEN_MUTATION_STATUSES)
SAFE_BASE_STATUSES: list[str] = sorted(SAFE_MUTATION_STATUSES)

# Whitespace characters including standard whitespace and unicode whitespace
WHITESPACE_CHARS: list[str] = [
    " ",
    "\t",
    "\n",
    "\r",
    "\v",
    "\f",
    "\u00a0",  # non-breaking space
    "\u2000",  # en quad
    "\u2002",  # en space
    "\u2003",  # em space
    "\u200b",  # zero-width space
    "\ufeff",  # byte order mark / zero-width non-breaking space
    "\u3000",  # ideographic space
]

whitespace_st: st.SearchStrategy[str] = st.text(alphabet=WHITESPACE_CHARS, min_size=0, max_size=5)


def to_fullwidth(s: str) -> str:
    """Convert an ASCII string to full-width unicode characters."""
    chars: list[str] = []
    for c in s:
        code = ord(c)
        if 0x21 <= code <= 0x7E:
            chars.append(chr(code + 0xFEE0))
        elif code == 0x20:
            chars.append("\u3000")
        else:
            chars.append(c)
    return "".join(chars)


@st.composite
def random_casing(draw: st.DrawFn, word: str) -> str:
    """Generate a string with random casing (upper, lower, title, mixed) and optional full-width."""
    cased = "".join(draw(st.sampled_from([c.lower(), c.upper()])) for c in word)
    if draw(st.booleans()):
        cased = to_fullwidth(cased)
    return cased


@st.composite
def status_keys(draw: st.DrawFn) -> str:
    """Generate status key variations with random casing and whitespace."""
    cased = draw(random_casing("status"))
    pre = draw(whitespace_st)
    post = draw(whitespace_st)
    return f"{pre}{cased}{post}"


@st.composite
def forbidden_status_values(draw: st.DrawFn) -> str:
    """Generate forbidden status values with random casing and whitespace."""
    base = draw(st.sampled_from(FORBIDDEN_BASE_STATUSES))
    cased = draw(random_casing(base))
    pre = draw(whitespace_st)
    post = draw(whitespace_st)
    return f"{pre}{cased}{post}"


# Recursive strategies for arbitrary nested JSON-like dictionaries and lists
json_primitives: st.SearchStrategy[Any] = (
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text()
)

json_values: st.SearchStrategy[Any] = st.recursive(
    json_primitives,
    lambda children: (
        st.lists(children, max_size=4) | st.dictionaries(st.text(), children, max_size=4)
    ),
    max_leaves=20,
)

json_dicts: st.SearchStrategy[dict[str, Any]] = st.dictionaries(
    st.text(),
    json_values,
    max_size=4,
)


@st.composite
def payload_with_forbidden_status(draw: st.DrawFn) -> dict[str, Any]:
    """Generate a nested dictionary payload containing a forbidden status 1 to 10 levels deep."""
    depth = draw(st.integers(min_value=1, max_value=10))
    s_key = draw(status_keys())
    s_val = draw(forbidden_status_values())

    # Innermost dictionary containing the forbidden status
    current: Any = {s_key: s_val}

    leaf_siblings = draw(st.dictionaries(st.text(min_size=1), json_values, max_size=3))
    for k, v in leaf_siblings.items():
        if not is_status_norm(k):
            current[k] = v

    # Wrap in (depth - 1) levels of nesting
    for _ in range(depth - 1):
        wrap_as_list = draw(st.booleans())
        if wrap_as_list:
            prefix_items = draw(st.lists(json_values, max_size=2))
            suffix_items = draw(st.lists(json_values, max_size=2))
            current = prefix_items + [current] + suffix_items
        else:
            outer_key = draw(st.text(min_size=1))
            other_entries = draw(st.dictionaries(st.text(min_size=1), json_values, max_size=2))
            other_entries.pop(outer_key, None)
            wrapper = {outer_key: current}
            wrapper.update(other_entries)
            current = wrapper

    # Ensure top-level payload is a dictionary as required by assert_write_permitted
    if isinstance(current, dict):
        payload = current
    else:
        root_key = draw(st.text(min_size=1))
        payload = {root_key: current}

    extra_root = draw(st.dictionaries(st.text(min_size=1), json_values, max_size=2))
    for k, v in extra_root.items():
        if k not in payload:
            payload[k] = v

    return payload


# Strategies for safe payloads
def is_forbidden_norm(s: str) -> bool:
    norm = unicodedata.normalize("NFKC", s).strip().lower()
    return norm in FORBIDDEN_MUTATION_STATUSES


def is_status_norm(k: str) -> bool:
    norm = unicodedata.normalize("NFKC", k).strip().lower()
    return norm == "status"


safe_strings = st.text().filter(lambda s: not is_forbidden_norm(s))
safe_scalars = (
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | safe_strings
)
non_status_keys = st.text().filter(lambda k: not is_status_norm(k))


@st.composite
def safe_status_values(draw: st.DrawFn) -> str:
    base = draw(st.sampled_from(SAFE_BASE_STATUSES))
    cased = draw(random_casing(base))
    pre = draw(whitespace_st)
    post = draw(whitespace_st)
    return f"{pre}{cased}{post}"


safe_json_values: st.SearchStrategy[Any] = st.recursive(
    safe_scalars | safe_status_values(),
    lambda children: (
        st.lists(children, max_size=3)
        | st.dictionaries(non_status_keys, children, max_size=3)
        | st.dictionaries(
            status_keys(),
            safe_status_values() | st.integers() | st.booleans() | st.none(),
            max_size=1,
        )
    ),
    max_leaves=15,
)

safe_payloads: st.SearchStrategy[dict[str, Any]] = st.dictionaries(
    non_status_keys,
    safe_json_values,
    max_size=4,
).flatmap(
    lambda d: st.booleans().flatmap(
        lambda include_status: (
            st.tuples(status_keys(), safe_status_values()).map(lambda kv: {**d, kv[0]: kv[1]})
            if include_status
            else st.just(d)
        )
    )
)


# Invariant Property 1: test_forbidden_status_always_raises
@given(payload=payload_with_forbidden_status())
@settings(max_examples=300)
def test_forbidden_status_always_raises(payload: dict[str, Any]) -> None:
    """Invariant Property 1: Assert that for any payload containing a forbidden status
    anywhere in its tree, assert_write_permitted("tool", payload, allow_writes=True)
    GUARANTEES raising SafetyInvariantViolation."""
    with pytest.raises(SafetyInvariantViolation):
        assert_write_permitted("test_tool", payload, allow_writes=True)


# Invariant Property 2: test_read_only_always_raises_regardless_of_payload
@given(
    payload=st.one_of(
        json_dicts,
        payload_with_forbidden_status(),
        safe_payloads,
    )
)
@settings(max_examples=300)
def test_read_only_always_raises_regardless_of_payload(payload: dict[str, Any]) -> None:
    """Invariant Property 2: Assert that when allow_writes=False, ANY payload
    whatsoever GUARANTEES raising PermissionError."""
    with pytest.raises(PermissionError, match=r"read-only mode"):
        assert_write_permitted("test_tool", payload, allow_writes=False)


# Invariant Property 3: test_safe_payloads_never_raise
@given(payload=safe_payloads)
@settings(max_examples=300)
def test_safe_payloads_never_raise(payload: dict[str, Any]) -> None:
    """Invariant Property 3: Assert that for payloads containing only allowed statuses
    or arbitrary harmless keys/values, assert_write_permitted never raises any error."""
    assert_write_permitted("test_tool", payload, allow_writes=True)
