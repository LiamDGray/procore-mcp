/-
  ProcoreSafety.lean
  Formal Lean 4 Specification and Machine-Checked Proof of the
  Zero Unauthorized Commitment Invariant for Procore MCP.
-/

namespace ProcoreMCP

/-- Lifecycle states across Procore RFIs, Commitments, Submittals, and Change Events. -/
inductive State : Type where
  | draft        : State
  | open_st      : State
  | pending      : State
  | under_review : State
  | out_for_bid  : State
  | approved     : State
  | issued       : State
  | executed     : State
  | closed       : State
  | void_st      : State
  deriving Repr, DecidableEq

/-- Terminal or legally binding states requiring human-in-the-loop sign-off. -/
def isTerminal : State → Bool
  | State.approved => true
  | State.issued   => true
  | State.executed => true
  | State.closed   => true
  | State.void_st  => true
  | _              => false

/-- The MCP Client Safety Barrier (assert_write_permitted).
    Any attempted transition into a terminal state is intercepted and rejected (returns none). -/
def mcpFilter (target : State) : Option State :=
  if isTerminal target then
    none
  else
    some target

/-- An execution step initiated by an autonomous agent via MCP. -/
def agentStep (current : State) (target : State) : State :=
  match mcpFilter target with
  | some nextState => nextState
  | none           => current -- State mutation blocked; reverts to current safe state

/-- Theorem: Zero Unauthorized Commitment
    For any initial non-terminal state `s` and any target state `target` proposed by an LLM,
    the resulting state `agentStep s target` is guaranteed never to be terminal. -/
theorem zero_unauthorized_commitment
  (s : State) (target : State) (h_safe : isTerminal s = false) :
  isTerminal (agentStep s target) = false := by
  dsimp [agentStep, mcpFilter]
  split
  · -- Case: isTerminal target = true -> blocked, returns s
    exact h_safe
  · -- Case: isTerminal target = false -> allowed, returns target
    rename_i h_not_terminal
    simp at h_not_terminal
    exact h_not_terminal

/-- Corollary: Inductive preservation of safety over arbitrary length execution traces. -/
inductive Trace : State → List State → State → Prop where
  | nil (s : State) : Trace s [] s
  | cons (s : State) (target : State) (rest : List State) (final : State) :
      Trace (agentStep s target) rest final → Trace s (target :: rest) final

theorem trace_preserves_safety
  (s final : State) (targets : List State)
  (h_init : isTerminal s = false)
  (h_trace : Trace s targets final) :
  isTerminal final = false := by
  induction h_trace with
  | nil => exact h_init
  | cons s' target' rest' final' h_step ih =>
    have h_next_safe : isTerminal (agentStep s' target') = false :=
      zero_unauthorized_commitment s' target' h_init
    exact ih h_next_safe

end ProcoreMCP
