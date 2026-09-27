---------------------------- MODULE EffectSeal ----------------------------
(***************************************************************************)
(* Admission of untrusted effects into trusted state.                      *)
(*                                                                         *)
(* Each request r runs an untrusted server against a private staging copy. *)
(* The server may write any value at any time while it is alive, and a    *)
(* writer may survive the quiesce step (WriterMayEscape). The mediator     *)
(* reads the staged result once, checks it, and promotes it or refuses.    *)
(* An allowance ledger bounds how many requests may execute.               *)
(*                                                                         *)
(* The flags turn each mechanism on or off, mirroring the ablation matrix: *)
(*   SameRead       promote the checked bytes, never re-read staging       *)
(*   StopWriters    quiesce writers before the read                        *)
(*   AtomicReserve  check-and-take the allowance slot in one step          *)
(*   ReplayGuard    a replayed request returns its record, never re-runs   *)
(* With every flag TRUE, all invariants hold even when writers escape.     *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets

CONSTANTS Req, Max, SameRead, StopWriters, AtomicReserve, ReplayGuard,
          WriterMayEscape

Vals == {"good", "bad"}      \* "good" = matches the contract
None == "none"

VARIABLES slot,     \* ledger: "free" | "reserved" | "committed" | "failed"
          execs,    \* how many times the untrusted server ran for r
          phase,    \* "idle" | "checked" | "running" | "stopped" | "read"
                    \*   | "done" | "crashed"
          alive,    \* an untrusted writer for r can still write
          staged,   \* the private copy
          checked,  \* the single snapshot the mediator read
          trusted   \* what entered trusted state for r

vars == <<slot, execs, phase, alive, staged, checked, trusted>>

Used == {r \in Req : slot[r] # "free"}

Init ==
    /\ slot    = [r \in Req |-> "free"]
    /\ execs   = [r \in Req |-> 0]
    /\ phase   = [r \in Req |-> "idle"]
    /\ alive   = [r \in Req |-> FALSE]
    /\ staged  = [r \in Req |-> None]
    /\ checked = [r \in Req |-> None]
    /\ trusted = [r \in Req |-> None]

\* Start the untrusted server on a fresh private copy.
Launch(r) ==
    /\ phase'  = [phase  EXCEPT ![r] = "running"]
    /\ alive'  = [alive  EXCEPT ![r] = TRUE]
    /\ execs'  = [execs  EXCEPT ![r] = @ + 1]
    /\ staged' = [staged EXCEPT ![r] = None]

Reserve(r) ==
    /\ AtomicReserve
    /\ phase[r] = "idle" /\ slot[r] = "free"
    /\ Cardinality(Used) < Max
    /\ slot' = [slot EXCEPT ![r] = "reserved"]
    /\ Launch(r)
    /\ UNCHANGED <<checked, trusted>>

\* Non-atomic variant: the room check and the take are separate steps.
CheckRoom(r) ==
    /\ ~AtomicReserve
    /\ phase[r] = "idle" /\ slot[r] = "free"
    /\ Cardinality(Used) < Max
    /\ phase' = [phase EXCEPT ![r] = "checked"]
    /\ UNCHANGED <<slot, execs, alive, staged, checked, trusted>>

TakeSlot(r) ==
    /\ phase[r] = "checked"
    /\ slot' = [slot EXCEPT ![r] = "reserved"]
    /\ Launch(r)
    /\ UNCHANGED <<checked, trusted>>

\* The same request arrives again after it finished.
Replay(r) ==
    /\ ~ReplayGuard
    /\ phase[r] = "done"
    /\ Launch(r)
    /\ UNCHANGED <<slot, checked, trusted>>

\* The adversary writes any value while any writer of r is alive.
ServerWrite(r, v) ==
    /\ alive[r]
    /\ phase[r] \in {"running", "stopped", "read", "done"}
    /\ staged' = [staged EXCEPT ![r] = v]
    /\ UNCHANGED <<slot, execs, phase, alive, checked, trusted>>

\* Quiesce. A writer that escapes the process tree stays alive.
Stop(r) ==
    /\ StopWriters
    /\ phase[r] = "running"
    /\ phase' = [phase EXCEPT ![r] = "stopped"]
    /\ alive' = [alive EXCEPT ![r] = WriterMayEscape]
    /\ UNCHANGED <<slot, execs, staged, checked, trusted>>

Read(r) ==
    /\ \/ phase[r] = "stopped"
       \/ ~StopWriters /\ phase[r] = "running"
    /\ checked' = [checked EXCEPT ![r] = staged[r]]
    /\ phase'   = [phase   EXCEPT ![r] = "read"]
    /\ UNCHANGED <<slot, execs, alive, staged, trusted>>

\* Promote. With SameRead the committed value IS the checked one; without it
\* the commit path re-reads the private copy.
Commit(r) ==
    /\ phase[r] = "read" /\ checked[r] = "good"
    /\ trusted' = [trusted EXCEPT ![r] = IF SameRead THEN checked[r]
                                                    ELSE staged[r]]
    /\ slot'    = [slot  EXCEPT ![r] = "committed"]
    /\ phase'   = [phase EXCEPT ![r] = "done"]
    /\ UNCHANGED <<execs, alive, staged, checked>>

Refuse(r) ==
    /\ phase[r] = "read" /\ checked[r] # "good"
    /\ slot'  = [slot  EXCEPT ![r] = "failed"]
    /\ phase' = [phase EXCEPT ![r] = "done"]
    /\ UNCHANGED <<execs, alive, staged, checked, trusted>>

\* The mediator dies mid-call. The durable reservation survives; the
\* private copy and the checked snapshot are lost.
Crash(r) ==
    /\ phase[r] \in {"running", "stopped", "read"}
    /\ phase'   = [phase   EXCEPT ![r] = "crashed"]
    /\ staged'  = [staged  EXCEPT ![r] = None]
    /\ checked' = [checked EXCEPT ![r] = None]
    /\ UNCHANGED <<slot, execs, alive, trusted>>

Next ==
    \E r \in Req :
        \/ Reserve(r) \/ CheckRoom(r) \/ TakeSlot(r) \/ Replay(r)
        \/ \E v \in Vals : ServerWrite(r, v)
        \/ Stop(r) \/ Read(r) \/ Commit(r) \/ Refuse(r) \/ Crash(r)

Spec == Init /\ [][Next]_vars

-----------------------------------------------------------------------------
(* Invariants *)

TypeOK ==
    /\ slot    \in [Req -> {"free", "reserved", "committed", "failed"}]
    /\ staged  \in [Req -> Vals \cup {None}]
    /\ checked \in [Req -> Vals \cup {None}]
    /\ trusted \in [Req -> Vals \cup {None}]

\* The allowance bounds how many requests ever executed.
AllowanceBound == Cardinality(Used) <= Max

\* No request executes the untrusted server twice.
ExecAtMostOnce == \A r \in Req : execs[r] <= 1

\* Only contract-matching effects enter trusted state.
TrustedOnlyAccepted == \A r \in Req : trusted[r] \in {None, "good"}

\* A committed request's trusted value is exactly what was checked.
CommittedIsChecked ==
    \A r \in Req : slot[r] = "committed" => trusted[r] = checked[r]

\* A crash never returns a slot to the pool: the outcome is UNKNOWN.
CrashStaysSpent ==
    \A r \in Req : phase[r] = "crashed" => slot[r] = "reserved"

\* Bounds the replay-enabled variants, where execs could otherwise grow forever.
StateConstraint == \A r \in Req : execs[r] <= 2

=============================================================================
