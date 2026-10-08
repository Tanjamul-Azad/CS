--------------------------- MODULE EffectSealNet ---------------------------
(***************************************************************************)
(* Admission of untrusted network effects (RQ-N).                          *)
(*                                                                         *)
(* A network send cannot be staged and undone, so the broker decides each  *)
(* request before it leaves. The untrusted server, while a call runs, may  *)
(* propose any request on two concurrent streams:                          *)
(*   "good"    matches the call's contract                                 *)
(*   "bad"     does not match (diverted recipient, extra write, ...)       *)
(*   "tokgood" matches the contract but carries the real API credential    *)
(*             inside the contract's slack (possible only if the server    *)
(*             holds the credential and the contract has slack)            *)
(*   "tokbad"  sends the credential somewhere the contract does not allow  *)
(*                                                                         *)
(* Flags mirror the ablations:                                             *)
(*   PreSend       check each request before it is transmitted             *)
(*   CredInjection the server holds only a dummy; the broker adds the real *)
(*                 credential to admitted requests                         *)
(*   Confined      the server has no route out except the broker           *)
(*   AtomicCount   check-and-count an allowance slot in one step           *)
(*   ReplayGuard   a finished call cannot be run again                     *)
(*   Slack         the contract leaves some bits free                      *)
(***************************************************************************)
EXTENDS Naturals

CONSTANTS Calls, Allowed, PreSend, CredInjection, Confined, AtomicCount,
          ReplayGuard, Slack

Streams == {1, 2}
None == "none"
Matches == {"good", "tokgood"}
Props == {"good", "bad"} \cup
         (IF CredInjection THEN {} ELSE ({"tokbad"} \cup (IF Slack THEN {"tokgood"} ELSE {})))

VARIABLES phase,    \* per call: "idle" | "running" | "done"
          runs,     \* how many times the call ran
          count,    \* admitted sends of the current run
          pending,  \* per call and stream: proposed request or None
          checked,  \* per call and stream: passed the room check (non-atomic)
          sent,     \* per call: transmitted requests, all runs
          badSent,  \* some non-matching request left the boundary
          tokenSent \* the real credential left the boundary

vars == <<phase, runs, count, pending, checked, sent, badSent, tokenSent>>

Init ==
    /\ phase     = [c \in Calls |-> "idle"]
    /\ runs      = [c \in Calls |-> 0]
    /\ count     = [c \in Calls |-> 0]
    /\ pending   = [c \in Calls |-> [s \in Streams |-> None]]
    /\ checked   = [c \in Calls |-> [s \in Streams |-> FALSE]]
    /\ sent      = [c \in Calls |-> 0]
    /\ badSent   = FALSE
    /\ tokenSent = FALSE

Start(c) ==
    /\ phase[c] = "idle"
    /\ phase' = [phase EXCEPT ![c] = "running"]
    /\ runs'  = [runs  EXCEPT ![c] = @ + 1]
    /\ UNCHANGED <<count, pending, checked, sent, badSent, tokenSent>>

\* Without a replay guard a finished call runs again with a fresh count.
Replay(c) ==
    /\ ~ReplayGuard /\ phase[c] = "done"
    /\ phase' = [phase EXCEPT ![c] = "running"]
    /\ runs'  = [runs  EXCEPT ![c] = @ + 1]
    /\ count' = [count EXCEPT ![c] = 0]
    /\ UNCHANGED <<pending, checked, sent, badSent, tokenSent>>

Propose(c, s, v) ==
    /\ phase[c] = "running" /\ pending[c][s] = None
    /\ pending' = [pending EXCEPT ![c][s] = v]
    /\ UNCHANGED <<phase, runs, count, checked, sent, badSent, tokenSent>>

Transmit(c, v) ==
    /\ sent'      = [sent EXCEPT ![c] = @ + 1]
    /\ badSent'   = (badSent \/ v \notin Matches)
    /\ tokenSent' = (tokenSent \/ v \in {"tokgood", "tokbad"})

Clear(c, s) ==
    /\ pending' = [pending EXCEPT ![c][s] = None]
    /\ checked' = [checked EXCEPT ![c][s] = FALSE]

\* Pre-send admission, atomic: match and take a slot in one step.
AdmitAtomic(c, s) ==
    /\ PreSend /\ AtomicCount
    /\ pending[c][s] \in Matches /\ count[c] < Allowed
    /\ count' = [count EXCEPT ![c] = @ + 1]
    /\ Transmit(c, pending[c][s]) /\ Clear(c, s)
    /\ UNCHANGED <<phase, runs>>

\* Pre-send admission, non-atomic: check room first, take the slot later.
CheckRoom(c, s) ==
    /\ PreSend /\ ~AtomicCount
    /\ pending[c][s] \in Matches /\ ~checked[c][s] /\ count[c] < Allowed
    /\ checked' = [checked EXCEPT ![c][s] = TRUE]
    /\ UNCHANGED <<phase, runs, count, pending, sent, badSent, tokenSent>>

TakeAndSend(c, s) ==
    /\ checked[c][s]
    /\ count' = [count EXCEPT ![c] = @ + 1]
    /\ Transmit(c, pending[c][s]) /\ Clear(c, s)
    /\ UNCHANGED <<phase, runs>>

Refuse(c, s) ==
    /\ PreSend
    /\ pending[c][s] # None /\ ~checked[c][s]
    /\ (pending[c][s] \notin Matches \/ count[c] >= Allowed)
    /\ Clear(c, s)
    /\ UNCHANGED <<phase, runs, count, sent, badSent, tokenSent>>

\* Without a pre-send check the request leaves first; any check comes too late.
SendUnchecked(c, s) ==
    /\ ~PreSend /\ pending[c][s] # None
    /\ count' = [count EXCEPT ![c] = @ + 1]
    /\ Transmit(c, pending[c][s]) /\ Clear(c, s)
    /\ UNCHANGED <<phase, runs>>

\* Without confinement the server can also send around the broker.
DirectSend(c, v) ==
    /\ ~Confined /\ phase[c] = "running"
    /\ Transmit(c, v)
    /\ UNCHANGED <<phase, runs, count, pending, checked>>

Finish(c) ==
    /\ phase[c] = "running"
    /\ \A s \in Streams : pending[c][s] = None
    /\ phase' = [phase EXCEPT ![c] = "done"]
    /\ UNCHANGED <<runs, count, pending, checked, sent, badSent, tokenSent>>

Next ==
    \E c \in Calls :
        \/ Start(c) \/ Replay(c) \/ Finish(c)
        \/ \E s \in Streams :
              \/ \E v \in Props : Propose(c, s, v)
              \/ AdmitAtomic(c, s) \/ CheckRoom(c, s) \/ TakeAndSend(c, s)
              \/ Refuse(c, s) \/ SendUnchecked(c, s)
        \/ \E v \in Props : DirectSend(c, v)

Spec == Init /\ [][Next]_vars

-----------------------------------------------------------------------------
(* Invariants *)

\* Only contract-matching requests ever leave the boundary.
OnlyApprovedSent == ~badSent

\* The real credential never leaves the boundary.
NoCredentialLeak == ~tokenSent

\* At most Allowed requests leave per approved call, across all runs.
SendBound == \A c \in Calls : sent[c] <= Allowed

\* Keeps the search finite in ablations that allow unbounded sends.
StateConstraint == \A c \in Calls : sent[c] <= Allowed + 1 /\ runs[c] <= 2

=============================================================================
