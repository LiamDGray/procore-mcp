--------------------------- MODULE procore_safety ---------------------------
(*
  Formal TLA+ Specification of the Procore MCP Client Safety Barrier
  and Zero Unauthorized Commitment Invariant.

  Evaluated with TLC Model Checker.
*)

EXTENDS Naturals, Sequences, FiniteSets

CONSTANTS
  Entities,            \* {"rfi", "commitment", "change_event", "submittal"}
  SafeStates,          \* {"draft", "open", "pending", "under_review", "out_for_bid"}
  ForbiddenStates,     \* {"issued", "approved", "executed", "closed", "void"}
  MaxSteps

VARIABLES
  currentState,        \* Current state of the entity in Procore
  proposedTransition,  \* Next state requested by LLM agent tool call
  mcpInterceptor,      \* State of safety barrier: "IDLE", "BLOCKED", "PASSED"
  stepCount            \* Bounded execution steps for finite model checking

vars == <<currentState, proposedTransition, mcpInterceptor, stepCount>>

AllStates == SafeStates \cup ForbiddenStates

-----------------------------------------------------------------------------
(* Initial State: Entities begin in draft or safe non-terminal state *)

Init ==
  /\ currentState = "draft"
  /\ proposedTransition = "none"
  /\ mcpInterceptor = "IDLE"
  /\ stepCount = 0

-----------------------------------------------------------------------------
(* Next State Relations *)

(* 1. Agent proposes an arbitrary transition from AllStates *)
AgentProposeTransition ==
  /\ mcpInterceptor = "IDLE"
  /\ stepCount < MaxSteps
  /\ \E next_s \in AllStates:
       /\ proposedTransition' = next_s
       /\ mcpInterceptor' = "EVALUATING"
       /\ UNCHANGED <<currentState, stepCount>>

(* 2. MCP Safety Barrier Intercepts & Blocks Terminal States *)
SafetyBarrierBlock ==
  /\ mcpInterceptor = "EVALUATING"
  /\ proposedTransition \in ForbiddenStates
  /\ mcpInterceptor' = "BLOCKED"
  /\ UNCHANGED <<currentState, proposedTransition, stepCount>>

(* 3. MCP Safety Barrier Passes Safe States *)
SafetyBarrierPass ==
  /\ mcpInterceptor = "EVALUATING"
  /\ proposedTransition \in SafeStates
  /\ mcpInterceptor' = "PASSED"
  /\ UNCHANGED <<currentState, proposedTransition, stepCount>>

(* 4. State Commit: Only occurs if safety barrier PASSED *)
CommitTransition ==
  /\ mcpInterceptor = "PASSED"
  /\ currentState' = proposedTransition
  /\ proposedTransition' = "none"
  /\ mcpInterceptor' = "IDLE"
  /\ stepCount' = stepCount + 1

(* 5. Reset after Blocked: State remains untouched, error returned to LLM *)
ResetBlocked ==
  /\ mcpInterceptor = "BLOCKED"
  /\ proposedTransition' = "none"
  /\ mcpInterceptor' = "IDLE"
  /\ stepCount' = stepCount + 1
  /\ UNCHANGED <<currentState>>

Next ==
  \/ AgentProposeTransition
  \/ SafetyBarrierBlock
  \/ SafetyBarrierPass
  \/ CommitTransition
  \/ ResetBlocked

Spec == Init /\ [][Next]_vars

-----------------------------------------------------------------------------
(* THEOREM & INVARIANTS: Zero Unauthorized Commitment Invariant *)

(* Type Invariant *)
TypeOK ==
  /\ currentState \in AllStates
  /\ proposedTransition \in (AllStates \cup {"none"})
  /\ mcpInterceptor \in {"IDLE", "EVALUATING", "BLOCKED", "PASSED"}
  /\ stepCount \in 0..MaxSteps

(* Safety Invariant: Current external state can NEVER be in ForbiddenStates *)
ZeroUnauthorizedCommitment ==
  currentState \notin ForbiddenStates

(* Temporal Safety Theorem: It is always the case that ZeroUnauthorizedCommitment holds *)
SafetyTheorem ==
  [][ZeroUnauthorizedCommitment]_vars

=============================================================================
