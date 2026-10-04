# Procore MCP Formal Verification Suite

This directory contains the mathematical models, specifications, and formal proof artifacts guaranteeing the **Zero Unauthorized Commitment Invariant** for the Procore Model Context Protocol (MCP) server.

---

## 1. The Core Safety Invariant

Autonomous AI agents operating over MCP must be mathematically prohibited from transitioning external enterprise systems of record into binding, irrevocable, or financially dangerous states (`approved`, `executed`, `issued`, `closed`, `void`).

$$\forall \text{ entities } E, \quad \forall \text{ execution traces } \sigma = \langle s_0, s_1, \dots, s_k \rangle \text{ under MCP gates}: \quad s_k \notin \text{ForbiddenStates}$$

---

## 2. Verification Artifacts

### A. SMT Model Checking via Microsoft Z3 (`procore_mcp/formal_z3.py`)
- **Engine**: Microsoft Z3 Theorem Prover (`z3-solver`).
- **Test Harness**: [`tests/test_formal_fsm_z3.py`](../tests/test_formal_fsm_z3.py).
- **Methodology**: Encodes the Procore lifecycle finite state machines (`rfi`, `commitment`, `change_event`, `submittal`) into first-order predicate logic over enumerated sorts.
- **Verification Result**: The conjecture that a sequence of MCP-gated tool transitions can reach any terminal status is proved **UNSAT** across all entities. Conversely, when the MCP gate is removed (`is_mcp=False`), the solver finds a valid counterexample path, proving that the verification theorem is non-vacuous.
- **To run**:
  ```bash
  pytest tests/test_formal_fsm_z3.py
  ```

### B. Concurrent State-Machine Specification in TLA+ (`procore_safety.tla`)
- **Specification**: [`procore_safety.tla`](./procore_safety.tla).
- **Engine**: TLC Model Checker.
- **Properties Checked**:
  - `TypeOK`: Well-typedness of states, interceptor tokens, and counters.
  - `ZeroUnauthorizedCommitment`: Invariant asserting `currentState \notin ForbiddenStates`.
  - `SafetyTheorem`: Temporal safety formula $\square (\text{ZeroUnauthorizedCommitment})$.

### C. Inductive Theorem Proving in Lean 4 (`ProcoreSafety.lean`)
- **Proof File**: [`ProcoreSafety.lean`](./ProcoreSafety.lean).
- **Engine**: Lean 4 Interactive Theorem Prover.
- **Theorems Proven**:
  - `zero_unauthorized_commitment`: Single-step inductive transition safety.
  - `trace_preserves_safety`: Multi-step trace induction proving safety holds over arbitrary path lengths $k \in \mathbb{N}$.

---

## 3. Hermetic CI Integration

The Z3 SMT verification suite executes automatically as part of the hermetic `./run_checks.sh` verification gate. Any change to entity lifecycles in `procore_mcp/fsm.py` that inadvertently exposes a path to a binding status immediately causes the test suite to fail with a formal solver violation.
