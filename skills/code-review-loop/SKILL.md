---
name: code-review-loop
description: "Run implementation/static-review rounds through one shared dispatcher. Implementors use a fresh reviewer session per round by default, or explicitly reuse a conversation. Workers finish each turn instead of waiting."
metadata:
  argument-hint: "implementor [coord=<absolute-dir>] [session-mode=fresh|reuse] [session=<id>] [completion-authority=implementor|caller] | reviewer [coord=<absolute-dir>] [revive]"
---

# Code Review Loop

One shared coordination directory serves multiple implementors. The public
`reviewer` role is the dispatcher: it creates one reviewer worker for each submitted
session and resumes it for later rounds when reuse is requested. All review content
passes through scripts; the dispatcher schedules worker turns.

## Roles and invocation

- **implementor:** changes code, runs checks, submits review, and consumes findings.
- **reviewer:** dispatches reviewer workers and manages their lifetime.
- **reviewer-worker:** internal role assigned by the dispatcher; performs one static
  review round and ends its turn. The conversation can be resumed.

**An implementor must never spawn, launch, delegate to, or simulate a reviewer.**
Only the dispatcher creates reviewer workers. Workers never create agents. Calling
this skill as implementor does not authorize launching the dispatcher or a substitute.

Capture the absolute current directory as the coordination directory unless the caller
supplies `coord=<absolute-dir>`. All participants use that same directory. Repository
paths come from the caller and the review handoff; they are not coordination directories.
Do not examine how source directories relate to other assignments.

Examples:

~~~text
/code-review-loop reviewer coord=/workspace
/code-review-loop implementor coord=/workspace
/code-review-loop implementor coord=/workspace session-mode=reuse
/code-review-loop implementor coord=/workspace session-mode=reuse session=<existing-id>
/code-review-loop reviewer coord=/workspace revive
~~~

A returning implementor needs its session ID or absolute session path from the caller.
An internal worker receives `reviewer-worker`, the coordination directory, session ID,
and this skill's absolute path from the dispatcher.

Implementors accept `session-mode=fresh|reuse`. **Omitted means `fresh`, the preferred
mode:** open a new session for every review round and close it after reading that
round's feedback, including findings. `reuse` keeps one session and reviewer conversation
across rounds. Supplying `session=<id>` reconnects to that session; it does not change
the default mode. These are implementor workflow inputs, not reviewer inputs.

Only implementors accept `completion-authority=implementor|caller`; omitted means
`implementor`. With `caller`, return a clean work-item result to the enclosing caller
and let it choose the next task or workflow completion. Fresh mode still closes every
review session; in reuse mode the caller also decides session closure. Reviewers have
no completion-authority input. Start a valid role immediately without asking whether
its counterpart is running.
If the role or a required existing session is missing, ask for that input.

## Script-only coordination

**Every interaction with coordination files goes through the bundled scripts.** This
applies to implementors, dispatcher, workers, and wrappers, during normal operation,
waiting, recovery, closure, and diagnosis. Never use `ls`, `cat`, `find`, `stat`,
`test -e`, `rg`, ad hoc Python, or hand-written polling to inspect that state. Never
edit, remove, or create protocol files manually. Read script JSON output instead.

Use the scripts beside this skill, not a guessed repository-relative copy. All pair
commands take `--coordination-dir <absolute-dir> --session <id-or-absolute-session-path>`.
Only `open-session` omits `--session`. A session folder is a channel, not a source tree.

Implementor and dispatcher waits poll inside Python once per second. **Stay silent
while waiting.** Prefer a host-managed background command with completion notification,
so the model is not called for periodic status checks. Keep one waiter, retain its task
handle, and wait for its notification; do not poll its output through repeated model turns.
Use the host's documented timeout and cancellation controls. Background limits vary;
if the host ends a waiter, restart only after confirming that process ended. Where only
foreground waiting exists, use the longest supported wait, resume the same process on
tool yields, and disclose the remaining idle-call cost once. Never promise zero idle
cost on such a host. Unexpected script errors must be reported, not repaired by hand.
Keep the implementor/dispatcher role open until protocol completion or shutdown;
a quiet wait or tool yield is not completion.
Reviewer workers have no waiting loop.

No skill-level worker count, pool, or wave limit applies. A real runtime launch failure
is reported for that session; `revive` retries it. A silently lost worker can leave a
request pending until the operator revives the dispatcher.

## Implementor

Use `scripts/implementor_loop.py`:

| Command | Result |
| --- | --- |
| `open-session --coordination-dir <dir>` | Returns the new session ID and path. Save them in conversation and report them to an enclosing wrapper. |
| `status` | Returns session state, saved `context_message`, and whether review, feedback, or closure is pending. Use this to reconnect. |
| `publish-context --message-file <absolute-file>` | Atomically publishes the complete review handoff. Inline `--message` and `--message-stdin` are also supported. |
| `request-review` | Submits the published context, or confirms an already submitted request. |
| `wait-for-review` | Blocks for a submitted review; returns feedback or closure. With neither a lock nor feedback, reports an error without submitting a round. |
| `acknowledge-feedback` | Removes consumed feedback so the next round can start. |
| `close-session` | Requests closure; may cancel an outstanding review. |
| `wait-for-close` | Blocks until the dispatcher records that the worker has stopped. |

For a new task, open a session, implement and test, publish context, request review,
then wait. For an existing session, use `status` to recover the saved context. If
`review_pending` or `feedback_ready` is true, use `wait-for-review` and consume the result
before editing. If closure is pending, use `wait-for-close`. Do not clear it on startup.

Every handoff includes:

- absolute coordination directory, session path, and repository path;
- the full task text or exact absolute files containing it;
- absolute context/evidence directories, operative files, and what they contribute;
- the review target/base, constraints and preserved behavior;
- checks run and their results, notes, and responses to earlier findings.

Once submitted, keep the code and review context unchanged until feedback is consumed
or closure is confirmed. One session has one outstanding round. Count accepted rounds
for reporting. Within a reused session, consume and acknowledge the last response
before submitting another round.

After reading feedback, follow the selected session mode:

- **Fresh (default):** retain the feedback in your task context, run `close-session`,
  then `wait-for-close`. Do this after findings as well as `NO_FINDINGS`, before editing
  or opening the next review session. Leave the response retained in the closed session;
  no acknowledgement is needed. Fix valid findings, run checks, and open a new session
  for the next review. Give the new reviewer the full task, prior findings and their
  disposition, and current evidence; it has no earlier conversation. Report each new
  session ID to an enclosing wrapper and count rounds across sessions.
- **Reuse:** retain the session ID. For findings, acknowledge, fix, check, publish the
  updated handoff, and submit again. The dispatcher resumes the same reviewer after
  its previous turn ends. Keep a clean response until deciding to continue or close;
  acknowledge before submitting another round.

Findings can be disputed with evidence in the next handoff. `NO_FINDINGS` applies only
to the submitted code. If closure fails, report it and resolve it before continuing.

At a clean endpoint, the completion authority chooses whether work continues. In reuse
mode, finish with `close-session` and `wait-for-close`; fresh mode has already closed
the last round. Closure during a pending review is cancellation, not approval.
If `wait-for-review` emits `session_closing`, stop work
and use `wait-for-close`; do not treat leftover feedback as a successful review.

## Reviewer worker

Review is **strictly static and read-only**. Read the source and supplied evidence;
never edit product code, build, compile, link, run tests, execute the program, or run
linters. The implementor owns execution. Concentrate on substantive correctness,
behavioral regressions, and violated task obligations. Potential compilation errors
can be findings, but mental compilation must not dominate the review.

Use `scripts/reviewer_loop.py`, always for the assigned session:

1. Run `read-request` once. It returns immediately; it never waits for future work.
2. On `review_request`, read the returned `message` and review the stated source.
   The message must identify the assigned coordination directory and session; report
   a mismatch without reviewing a guessed target.
3. Publish findings with `publish-response --message-file <absolute-file>` (or inline/
   stdin). With no actionable findings, publish only `NO_FINDINGS`. Metadata and prose
   must not accompany that sentinel. The script publishes before releasing the round.
4. On `review_ready_to_release`, run `release-review` to finish the existing response;
   do not review again or replace it.
5. After publication/release, end this turn. Return only a short completion notice
   naming the session to the dispatcher; findings belong in the channel, not the parent
   conversation. Do not wait, poll, or read another request. The dispatcher can resume
   this conversation for another round; a finished turn does not close the session.
6. On `no_request` or `session_closing`, end the turn. If a
   publishing command reports that the session is closing, end without publishing.

On a dispatcher stop instruction, stop any active tool process and end the turn.
Leave channel files untouched. Read relevant source and dependencies without repeatedly
dumping entire trees, diffs, or logs into context. Preserve task constraints,
unresolved findings and their disposition, and evidence pointers through the host's
supported compaction.

## Dispatcher

Use `scripts/dispatcher_loop.py` for every protocol operation. Use native runtime
tools only for creating, addressing, inspecting, resuming, and stopping workers.

Before starting, establish that creating a worker returns its handle while it remains
active, and that the host can inspect/stop workers and deliver worker-completion
notifications while the dispatcher listens. Establish whether completed conversations
can be resumed. A notification must let the dispatcher handle it without waiting for
a coordination-file event.
A synchronous spawn-and-collect runtime cannot support concurrent reviews.
Prefer resuming an existing conversation when supported; otherwise use the helper's
replacement decision. Do not assume arbitrary cross-parent resume support.
Honor caller-supplied compaction settings when supported; report unsupported settings
before launching. Do not silently replace a reusable conversation at an invented token
threshold or reduce its requested review effort.

Run `start --coordination-dir <dir>` on every start. It returns all open sessions for
recovery before normal listening. If a dispatcher marker remains, the operator must
stop the old dispatcher and explicitly request `revive`; then run `start --revive`.
When reviving in the same conversation, stop its old waiter before starting another.
The marker is operational bookkeeping, not a lease or proof of liveness. Accept
`revive` only in the dispatcher's conversation, never from an implementor's control file.

For each returned session or later listener event:

1. Report any `session_error` row and skip that session; do not infer a missing handle
   from unreadable state. Inspect other sessions' recorded handles using runtime tools.
   With no handle, use `gone`.
   Pass the observation to `reconcile --session <id> --worker-status <status>`.
2. Execute the returned `action`; the helper owns the lifecycle decision.
3. Record new handles through `bind`, and stop/failure outcomes through `reconcile`
   as described below. Report errors or replacements once, then service other sessions.

Runtime status inputs:

| Status | Meaning |
| --- | --- |
| `running` | The worker is currently executing, including finishing its response turn. |
| `resumable` | Execution ended and the same conversation can be resumed for pending work. |
| `stopped` | Worker and its tool processes are confirmed stopped. During closure/shutdown, this applies even if the conversation could later be resumed. During recovery, prefer `resumable` when available. |
| `gone` | Execution has stopped and no usable conversation remains. |
| `unknown` | The runtime explicitly does not recognize the handle; treat it as gone. |
| `error --error <details>` | The runtime call failed; this is not an unknown-handle answer. |

Actions:

| Action | Dispatcher duty |
| --- | --- |
| `launch` / `replace` | Create a worker with this skill, internal role, coordination directory, and session ID. Its task context comes through the channel. Immediately record the returned handle with `bind --worker-handle <handle>`. Report replacements. |
| `continue` | The current turn is already dispatched. Leave it running without a duplicate message or invocation. |
| `await_worker` | A new round arrived while the previous worker turn is finishing. Retain the pending request and defer it with `--busy-session <id>` until that worker's completion notification. Do not resume a running worker or poll its runtime status. |
| `resume` | Resume the same conversation for one round. A successful resume needs no further reconciliation; the helper already acknowledged dispatch. If it cannot be resumed and execution has stopped, reconcile as `stopped`; other failures use `error`. |
| `stop` | If the worker and its tool processes already ended, reconcile as `stopped`, even if the conversation is resumable; no extra runtime stop call is needed. Otherwise instruct it to stop and end, and use the runtime's stop/close operation as needed. Reconcile as `stopped` only after execution has stopped; otherwise report `error`. |
| `mark_closed` | The helper recorded closure. No new worker is needed. |
| `report` / `leave` | Report the supplied error, or leave the session unchanged. |

A pending close takes precedence over revival. An unknown handle with pending work
gets a replacement; an unknown handle on a closing session is marked closed. Retain
idle open conversations without launching or resuming anything until work arrives.
Start/revive re-enables dispatch for all open sessions and preserves published feedback.
Closed sessions stay closed. A failed launch/stop is left for operator `revive`, rather
than retried in a tight loop. If launch succeeds but recording its handle fails, stop
that new worker and report the failure.

Then run `wait --coordination-dir <dir>`. It returns on a new review request in any
session, a close request, or an unreported session error. Reconciliation acknowledges
a review dispatch before launch/resume, so the listener does not repeatedly report it.
Use `--busy-session <id>` for each `await_worker` session. These flags defer only review
dispatch, never closure or errors. On that worker's completion notification, stop and
collect the existing listener if necessary, remove the ID, inspect the worker, and
reconcile the session before listening again. Clear busy IDs on start/revive. If the
worker completed before you registered the deferral, use the already-received completion
notification or one immediate runtime observation; do not wait for a second notification.

Other normal worker completions need no resume. A failed worker, or one that ends with
its dispatched round still locked, is reported through `reconcile --worker-status error`
with `--error <details>` and left for revive. Do not repeatedly resume failed work.
A pending new round carrying `dispatch_requested: true` is distinct from that failure.
Keep dispatcher context limited to session IDs, runtime handles, lifecycle actions,
and brief errors; avoid reading review diffs or copying findings into this conversation.
For inspection, use `status`, optionally
with `--session`; it returns structured state without reading files manually.

Scans ignore stray files, invalid session-directory names, and symlinks. Broken sessions
produce `session_error` rows in the completed wait result, so hosts that buffer output
still surface them. Report the affected session for operator attention; never repair its
files manually. Pass each ID in the returned `reported_errors` list to the next wait as
`--reported-error <session-id>` (repeat the option for multiple IDs). Replace this list
after every returned wait. Already-reported broken sessions then remain quiet while
healthy sessions continue; the flags suppress only errors, never reviews or closure.
The waiter drops an ID when it observes that session repaired. Clear the list after
start/revive, or omit the flags to report current errors again. This uses conversation state,
not additional coordination files.

For service shutdown, use `status` and obtain fresh runtime observations for the
listed open workers. Pass a JSON mapping of session IDs to runtime statuses to
`shutdown --coordination-dir <dir> --statuses-stdin`. On `shutdown_pending`, execute
its `stop` actions, resolve/report failures, and call shutdown again with fresh statuses.
Only `service_stopped` means all workers stopped and the marker was removed. Shutdown
preserves otherwise open sessions and channel data for the next start. It does not
imply those reviews passed. Stop failures or unreadable session state leave shutdown
pending and the marker in place; healthy sessions are still processed.

## Delete closed sessions

When the operator requests cleanup, use:

~~~text
python3 "<skill-dir>/scripts/dispatcher_loop.py" cleanup-closed --coordination-dir /workspace
~~~

Run it after affected implementors and wrappers have finished reading their results
and confirming closure. It deletes the complete directories of confirmed closed
sessions, including handoffs and findings, so subsequent scans no longer visit them.
Open sessions and pending closes remain. The listener may keep running.

The command returns a deletion count and reports unreadable sessions or deletion
failures with a nonzero exit status. Rerun it to finish interrupted deletions; temporary
deletion directories are excluded from scans. There is no retained archive. Keep this
explicit maintenance separate from `close-session` and `wait-for-close`, since callers
still need those results to verify completion. Use scripts for cleanup, never shell
deletion or manual inspection of coordination files.

## Validation and scope

Run the Python tests with:

~~~text
python3 -m unittest discover -s "<skill-dir>/scripts" -p 'test_*.py'
~~~

The [TLA+ suite](verification/README.md) checks bounded publication,
dispatcher decisions, closure, shutdown/start/revive, and interrupted publication
recovery. Its session records are isolated by construction; the Python routing tests
provide evidence for concrete session isolation. For protocol changes, keep the model
and its bounds in sync and run `verification/check-all.sh` alongside the Python tests. Liveness is
conditional on a healthy service and fair external runtime operations; lost workers
may require operator `revive`. These checks do not prove filesystem check/write
atomicity or agent/runtime behavior. Actual agent exercises remain necessary.

## Example activations

- "Act as the review dispatcher in this workspace."
- "Implement this task and enter the review loop using the workspace dispatcher."
- "Use session-mode=reuse and continue session <id> with the next task."
- "Revive all open reviewer sessions, including idle ones."
