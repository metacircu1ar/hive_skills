# Code Review Loop Formal Verification

This directory contains the TLA+ state machine and reproducible TLC checks for the review protocol coordinated through one fixed shared directory.

The skill package's [implementor CLI](../scripts/implementor_loop.py) and [reviewer CLI](../scripts/reviewer_loop.py) are the complete concrete protocol endpoints: they own channel publication and receipt, lock transitions, waits, acknowledgement, recovery, and cleanup. Their blocking wait commands inspect protocol state once per second and remain silent until an actionable state or protocol error occurs; role agents do not inspect the files directly.

## Files

- `CodeReviewLoop.tla` — state machine, safety invariants, fairness assumptions, and liveness properties.
- `CodeReviewLoop.cfg` — normal TLC configuration with one bounded lock loss enabled.
- `CodeReviewLoopEarlyUnlock.cfg` — negative mutation that unlocks before feedback publication.
- `CodeReviewLoopTempFileEarlyUnlock.cfg` — negative mutation that unlocks after the reviewer temp write but before rename.
- `CodeReviewLoopEarlyCompletionPublication.cfg` — negative mutation that publishes completion before cleanup finishes.
- `run-tlc.sh` — digest-verifying TLC runner.
- `check-state-space.sh` — guards the recorded state counts and graph depth.
- `check-early-unlock.sh`, `check-temp-file-unlock.sh`, and `check-cleanup-order.sh` — ensure deliberately invalid transitions violate their intended properties.

## Abstraction and file mapping

The model treats the captured coordination directory as one abstract file namespace and keeps clean identifiers independent of the skill's `.hive_skills_` filesystem prefix:

| Model field | Skill file |
| --- | --- |
| `files.reviewLock` | empty review-lock marker |
| `files.implementorToReviewerTmp` | implementor-to-reviewer temp channel |
| `files.implementorToReviewerTxt` | implementor-to-reviewer final channel |
| `files.reviewerToImplementorTmp` | reviewer-to-implementor temp channel |
| `files.reviewerToImplementorTxt` | reviewer-to-implementor final channel |
| `files.roundComplete` | empty completion marker |

The six file-presence fields are initialized independently, so TLC explores all 64 possible stale startup combinations. The implementor removes them one at a time, with completion removed last. The reviewer begins in `offline`; `StartReviewer` represents the external caller launching it only after startup cleanup completes. Reviewer-local participation is encoded by `pollingFresh` versus `pollingParticipated`, while the `request` record contains only per-request bookkeeping.

Top-level state is factored into six canonical variables: the two actor states plus `files`, `content`, `request`, and `faults` records. Every action specifies the full next state of every top-level variable.

The implementation and both channel bodies are abstracted to Boolean version bits. A finite `feedbackKind` records findings or the exact `NO_FINDINGS` sentinel. Concrete message text, the coordination-directory path, repository and context paths, path-equality validation, Python process lifetime, and filesystem calls are otherwise abstracted away. The lock and completion marker are presence-only signals and carry no data. A script's internal one-second poll that observes no actionable change is a stuttering step and is not modeled as a separate transition. Missing-lock recovery performed inside the implementor waiter is represented by `RetryMissingRequest`.

## Modeled behavior

The model covers:

- cleanup from every possible combination of six stale startup files, with stale completion removed last;
- externally ordered reviewer launch after startup cleanup;
- logical waiting states, with idle script polls represented as stuttering and process blocking assumed rather than verified;
- mandatory implementor context on every request, with an initial publication and later reuse or atomic refresh;
- atomic publication for both directional channels;
- opposite channel polarity: implementor publication while unlocked and reviewer publication while locked;
- implementation and implementor-message freezing through a missing-lock retry gap;
- one bounded lock deletion before reviewer acquisition or while a reviewer is active but undecided;
- findings-or-`NO_FINDINGS` publication before every reviewer unlock;
- implementor read/handling followed by a separate inbound-message acknowledgement;
- another planned implementation phase after `NO_FINDINGS` without terminating the reviewer;
- exactly one reviewer-channel decision per logical request;
- final cleanup and completion publication through the implementor CLI only after `NO_FINDINGS`, whether the declared decision authority is the implementor or its caller;
- completion acknowledgement by the participating reviewer and observation by the implementor-side endpoint used by the declared authority;
- successful termination with all six files absent.

The action relation assumes both agents and the role scripts follow the protocol. TLC checks compliant interleavings and explicitly enabled mutations; it does not establish that an LLM will invoke or keep waiting on the correct script process, limit protocol operations to the captured directory, or keep review activity static and read-only. The implementor's `completion-authority` is caller-versus-implementor control policy rather than file state: either authority uses the same implementor CLI transition, so the choice is abstracted from the model and is not an input to the reviewer.

## Checked properties

| Protocol requirement | TLA+ property |
| --- | --- |
| Actor states, records, counters, versions, and file markers remain in finite domains | `TypeOK` |
| Reviewer launch occurs only after startup cleanup | `ReviewerStartsAfterStartupCleanup` |
| Implementation cannot change while locked or through the same request's missing-lock retry gap | `ImplementationFrozenThroughReview` |
| Submitted implementor context cannot appear, disappear, or change through that interval | `ImplementorMessageFrozenThroughReview` |
| Implementor-channel temp/final publication is atomic and unlocked | `ImplementorMessagePublicationIsAtomic` |
| Reviewer-channel temp/final publication is atomic and writer-owned | `ReviewerMessagePublicationIsAtomic` |
| Reviewer temp publication starts while the lock exists | `ReviewerMessagePublicationStartsWhileLocked` |
| Published reviewer contents remain unchanged until implementor acknowledgement | `ReviewerMessageFrozenUntilConsumed` |
| Every undecided request carries a frozen implementor context | `ReviewRequestsIncludeImplementorContext` |
| Reviewer decisions use the submitted implementation and mandatory context snapshot | `ReviewerUsesFrozenSnapshot` |
| A reviewer cannot unlock before a complete reviewer final exists | `ReviewerMessagePublishedBeforeUnlock` |
| Decision counts and findings/`NO_FINDINGS` kinds agree with file state | `DecisionAccounting` |
| Lock, feedback, completion, and logical-request state remain correlated | `RequestStateIsConsistent` |
| Feedback handling and outbound preparation require published reviewer feedback | `HandlingRequiresReviewerMessage` |
| A published completion marker is the only remaining file while acknowledgement is pending | `CompletionHasPriority` |
| Final cleanup and shutdown are reachable only from `NO_FINDINGS` | `CompletionRequiresNoFindings` |
| The reviewer terminates only after acknowledging completion | `ReviewerTerminatesOnlyAfterCompletion` |
| Successful termination removes all six working files | `SuccessfulTerminationIsClean` |
| The declared authority, through the implementor endpoint, atomically promotes the final clean response to completion after the other four files are absent | `CompletionMarkerPublishedLast` |
| Any completion-marker removal occurs only after the other five files are absent | `CompletionMarkerRemovedLast` |
| Only the participating reviewer acknowledges normal completion | `CompletionAcknowledgedByParticipatingReviewer` |
| Every logical request reaches exactly one decision before closing | `ExactlyOneDecisionPerLogicalRequest` |
| Startup cleanup reaches a clean implementation state | `StartupCleanupEventuallyFinishes` |
| The externally launched reviewer eventually becomes active | `ReviewerEventuallyStarts` |
| Every live review lock eventually unlocks after a decision | `ReviewRequestEventuallyReleased` |
| `NO_FINDINGS` eventually continues into another phase or shutdown | `NoFindingsEventuallyContinuesOrShutsDown` |
| Reviewer messages are consumed, missing implementor context is published before review, and live temp publications complete | `ReviewerMessageEventuallyConsumed`, `ImplementorContextEventuallyAvailable`, `ReviewerMessageTempEventuallyPublished`, `ImplementorMessageTempEventuallyPublished` |
| Completion is eventually acknowledged and both actors terminate | `CompletionEventuallyAcknowledged`, `ShutdownEventuallyFinishes` |

## Run

Java 11 or newer and a `tla2tools.jar` build are required:

```sh
./run-tlc.sh
./check-state-space.sh
./check-early-unlock.sh
./check-temp-file-unlock.sh
./check-cleanup-order.sh
```

The normal run must finish without errors. The state-space check reruns it and fails if the recorded counts or depth change. The final three commands enable deliberately invalid actions and succeed only when TLC reports the intended property violation.

Override tool discovery when needed:

```sh
JAVA_BIN=/path/to/java \
TLA2TOOLS_JAR=/path/to/tla2tools.jar \
TLA2TOOLS_SHA256=expected-digest \
./run-tlc.sh
```

The runner verifies the pinned default jar's SHA-256 digest. A custom jar is verified when `TLA2TOOLS_SHA256` is supplied; otherwise the runner warns. `TLC_METADIR` selects the state directory, and `TLC_COVERAGE=1` enables action coverage.

The recorded 2026-08-26 normal run completed without errors after generating 1,127 states, finding 738 distinct states, and reaching graph depth 23. TLC checked eleven temporal-property branches. All three negative mutation checks produced their expected violations.

Coverage confirms both lock-loss locations and retry: `LosePollingLock`, `LoseActiveReviewLock`, and `RetryMissingRequest` are reachable. Both reviewer outcomes and both implementor choices after them are reachable, as are `PublishCompletion`, `AcknowledgeCompletion`, and `ObserveCompletionAcknowledged`. `RemoveCleanupReviewerTmp` and `RemoveCleanupImplementorTmp` remain at `0:0` because compliant publication ordering makes both temp files absent before final cleanup; they remain defensive actions matching the skill's remove-if-present instructions. Arbitrary stale temp cleanup is exercised during startup.

## Fault-model limits

The simplified protocol intentionally delegates lifecycle isolation to external orchestration. The model assumes the implementor completes startup cleanup before the reviewer is launched and that no reviewer from an older loop remains active. Because the files carry no IDs or generation tags, a stale live agent could otherwise interfere with a new loop; that behavior is outside the model rather than silently claimed as verified.

Filesystem checks and subsequent writes or removals are separate real calls but single TLA+ actions. The model therefore does not prove compare-and-act atomicity. It does exercise one bounded lock deletion while the reviewer is polling, reviewing, or publishing, and proves that retry preserves the same frozen logical request. Repeated deletions and arbitrary lock loss after a decision are not modeled.

After startup, temp files are reachable only while their compliant publisher is active. Fairness lets `AbortReviewAfterLockLoss` clear a reviewer temp before retry. TLC verifies that the implementor context file exists and remains frozen; it abstracts the required absolute paths, task source or full text, evidence explanation, and implementor notes rather than interpreting their prose. It also abstracts the review itself, so it does not prove that the reviewer avoids builds, tests, execution, or writes outside the protocol files, nor that it prioritizes substantive correctness over compilation concerns. TLC is untimed and does not model the scripts' one-second poll interval, their 90-second stale-state grace period, process interruption by an execution environment, arbitrary findings text, or whether an LLM understands and correctly acts on a message it read.

The completion CLI retains the clean reviewer final as a durable phase record while removing the other files, empties it, and atomically renames that same filesystem entry to the completion marker. The `PublishCompletion` action models that final atomic promotion. If the process is interrupted before or after the rename, replay can distinguish the retained reviewer final, the published marker, and an already-acknowledged all-absent state. TLC verifies only this common post-authorization file transition; it does not verify who chose to close a caller-owned session or the control-plane handback itself.

The model assumes the participating reviewer remains live long enough to remove the completion marker. The implementor script now waits indefinitely for that acknowledgement unless the operator or execution environment interrupts it; interruption and restart behavior are outside the model.

The fault budget permits one environmental lock deletion before a reviewer decision. Early unlocks and early completion publication are enabled only by their negative configurations.

## Verified tool identity

The local verification used OpenJDK 25.0.2 and an untagged TLA+ master build whose manifest reports `Implementation-Version: 2.0 2026-08-11`, an empty `X-Git-Tag`, and revision [`0894c3407f4717fec7cc18bde3bf3c857fa47333`](https://github.com/tlaplus/tlaplus/commit/0894c3407f4717fec7cc18bde3bf3c857fa47333), with TLC banner `2026.08.11.125311`. Its SHA-256 digest is `ab323b79802aedc3203b3f9af37c6aca3ed43f4e0225b36f2aa77b26de46c05f`, which `run-tlc.sh` verifies before launching the pinned default binary.

This binary came from the mutable Clarke `v1.8.0` pre-release channel; `v1.8.0` is not its implementation version and the channel asset is not a durable content pin. Reproduce the run with the exact digest above or build the referenced source revision.
