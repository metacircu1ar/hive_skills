--------------------------- MODULE CodeReviewLoop ---------------------------
EXTENDS Naturals, FiniteSets, TLC

(***************************************************************************
On-demand reviewer turns, session channels, and one shared dispatcher.

This is a bounded behavioral abstraction, NOT a refinement proof of Python or
of the runtime. Each session has one compliant implementor and at most one
executing worker. Helpers' check/act sequences are atomic at the boundaries
below; context temp creation, context promotion, dispatch queuing, request creation, response
temp creation, response promotion, release, consumption, and acknowledgement
are separate actions. Workers finish after each round. Runtime status
is truthful and stable until the corresponding modeled operation completes.

Launch + bind is one external-success action. A real bind failure must stop
that unrecorded worker before dispatch continues; interruption in that window
is outside this model. The dispatcher is unique: its marker is bookkeeping,
not a lease. OperatorRevive represents explicit operator intervention after
stopping the old dispatcher/waiter. It is deliberately NOT fair.

The finite Sessions set starts with fresh open channels. Opening them earlier
or later than service startup is immaterial to the modeled decisions. Round,
accepted, decisions, and payload tags are specification bookkeeping, NOT new
runtime fields. Interruption/shutdown history serves only reachability witnesses.
No source trees, textual findings, wall-clock polling, stale
lock deletion, arbitrary file corruption, or wrapper terminal messages are
modeled. See README.md for the complete boundary and checked configurations.
***************************************************************************)

CONSTANTS Sessions, MaxRounds, MaxHandles, FaultBudget,
          EnableServiceLifecycle, Mutation
ASSUME /\ Sessions # {}
       /\ MaxRounds \in Nat \ {0}
       /\ MaxHandles \in Nat \ {0}
       /\ FaultBudget \in Nat
       /\ EnableServiceLifecycle \in BOOLEAN
       /\ Mutation \in {"none", "earlyUnlock", "tempUnlock", "crossSession",
                       "closeBeforeStop", "dropFeedback", "replaceRunning",
                       "shutdownCloses"}

Kinds == {"none", "findings", "clean"}
RuntimeStatuses == {"running", "resumable", "stopped", "gone", "unknown", "error"}
Commands == {"none", "launch", "replace", "resume", "stop"}

VARIABLES q, service, faults
vars == <<q, service, faults>>

EmptySession(s) ==
    [closed |-> FALSE, close |-> FALSE, handle |-> 0,
     runtime |-> "gone", command |-> "none", error |-> "none",
     phase |-> "idle", round |-> 0, accepted |-> 0,
     context |-> 0, contextTemp |-> FALSE, lock |-> FALSE,
     dispatch |-> FALSE, deferred |-> FALSE,
     responseTemp |-> "none", response |-> "none",
     responseOwner |-> s, responseRound |-> 0, decisions |-> 0,
     workerPC |-> "wait", reviewedRound |-> 0, interruptedAt |-> "none"]

Init ==
    /\ q = [s \in Sessions |-> EmptySession(s)]
    /\ service = [mode |-> "off", recover |-> {}, stoppedOnce |-> FALSE, restarted |-> FALSE,
                   idleShutdownHandle |-> [s \in Sessions |-> 0]]
    /\ faults = FaultBudget

Open(s) == ~q[s].closed /\ ~q[s].close
Bound(s) == q[s].handle # 0
Live(s) == q[s].runtime = "running"
WorkerCanRun(s) == Bound(s) /\ q[s].runtime = "running"

\* Literal branch ordering of dispatcher_loop.decide_action.
Decide(x, observed, shuttingDown) ==
    IF x.closed THEN "leave"
    ELSE IF observed = "error" THEN "report"
    ELSE IF x.close \/ shuttingDown THEN
        IF x.handle = 0 \/ observed \in {"stopped", "gone", "unknown"}
        THEN IF x.close THEN "mark_closed" ELSE "leave"
        ELSE "stop"
    ELSE IF ~x.lock THEN "leave"
    ELSE IF x.handle = 0 THEN "launch"
    ELSE IF observed = "running" THEN IF x.dispatch THEN "await_worker" ELSE "continue"
    ELSE IF observed = "resumable" THEN "resume"
    ELSE "replace"

\* Unknown is an explicit unknown-handle answer, never a runtime-call error.
Observations(s) ==
    IF ~Bound(s) THEN {"gone"}
    ELSE IF q[s].runtime = "gone" THEN {"gone", "unknown"}
    ELSE IF q[s].runtime = "resumable" /\ (q[s].close \/ service.mode = "shutdown")
         THEN {"stopped"}
    ELSE {q[s].runtime}

ListenerEvent(s) ==
    /\ ~q[s].closed
    /\ IF q[s].close THEN q[s].error # "close"
       ELSE q[s].dispatch /\ ~q[s].deferred /\ q[s].error = "none" /\ q[s].lock

NeedsDispatch(s) ==
    /\ q[s].command = "none"
    /\ service.mode \in {"running", "shutdown"}
    /\ s \in service.recover \/
       (service.mode = "running" /\ ListenerEvent(s))

PrepareContext(s) ==
    /\ Open(s) /\ q[s].phase = "idle" /\ q[s].round < MaxRounds
    /\ ~q[s].lock /\ q[s].response = "none"
    /\ q[s].responseTemp = "none"
    /\ q' = [q EXCEPT ![s].phase = "contextTemp",
                     ![s].round = @ + 1, ![s].context = 0,
                     ![s].contextTemp = TRUE, ![s].decisions = 0,
                     ![s].dispatch = FALSE]
    /\ UNCHANGED <<service, faults>>

\* A restarted publish-context removes its unfinished temp and republishes.
\* Rewriting the same abstract complete body is a stutter at this boundary.
PromoteContext(s) ==
    /\ Open(s) /\ q[s].phase = "contextTemp"
    /\ q[s].contextTemp /\ ~q[s].lock
    /\ q' = [q EXCEPT ![s].contextTemp = FALSE,
                     ![s].context = q[s].round, ![s].phase = "ready"]
    /\ UNCHANGED <<service, faults>>

QueueDispatch(s) ==
    /\ Open(s) /\ q[s].phase = "ready" /\ ~q[s].lock /\ ~q[s].dispatch
    /\ q' = [q EXCEPT ![s].dispatch = TRUE]
    /\ UNCHANGED <<service, faults>>

RequestReview(s) ==
    /\ Open(s) /\ q[s].phase = "ready"
    /\ q[s].context = q[s].round /\ ~q[s].contextTemp
    /\ ~q[s].lock /\ q[s].response = "none" /\ q[s].dispatch
    /\ q' = [q EXCEPT ![s].lock = TRUE, ![s].phase = "waiting"]
    /\ UNCHANGED <<service, faults>>

ReadRequest(s) ==
    /\ Open(s) /\ WorkerCanRun(s) /\ q[s].workerPC = "wait"
    /\ q[s].lock /\ q[s].response = "none"
    /\ q' = [q EXCEPT ![s].workerPC = "review",
                     ![s].reviewedRound = q[s].context]
    /\ UNCHANGED <<service, faults>>

WriteResponseTemp(s) ==
    /\ Open(s) /\ WorkerCanRun(s) /\ q[s].workerPC = "review"
    /\ q[s].lock /\ q[s].response = "none"
    /\ \E kind \in Kinds \ {"none"}:
         q' = [q EXCEPT ![s].responseTemp = kind, ![s].workerPC = "promote"]
    /\ UNCHANGED <<service, faults>>

PromoteResponse(s) ==
    /\ Open(s) /\ WorkerCanRun(s) /\ q[s].workerPC = "promote"
    /\ q[s].lock /\ q[s].responseTemp # "none" /\ q[s].response = "none"
    /\ q' = [q EXCEPT ![s].response = q[s].responseTemp,
                     ![s].responseTemp = "none", ![s].responseOwner = s,
                     ![s].responseRound = q[s].round,
                     ![s].decisions = @ + 1, ![s].workerPC = "release"]
    /\ UNCHANGED <<service, faults>>

\* Any restored worker sees the final and releases it without reviewing again.
RecoverPublishedResponse(s) ==
    /\ Open(s) /\ WorkerCanRun(s) /\ q[s].workerPC = "wait"
    /\ q[s].lock /\ q[s].response # "none"
    /\ q' = [q EXCEPT ![s].workerPC = "release"]
    /\ UNCHANGED <<service, faults>>

ReleaseReview(s) ==
    /\ Open(s) /\ WorkerCanRun(s) /\ q[s].workerPC = "release"
    /\ q[s].lock /\ q[s].response # "none" /\ q[s].responseTemp = "none"
    /\ q' = [q EXCEPT ![s].lock = FALSE, ![s].workerPC = "end"]
    /\ UNCHANGED <<service, faults>>

\* Completion notification removes the dispatcher's busy-session deferral.
\* No model/API call is needed while the resulting conversation is idle.
FinishTurn(s) ==
    /\ WorkerCanRun(s) /\ q[s].workerPC = "end"
    /\ q' = [q EXCEPT ![s].runtime = "resumable", ![s].deferred = FALSE]
    /\ UNCHANGED <<service, faults>>

ConsumeResponse(s) ==
    /\ Open(s) /\ q[s].phase = "waiting"
    /\ ~q[s].lock /\ q[s].response # "none" /\ q[s].responseTemp = "none"
    /\ q' = [q EXCEPT ![s].phase = "received", ![s].accepted = q[s].round]
    /\ UNCHANGED <<service, faults>>

Acknowledge(s) ==
    /\ Open(s) /\ q[s].phase = "received" /\ ~q[s].lock
    /\ q' = [q EXCEPT ![s].response = "none", ![s].phase = "idle"]
    /\ UNCHANGED <<service, faults>>

RequestClose(s) ==
    /\ Open(s)
    /\ q' = [q EXCEPT ![s].close = TRUE]
    /\ UNCHANGED <<service, faults>>

\* Closure while waiting cancels the round. Neither files nor a clean response
\* are deleted or manufactured. The frozen phase remains until close is confirmed.
WorkerSeesClose(s) ==
    /\ q[s].close /\ ~q[s].closed /\ q[s].runtime = "running"
    /\ q' = [q EXCEPT ![s].runtime = "resumable", ![s].workerPC = "end",
                     ![s].deferred = FALSE]
    /\ UNCHANGED <<service, faults>>

StartService ==
    /\ service.mode = "off"
    /\ service' = [service EXCEPT !.mode = "running",
                        !.recover = {s \in Sessions : ~q[s].closed},
                        !.restarted = service.stoppedOnce]
    /\ q' = [s \in Sessions |-> [q[s] EXCEPT !.deferred = FALSE]]
    /\ UNCHANGED faults

\* Operator-triggered, including in an existing dispatcher conversation.
OperatorRevive ==
    /\ EnableServiceLifecycle
    /\ service.mode \in {"running", "down"}
    /\ \A s \in Sessions : q[s].command = "none"
    /\ service' = [service EXCEPT !.mode = "running",
                        !.recover = {s \in Sessions : ~q[s].closed}]
    /\ q' = [s \in Sessions |-> [q[s] EXCEPT !.deferred = FALSE]]
    /\ UNCHANGED faults

Dispatch(s) ==
    /\ NeedsDispatch(s)
    /\ \E observed \in Observations(s):
       LET action == Decide(q[s], observed, service.mode = "shutdown") IN
       /\ q' = [q EXCEPT ![s].error = "none",
                  ![s].closed = IF action = "mark_closed" THEN TRUE ELSE @,
                  ![s].dispatch = IF action \in {"launch", "replace", "resume"} THEN FALSE ELSE @,
                  ![s].deferred = action = "await_worker",
                  ![s].command = IF action \in Commands THEN action ELSE "none"]
       /\ service' = [service EXCEPT !.recover = @ \ {s}]
    /\ UNCHANGED faults

DispatchError(s) ==
    /\ NeedsDispatch(s) /\ faults > 0
    /\ q' = [q EXCEPT ![s].error = IF q[s].close THEN "close" ELSE "runtime"]
    /\ service' = [service EXCEPT !.recover = @ \ {s}]
    /\ faults' = faults - 1

RuntimeLaunchBind(s) ==
    /\ q[s].command \in {"launch", "replace"}
    /\ service.mode \in {"running", "shutdown"}
    /\ q[s].handle < MaxHandles /\ ~q[s].closed
    /\ q' = [q EXCEPT ![s].handle = @ + 1, ![s].runtime = "running",
                     ![s].command = "none", ![s].error = "none",
                     ![s].workerPC = "wait"]
    /\ UNCHANGED <<service, faults>>

RuntimeResume(s) ==
    /\ q[s].command = "resume"
    /\ q' = [q EXCEPT ![s].runtime = "running", ![s].command = "none",
                     ![s].workerPC = "wait"]
    /\ UNCHANGED <<service, faults>>

RuntimeStop(s) ==
    /\ q[s].command = "stop"
    /\ q' = [q EXCEPT ![s].runtime = "stopped", ![s].command = "none",
                     ![s].workerPC = "wait"]
    /\ service' = [service EXCEPT !.recover = @ \cup {s}]
    /\ UNCHANGED faults

RuntimeFailure(s) ==
    /\ q[s].command # "none" /\ faults > 0
    /\ q' = [q EXCEPT ![s].command = "none",
                     ![s].error = IF q[s].close THEN "close" ELSE "runtime"]
    /\ faults' = faults - 1
    /\ UNCHANGED service

\* Silence is not a listener event for a bound session. Only explicit recovery
\* or a close request can bring this loss to the dispatcher.
LoseWorker(s) ==
    /\ faults > 0 /\ Bound(s) /\ q[s].runtime = "running"
    /\ q[s].command = "none" /\ ~q[s].closed
    /\ \E result \in {"gone", "resumable"}:
         q' = [q EXCEPT ![s].runtime = result, ![s].workerPC = "wait",
                ![s].interruptedAt = IF q[s].lock /\ q[s].response # "none" THEN "final"
                    ELSE IF q[s].responseTemp # "none" THEN "temp" ELSE "review"]
    /\ faults' = faults - 1
    /\ UNCHANGED service

CrashDispatcher ==
    /\ faults > 0 /\ service.mode = "running"
    /\ \A s \in Sessions : q[s].command = "none"
    /\ service' = [service EXCEPT !.mode = "down", !.recover = {}]
    /\ faults' = faults - 1
    /\ UNCHANGED q

BeginShutdown ==
    /\ EnableServiceLifecycle /\ service.mode = "running"
    /\ \A s \in Sessions : q[s].command = "none"
    /\ service' = [service EXCEPT !.mode = "shutdown",
                        !.recover = {s \in Sessions : ~q[s].closed},
                        !.idleShutdownHandle = [s \in Sessions |->
                            IF Open(s) /\ q[s].phase = "idle" /\ Bound(s)
                            THEN q[s].handle ELSE 0]]
    /\ UNCHANGED <<q, faults>>

\* A repeated shutdown command obtains fresh observations, including errors.
RetryShutdown ==
    /\ service.mode = "shutdown" /\ service.recover = {}
    /\ \A s \in Sessions : q[s].command = "none"
    /\ \E s \in Sessions : ~q[s].closed /\ (Live(s) \/ q[s].error # "none")
    /\ service' = [service EXCEPT !.recover = {s \in Sessions : ~q[s].closed}]
    /\ UNCHANGED <<q, faults>>

FinishShutdown ==
    /\ service.mode = "shutdown" /\ service.recover = {}
    /\ \A s \in Sessions : /\ q[s].command = "none"
                             /\ ~Live(s) /\ q[s].error = "none"
    /\ service' = [service EXCEPT !.mode = "off", !.recover = {}, !.stoppedOnce = TRUE]
    /\ UNCHANGED <<q, faults>>

\* A later runtime inspection may offer resume of a conversation whose prior
\* execution was confirmed stopped. This changes only
\* the observation, not execution; RuntimeResume is still required.
ObserveResumeAvailable(s) ==
    /\ service.mode = "running" /\ service.stoppedOnce
    /\ s \in service.recover /\ Open(s)
    /\ Bound(s) /\ q[s].runtime = "stopped" /\ q[s].command = "none"
    /\ q' = [q EXCEPT ![s].runtime = "resumable"]
    /\ UNCHANGED <<service, faults>>

PairProgress(s) ==
    PrepareContext(s) \/ PromoteContext(s) \/ QueueDispatch(s) \/ RequestReview(s) \/
    ReadRequest(s) \/ WriteResponseTemp(s) \/ PromoteResponse(s) \/
    RecoverPublishedResponse(s) \/ ReleaseReview(s) \/
    ConsumeResponse(s) \/ Acknowledge(s) \/ WorkerSeesClose(s) \/ FinishTurn(s)
RuntimeSuccess(s) == RuntimeLaunchBind(s) \/ RuntimeResume(s) \/ RuntimeStop(s)
LocalStep(s) == PairProgress(s) \/ RequestClose(s) \/ Dispatch(s) \/
                DispatchError(s) \/ RuntimeSuccess(s) \/ RuntimeFailure(s) \/ LoseWorker(s) \/ ObserveResumeAvailable(s)

\* Deliberately wrong transitions; each negative config names its expected failure.
BadUnlock(s) ==
    /\ Mutation \in {"earlyUnlock", "tempUnlock"}
    /\ q[s].lock /\ q[s].response = "none"
    /\ q[s].workerPC = IF Mutation = "tempUnlock" THEN "promote" ELSE "review"
    /\ q' = [q EXCEPT ![s].lock = FALSE]
    /\ UNCHANGED <<service, faults>>
BadRoute(s, t) ==
    /\ Mutation = "crossSession" /\ s # t
    /\ q[s].response # "none"
    /\ q' = [q EXCEPT ![t].response = q[s].response,
                     ![t].responseOwner = s, ![t].responseRound = q[s].responseRound]
    /\ UNCHANGED <<service, faults>>
BadClose(s) ==
    /\ Mutation = "closeBeforeStop" /\ q[s].close /\ Live(s)
    /\ q' = [q EXCEPT ![s].closed = TRUE]
    /\ UNCHANGED <<service, faults>>
BadRecovery(s) ==
    /\ Mutation = "dropFeedback" /\ s \in service.recover
    /\ q[s].response # "none"
    /\ q' = [q EXCEPT ![s].response = "none"]
    /\ UNCHANGED <<service, faults>>
BadReplacement(s) ==
    /\ Mutation = "replaceRunning" /\ Live(s) /\ q[s].handle < MaxHandles
    /\ q' = [q EXCEPT ![s].handle = @ + 1]
    /\ UNCHANGED <<service, faults>>
BadShutdown(s) ==
    /\ Mutation = "shutdownCloses" /\ service.mode = "shutdown"
    /\ ~q[s].closed /\ ~q[s].close /\ ~Live(s)
    /\ q' = [q EXCEPT ![s].closed = TRUE]
    /\ UNCHANGED <<service, faults>>

Next ==
    \/ \E s \in Sessions : LocalStep(s)
    \/ StartService \/ OperatorRevive \/ CrashDispatcher
    \/ BeginShutdown \/ RetryShutdown \/ FinishShutdown
    \/ \E s \in Sessions : BadUnlock(s) \/ BadClose(s) \/ BadRecovery(s) \/
                            BadReplacement(s) \/ BadShutdown(s)
    \/ \E s, t \in Sessions : BadRoute(s, t)

SafetySpec == Init /\ [][Next]_vars
\* Only healthy configurations use these assumptions. Neither revive, stop
\* failures, shutdown retries, nor crash recovery are promised to happen.
LiveSpec == SafetySpec /\ WF_vars(StartService) /\
    \A s \in Sessions : WF_vars(PairProgress(s)) /\ WF_vars(Dispatch(s)) /\
                         WF_vars(RuntimeSuccess(s))

TypeOK ==
    /\ DOMAIN q = Sessions
    /\ service \in [mode : {"off", "running", "down", "shutdown"}, recover : SUBSET Sessions,
                       stoppedOnce : BOOLEAN, restarted : BOOLEAN,
                       idleShutdownHandle : [Sessions -> 0..MaxHandles]]
    /\ faults \in 0..FaultBudget
    /\ \A s \in Sessions :
       /\ q[s] \in [closed : BOOLEAN, close : BOOLEAN, handle : 0..MaxHandles,
            runtime : {"gone", "running", "resumable", "stopped"},
            command : Commands, error : {"none", "runtime", "close"},
            phase : {"idle", "contextTemp", "ready", "waiting", "received"},
            round : 0..MaxRounds, accepted : 0..MaxRounds, context : 0..MaxRounds,
            contextTemp : BOOLEAN, lock : BOOLEAN, responseTemp : Kinds,
            dispatch : BOOLEAN, deferred : BOOLEAN,
            response : Kinds, responseOwner : Sessions, responseRound : 0..MaxRounds,
            decisions : 0..1, workerPC : {"wait", "review", "promote", "release", "end"},
            reviewedRound : 0..MaxRounds, interruptedAt : {"none", "review", "temp", "final"}]
       /\ q[s].accepted <= q[s].round

RequestHasContext == \A s \in Sessions :
    q[s].lock => q[s].context = q[s].round /\ q[s].round > 0 /\ ~q[s].contextTemp
ResponseMatchesSession == \A s \in Sessions : q[s].response # "none" =>
    /\ q[s].responseOwner = s /\ q[s].responseRound = q[s].round
    /\ q[s].decisions = 1 /\ q[s].responseTemp = "none"
ClosedOnlyAfterStop == \A s \in Sessions : q[s].closed =>
    q[s].close /\ ~Live(s) /\ q[s].command = "none"
StoppedServiceHasNoWorkers == service.mode = "off" =>
    \A s \in Sessions : ~Live(s) /\ q[s].command = "none"
FrozenPendingContext == \A s \in Sessions : q[s].phase = "waiting" =>
    q[s].context = q[s].round /\ ~q[s].contextTemp
ReviewedSubmittedRound == \A s \in Sessions :
    q[s].workerPC \in {"review", "promote"} => q[s].reviewedRound = q[s].round
IdleWorkersStayDormant == [] [\A s \in Sessions :
    (~WorkerCanRun(s) /\ q'[s].runtime = "running") => q[s].lock]_vars

PublicationBeforeUnlock == [] [\A s \in Sessions :
    (q[s].lock /\ ~q'[s].lock) =>
        q[s].response # "none" /\ q[s].responseTemp = "none"]_vars
FeedbackPreservedUntilAcknowledged == [] [\A s \in Sessions :
    (q[s].response # "none" /\ q'[s].response # q[s].response) =>
        /\ Open(s) /\ q[s].phase = "received" /\ ~q[s].lock
        /\ q'[s].phase = "idle" /\ q'[s].response = "none"]_vars
NoAcceptanceAfterClose == [] [\A s \in Sessions :
    (q[s].close \/ q[s].closed) => q'[s].accepted = q[s].accepted]_vars
ClosedStaysClosed == [] [\A s \in Sessions : q[s].closed => q'[s].closed]_vars
HandleChangesOnlyWhenUnavailable == [] [\A s \in Sessions :
    (q[s].handle # 0 /\ q'[s].handle # q[s].handle) => ~Live(s)]_vars
\* Separation holds by construction in LocalStep. This is structural bookkeeping,
\* not a proof of Python folder/path routing; the process tests provide that evidence.
SessionIsolation == [] [\A s \in Sessions : LocalStep(s) =>
    \A t \in Sessions \ {s} : q'[t] = q[t]]_vars

RequestEventuallyResolved == \A s \in Sessions :
    (q[s].phase = "waiting" /\ ~q[s].closed) ~>
        (q[s].accepted = q[s].round \/ q[s].closed)
CloseEventuallyConfirmed == \A s \in Sessions : q[s].close ~> q[s].closed

\* Reachability checks intentionally violate these predicates. They guard
\* against a successful but vacuous safety run that never reaches the feature.
NoTwoRoundsWitness == ~\E s \in Sessions : q[s].accepted = 2 /\ q[s].handle = 1
NoDeferredRoundWitness == ~\E s \in Sessions :
    q[s].deferred /\ q[s].lock /\ q[s].workerPC = "end" /\
    q[s].reviewedRound < q[s].round
NoConcurrentWitness == ~\E s, t \in Sessions : s # t /\
    q[s].workerPC = "review" /\ q[t].workerPC = "review"
NoRecoveryReleaseWitness == ~\E s \in Sessions :
    q[s].handle = 2 /\ q[s].interruptedAt = "final" /\
    q[s].response # "none" /\ ~q[s].lock
NoRecoveryTempWitness == ~\E s \in Sessions :
    q[s].handle = 2 /\ q[s].interruptedAt = "temp" /\ q[s].accepted = 1
NoRestartIdleWitness == ~\E s \in Sessions :
    service.mode = "running" /\ service.restarted /\
    service.idleShutdownHandle[s] > 0 /\
    q[s].handle = service.idleShutdownHandle[s] /\
    q[s].runtime \in {"resumable", "stopped"} /\ q[s].phase = "idle" /\
    s \notin service.recover
NoRestartReplacementWitness == ~\E s \in Sessions :
    service.mode = "running" /\ service.restarted /\
    service.idleShutdownHandle[s] > 0 /\
    q[s].handle > service.idleShutdownHandle[s] /\
    q[s].runtime = "running" /\ q[s].phase = "waiting" /\ q[s].round = 2
LostWorkerEventuallyRecovers == \A s \in Sessions :
    (Bound(s) /\ q[s].runtime = "gone" /\ ~q[s].close /\ ~q[s].closed) ~>
        (WorkerCanRun(s) \/ q[s].closed)
=============================================================================
