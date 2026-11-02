# Code Review Loop verification

This is active, bounded verification of the shared-dispatcher/session protocol in
[the skill](../SKILL.md). It replaces the retired single-pair model; the old
completion-marker cleanup checks are removed. No runtime protocol fields or features
are added by this model. It complements the Python helper/process tests and real-agent
exercises; it is not an exhaustive correctness proof of the Python, filesystem, runtime,
or agent instructions.

## Run

From this directory:

```sh
./check-all.sh
```

Or run checks separately:

```sh
./run-tlc.sh                                      # normal safety
TLC_CONFIG=CodeReviewLoopRecovery.cfg ./run-tlc.sh
TLC_CONFIG=CodeReviewLoopIsolation.cfg ./run-tlc.sh
TLC_CONFIG=CodeReviewLoopLiveness.cfg ./run-tlc.sh
python3 ./check-helper-decisions.py
./check-state-space.sh
./check-mutations.sh
./check-witnesses.sh
./check-liveness-limit.sh
```

Java 11+ and `tla2tools.jar` are required. The runner retains the pinned build
`2026.08.11.125311-0894c34`, SHA-256
`ab323b79802aedc3203b3f9af37c6aca3ed43f4e0225b36f2aa77b26de46c05f`, built from
[upstream revision `0894c3407f4717fec7cc18bde3bf3c857fa47333`](https://github.com/tlaplus/tlaplus/tree/0894c3407f4717fec7cc18bde3bf3c857fa47333).
Override with `JAVA_BIN`, `TLA2TOOLS_JAR`, and `TLA2TOOLS_SHA256` when needed; an
unverified custom jar produces a warning. `TLC_WORKERS` defaults to 1, and
`TLC_COVERAGE=1` adds coverage. Each run gets a private temporary state directory,
removed on exit; `TLC_METADIR` explicitly selects a retained directory instead.
`TLC_MODEL` is used by the helper-parity check for its temporary instrumented copy.
These checks never start a dispatcher or inspect a coordination directory.

[`check-state-space.sh`](check-state-space.sh) is the single source of exact recorded
state counts and depths for all four positive configurations. It prints and checks
them on each run. Unexpected tool failures fail the
suite. The negative and witness scripts require their exact expected TLC diagnostic;
an arbitrary nonzero exit is not success. The two older unlock check entrypoints
remain as shortcuts to their updated mutations.

## Model and implementation correspondence

`CodeReviewLoop.tla` uses `q[session]` for independent session state and `service` for
dispatcher state. Session IDs and channel owners are distinct TLC model values; handles
are session-local ordinals (the abstract runtime handle is the session/ordinal pair).
There is no source-directory comparison or source isolation guarantee.

Session separation holds **by construction** in this abstraction: every local action
updates only its indexed session record. `SessionIsolation` is a structural assertion,
not an independent isolation proof. The wrong-routing mutation demonstrates that the
owner tag check rejects an injected mismatch; it does not verify filesystem routing.
Concrete isolation evidence comes from
[`test_three_sessions_and_followup_rounds_remain_independent`](../scripts/test_sessions.py)
and the session-path validation tests, which exercise the Python scripts and folders.

| Model state/action | Current implementation |
| --- | --- |
| `contextTemp`, `context`; `PrepareContext`, `PromoteContext` | `implementor_loop.publish_context`: prepare/remove old output, write temp, promote complete context |
| `dispatch`, `lock`; `QueueDispatch`, `RequestReview` | `implementor_loop.request_review` queues a dispatch marker before publishing the review-lock marker; locked retries do not requeue |
| `ReadRequest`, `workerPC`, `reviewedRound` | Worker receives its assigned session's complete handoff and performs static review |
| `responseTemp`, `response`; `WriteResponseTemp`, `PromoteResponse` | `reviewer_loop.publish_response`: replace an unfinished temp, then atomically publish findings or `NO_FINDINGS` |
| `RecoverPublishedResponse`, `ReleaseReview` | `read_request` returns `review_ready_to_release`; `release_review` releases an existing final without publishing a second decision |
| `FinishTurn`, `deferred` | Worker ends its turn; a runtime completion notification clears the dispatcher's `--busy-session` deferral |
| `ConsumeResponse`, `Acknowledge` | Implementor `wait_for_review`, then `acknowledge_feedback` |
| `close`, `closed`; `RequestClose`, `WorkerSeesClose` | Session `close-request`, worker exits its role, dispatcher records `state.json` status only after stop confirmation |
| `Decide`, `Dispatch`, `error`, `command` | `dispatcher_loop.decide_action`, `reconcile`, pending runtime action, error suppression in `pending_events` |
| `RuntimeLaunchBind`, `RuntimeResume`, `RuntimeStop` | External runtime outcomes; dispatch is acknowledged before calling the runtime, bind records a new handle, stop confirmation permits closure |
| `StartService`, `OperatorRevive`, `service.recover` | `start` lists every open session and clears conversation-local deferrals; idle conversations stay dormant, explicit `--revive` retries pending work |
| `BeginShutdown`, `RetryShutdown`, `FinishShutdown` | `shutdown` uses fresh statuses, keeps the marker on stop/error, preserves open channels, removes marker only on completion |

The model's `Decide` branch order is checked against the **actual Python function**
for all 384 combinations of open/closed, close request, handle presence, pending review,
dispatch marker, shutdown, and the six runtime-status inputs. This parity check calls only the pure
`decide_action` function. It does not establish parity for other Python functions.

All sessions begin as fresh open channels. They can submit before service startup.
`service.mode = "off"` means the marker is absent; `"down"` means an interrupted
service whose marker remains. Plain start is enabled only from `off`. `OperatorRevive`
is explicit external intervention, including in an existing dispatcher conversation;
there is no automatic supervision transition for silently lost bound workers.

Every round is dispatched once during healthy execution. The dispatcher acknowledges
the dispatch marker before the runtime call, so bind cannot erase a fast follow-up
request. A submitted follow-up can arrive while the worker is finishing its previous
turn; `await_worker` defers that session until runtime completion notification. The
model represents that notification together with `FinishTurn`; actual notification
delivery is a host assumption, not something Python observes. Idle workers do not wait
or resume. A pending
close takes precedence over resume/replacement decisions. A close arriving after an
already-issued launch decision can still be followed by bind and then stop, matching
the helper's close-aware bind result. A launch/stop/observation error leaves the session
for later recovery, while a close can still wake a session with an earlier launch error.

Channel promotion and lock release are separate transitions. Worker interruption can
leave a response temp or a promoted final behind. Recovery can replace a temp, but must
release a complete final unchanged, without another decision. An interrupted implementor
publication is represented by remaining in `contextTemp`; restarting its publication
removes/replaces that temp before promotion. Command retries that leave the abstract
state unchanged and polling without events are stuttering steps.

Shutdown does not close an otherwise open session or consume feedback. A subsequent
plain start retains idle conversations, and resumes or replaces only for pending work.
During closure/shutdown, a completed resumable worker is observed as `stopped` and
needs no redundant stop call. `RuntimeStop` handles execution that is still active.
`ObserveResumeAvailable` represents a fresh startup observation that a previously
stopped idle/open conversation can now be resumed; it does not restart execution.
Until explicit cleanup, closed sessions retain channel data, including a lock/temp/final from cancellation.
Closure is **not approval** and is not evidence of `NO_FINDINGS` or successful tests.
The wrapper's terminal-result validation remains outside this model. Fresh mode uses
one round per session and closes it after feedback; reuse mode permits later rounds
on the same handle. The finite model covers both sequences, but does not enforce an
implementor's mode choice or generate an unbounded supply of fresh sessions.

## Bounds and checked results

The positive checks completed on 2026-11-04 using the pinned TLC build. These are
finite state spaces, not a proof for arbitrary numbers of sessions or rounds.

| Configuration | Sessions | Rounds/session | Handle ordinals/session | Fault budget | Service lifecycle |
| --- | ---: | ---: | ---: | ---: | --- |
| `CodeReviewLoop.cfg` | 2 | 2 | 1 | 0 | Startup and session closure |
| `CodeReviewLoopLiveness.cfg` | 2 | 2 | 1 | 0 | Startup and session closure |
| `CodeReviewLoopRecovery.cfg` | 1 | 1 | 2 | 1 | Shutdown, start, revive |
| `CodeReviewLoopIsolation.cfg` | 2 | 1 | 1 | 1 | Shutdown, start, revive |

One shared fault budget permits at most one runtime-call failure, worker interruption
(to resumable or gone), or dispatcher interruption. Successful shutdown/start/revive
may repeat within the finite state space. Handle ordinals are never reused. Reaching
the configured handle bound can leave a replacement action blocked; this is a modeling
cutoff, not a runtime capacity rule. Replacement recovery is checked in the one-session,
two-handle configuration; the two-session recovery check explores concurrent lifecycle
interleavings in structurally separate records and same-handle resume.
No liveness claim is made for either fault configuration. `CHECK_DEADLOCK FALSE`
allows idle sessions, reached bounds, and waits requiring external intervention;
the separate temporal properties check the progress that is actually promised.

Safety checks cover:

- typed state, complete submitted context, frozen pending context, and response tags
  matching the assigned session and round;
- at most one final publication per round, publication before unlock, and feedback
  preservation until explicit implementor acknowledgement;
- no new acceptance once close is requested, closed sessions staying closed, and
  closure requiring both a close request and a stopped/gone worker;
- handle replacement only after the old worker is unavailable, and no workers left
  active when clean service shutdown has removed the marker;
- starting/resuming a worker only for a pending review, with dormant idle conversations.

`check-mutations.sh` verifies that these checks reject seven deliberate faults:
unlock before any response, unlock with a response temp, wrong-session delivery,
closure before stop, feedback deletion during recovery, replacing a running worker,
and treating service shutdown as session closure.

`check-witnesses.sh` requires actual reachable traces for concurrent reviews,
two accepted rounds on the first handle, deferral of a follow-up while its worker is
finishing, recovery after interruption at the response temp and final boundaries,
idle-conversation retention after shutdown/start, and replacement when another round
arrives afterward. Specification-only `interruptedAt` and
`idleShutdownHandle` records tie these witnesses to those exact histories; they are
not runtime bookkeeping. The restart witnesses require an idle bound conversation
captured by that shutdown, retained on restart, and either left dormant or replaced
for a second submitted round.

## Liveness and external assumptions

Only `CodeReviewLoopLiveness.cfg` asserts progress: every submitted round eventually
has feedback consumed or closure confirmed, and every close request is eventually
confirmed. It assumes no failures, no service shutdown, eventual service startup,
and weak fairness of each session's pair progress, dispatcher handling, and successful
runtime operations. It does not require the operator to choose closure, nor claim that
all tasks eventually receive clean feedback or succeed.

`check-liveness-limit.sh` intentionally disproves `LostWorkerEventuallyRecovers` with
one possible worker loss, no operator revive/shutdown, and otherwise fair actors.
The trace reaches a bound worker that is gone and can stutter indefinitely: its round
was already dispatched and worker-loss notification is absent. The spare handle remains available, so this is
not a counterexample caused by the bounded handle supply. This is an expected protocol
limit, not an implementation defect or a reason to add automatic lost-worker detection.

The model assumes:

- one dispatcher per coordination directory, one compliant implementor per session,
  unique runtime handles, and no stale worker executing after confirmed stop;
- truthful runtime observations and stable stop/launch/resume outcomes at their modeled
  boundaries; a stop confirms both the worker and its active tool processes ended;
- completion notifications for healthy finishing workers, clearing busy-session
  deferrals without model-driven runtime polling; lost notifications require revive;
- the old dispatcher and its waiter are stopped before operator revival; the marker
  itself neither proves liveness nor enforces ownership;
- each participant uses the correct session script and keeps source/context frozen
  until feedback consumption or confirmed cancellation. Source contents, static-review
  quality, and agent obedience are assumptions, not mechanically checked behavior.

The Python scripts perform filesystem checks and subsequent writes/removals separately.
The model **does not prove those sequences atomic**: guards and each modeled file effect
are one abstract step. In particular, it does not check a close arriving between a
script's final open check and file mutation, stale snapshot races, partial writes,
power-loss durability, corrupt/missing channels, or external lock deletion. Atomic
rename is assumed. It also combines successful runtime launch and handle bind; a failed
bind must stop the unrecorded worker before further dispatch. Crashes or failed stops
inside that unrecorded-worker window are outside the abstraction. Dispatcher operations
on distinct sessions may interleave, an abstraction of independent session work; service
shutdown starts only after pending runtime operations finish.

Python regression tests cover stray directory entries, per-session corruption reports
that complete a wait even on hosts with buffered output, suppression of already-reported
errors while healthy sessions continue, and an implementor waiter rejecting absent
requests without creating a lock. Process tests also cover immediate worker reads,
dispatch acknowledgement before a fast follow-up, busy-session deferral without
hiding closure/errors, fresh-session closure, and same-handle continuation. These
runtime/file details are
outside the TLA+ fault model. A broken session does not abort scans of healthy sessions;
unreadable state still prevents claiming successful service shutdown.
The explicit `cleanup-closed` command removes terminal session directories after
consumers finish their closure checks. Deleting terminal artifacts is outside this
model; Python tests cover closed-only deletion, concurrent scanning, failure reporting,
and retry after interrupted deletion. The modeled active-session decisions are unchanged.

Maintain the model, parity check, bounds, mutations, and recorded counts alongside
protocol changes. Run the Python suites as well:

```sh
python3 -m unittest discover -s ../scripts -p 'test_*.py'
python3 -m unittest discover -s ../../parallel-code-review-loop/scripts -p 'test_*.py'
```

The Python tests exercise real helper/channel/process behavior that this state machine
abstracts. Real-agent exercises remain necessary for background notification delivery,
one-round worker behavior, actual idle token cost, and host-specific conversation
resume/replace behavior. No new live-agent billing measurement is claimed here.
