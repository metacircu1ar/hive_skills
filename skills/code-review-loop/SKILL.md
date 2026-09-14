---
name: code-review-loop
description: "Coordinate one externally launched implementor and one externally launched static reviewer through script-private blocking file transitions. Invoke as reviewer, or as implementor with an optional completion authority."
metadata:
  argument-hint: "implementor [completion-authority=implementor|caller] | reviewer"
---

# Code Review Loop

Use this skill to coordinate exactly two externally launched agents through one shared coordination directory:

- **implementor** — changes the code, requests review, applies valid feedback, and repeats;
- **reviewer** — passively waits for requests, performs a strictly static read-only review of the identified repository and context, publishes findings or `NO_FINDINGS`, and remains available until its script reports session completion.

**Externally launched means launched by a caller outside both roles. It is not authorization for either role to launch the other.** An agent assigned `implementor` has authority to run only the implementor role. It must never create, spawn, delegate to, invoke, or simulate a reviewer or any substitute reviewer, even if subagent tools are available or the caller says only “start the review loop.” The same prohibition applies symmetrically to the reviewer.

## Invocation

Invoke this skill with exactly one role. Completion authority is an implementor-only input:

~~~text
/code-review-loop implementor
~~~

or:

~~~text
/code-review-loop reviewer
~~~

The invocation arguments are available as `$ARGUMENTS` on systems that support skill arguments.

Determine the role from the arguments or explicit value supplied by the caller. The only valid roles are `implementor` and `reviewer`.

For the implementor only, resolve omitted completion authority to `implementor`. The only valid explicit values are:

- `completion-authority=implementor` — the implementor decides when no work remains and closes the session itself;
- `completion-authority=caller` — the enclosing caller decides whether to continue with another work item or close the session. The implementor must not close it on its own.

The reviewer has no completion-authority input. Do not supply one to the reviewer, and the reviewer must not ask for, record, infer, or validate one. It waits for script-reported requests and completion regardless of who controls the implementor endpoint. If the role is missing or ambiguous, an implementor authority is invalid, or a reviewer invocation includes an authority, do not guess; stop and request valid invocation values.

For example, an epic that keeps one reviewer alive across several tasks invokes the implementor with `completion-authority=caller` and invokes the reviewer simply as `reviewer`. Each task ends at a clean work-item boundary; only the epic decides when to close the shared review session.

Once given a valid role, start that role immediately. Do not ask whether the opposite role is running, ready, or already launched, and do not wait for the caller to confirm its status. The implementor begins cleanup and implementation; the reviewer starts its blocking waiter.

## Required external launch order

This ordering is a safety requirement, not a convenience:

1. The external caller ensures that neither role from a previous loop remains active.
2. The external caller launches the implementor.
3. The implementor completes its one-time startup cleanup and explicitly reports that all six working files are absent from the coordination directory.
4. Only then does the external caller launch the passive reviewer. Do not launch both roles simultaneously.

The implementor is never the external caller for step 4. It reports cleanup completion and continues its own work; it does not call a subagent tool, agent launcher, wrapper, or another model to create the reviewer.

The files deliberately carry no IDs or generation tags, so they cannot distinguish an old live reviewer from the current one. A reviewer may accept a lock that already exists when it starts; this preserves delayed launch and reviewer-restart recovery, and is safe only under the required external launch order above.

The launch order is the external caller's responsibility. Stopping old roles before cleanup is mandatory because cleanup cannot stop an old process from recreating or republishing a protocol file afterward. Neither agent asks the caller or the opposite role to confirm that the order was followed; each starts its assigned behavior as soon as it is invoked.

## Working state files

At invocation, resolve the current working directory to an absolute path and keep it as the fixed **coordination directory** for the entire loop. All six working state files live directly in that directory:

- `.hive_skills_review_lock` — empty marker: a completed implementation snapshot is waiting for review.
- `.hive_skills_implementor_to_reviewer.txt` — implementor-authored review context. Its first publication is mandatory and contains the complete context handoff; later requests retain or atomically replace it with a complete current message.
- `.hive_skills_reviewer_to_implementor.txt` — reviewer-authored findings or the exact `NO_FINDINGS` signal.
- `.hive_skills_review_round_complete` — empty marker: the session controller has closed the whole review session through the implementor CLI and requests reviewer shutdown acknowledgement.
- `.hive_skills_implementor_to_reviewer.tmp` — temporary output for atomic implementor-channel publication.
- `.hive_skills_reviewer_to_implementor.tmp` — temporary output for atomic reviewer-channel publication.

These six paths are private implementation details of the role scripts. Neither role may inspect, list, search for, `stat`, test, read, write, truncate, rename, create, or remove them with filesystem or shell tools. Agents learn protocol state and incoming message bodies only from role-script JSON output and cause transitions only through role-script commands.

The coordination directory is not implicitly the repository root. It may be the repository root, a parent such as `/x` for a repository at `/x/repo1`, or an unrelated shared directory. Repository and context paths are supplied separately in the implementor message. Even if an agent changes its shell working directory to inspect the repository, every protocol-script invocation must continue using the captured absolute coordination directory. Never search for protocol state in the repository, its parents, its children, or any context directory.

The lock and completion marker are empty files. Human-readable text belongs only in the two `.txt` channels. Channel files contain only their message bodies; do not add protocol headers.

## Required protocol scripts

Use Python 3.9 or newer. The examples use `python3`; use the platform's equivalent Python 3 launcher, such as `python` or `py -3`, when needed. Resolve `<skill-dir>` to the directory containing this `SKILL.md`, and pass the captured absolute coordination directory as `<coordination-dir>`. The role entrypoints are:

- `<skill-dir>/scripts/implementor_loop.py`
- `<skill-dir>/scripts/reviewer_loop.py`

The scripts own every protocol read, publication, wait, validation, lock transition, acknowledgement, and cleanup operation. Their wait commands run silently in the foreground, inspect the six protocol paths once per second, and exit only after the requested state is actionable or a protocol error is detected. They use only the Python standard library; do not install Watchdog or substitute an OS-specific filesystem watcher.

A wait command returning a live process or session identifier is still running. Continue waiting on that exact process with the execution environment's wait/resume mechanism. Silence, an execution-tool yield, or an ordinary tool-call time limit is not a protocol result. **While the wait is unchanged, emit no commentary, progress report, status message, reassurance, or repeated “still waiting” text. Resume the same process silently.** Do not send a final response, start a second waiter, or leave the role. Only a completed process that exits zero with JSON `"status": "ready"` authorizes the next step. On a nonzero exit accompanied by JSON `"status": "error"`, report the protocol error. If the environment is known to have externally terminated a waiter without either record, including exit 130, immediately run the same wait command again against the same frozen state unless the operator explicitly stops the loop. Treat any other unstructured nonzero exit as a launcher or runtime failure: report it instead of retrying indefinitely.

Do not reproduce a wait with shell loops, manual sleeps, repeated file checks, Watchdog, `inotify`, or another agent-side polling mechanism. Do not use filesystem tools to inspect or mutate protocol paths for any reason, including diagnosis; invoke the owning role script and trust only its structured result.

Cleanup and transition commands are replay-safe for their documented state. If the execution environment is known to terminate one before it emits JSON, rerun that same command rather than finishing its file operations manually, except for `publish-response`: after an interrupted response publication, run `wait-for-request --participated`, which safely distinguishes an unpublished request, a published response awaiting unlock, a completed round, and a still-idle session. In particular, `complete` retains the clean reviewer response as a durable phase record and atomically promotes it to the empty completion marker, so interruption cannot strand an ambiguous all-files-absent pre-acknowledgement state.

## Script-owned protocol

- The implementor script alone creates the lock. The completion controller creates the completion marker only through the implementor CLI.
- The reviewer script alone removes the lock after publishing its complete response.
- The implementor script alone creates, refreshes, or replaces the implementor-to-reviewer channel.
- The reviewer script alone creates, refreshes, or replaces the reviewer-to-implementor channel.
- The implementor removes the reviewer final only through `acknowledge-feedback` or `complete`, after reading and fully consuming it. The reviewer never removes the implementor final.
- The implementor script may remove all six files during one-time startup cleanup. During final cleanup it makes the other five paths absent, atomically promoting the clean reviewer final into the completion marker, and leaves completion-marker removal to the reviewer script.
- The reviewer that participated in this loop removes the completion marker through `acknowledge-completion` and then terminates.

Outbound messages enter the scripts through `--message-stdin`, `--message-file <absolute-path>`, or `--message <text>`. Prefer standard input for generated multi-line messages and `--message-file` for an already-existing message source. The script writes the temporary channel, validates the transition, and atomically promotes it. Never reproduce those operations manually.

The channels have opposite lock polarity: the implementor publishes only while the lock is absent; the reviewer publishes only while the lock exists.

## Mandatory invariants

1. The implementor does not modify implementation files or its outbound channel while the lock exists.
2. Apart from publishing its response and removing protocol markers as specified here, the reviewer never modifies repository or context files and performs only static inspection.
3. Every review request carries a complete implementor final, and the reviewer reads and considers it before reviewing.
4. The implementor reads and considers the reviewer final before editing after a review.
5. The reviewer atomically publishes findings or `NO_FINDINGS` before removing the lock.
6. The implementor does not read reviewer feedback while the lock exists.
7. Each logical request receives exactly one reviewer decision. Recreating a missing, unclaimed lock continues the same request and frozen snapshot.
8. A reviewer that cannot finish leaves the lock and does not publish a decision.
9. The implementor or its caller publishes completion through the implementor CLI only after consuming `NO_FINDINGS` and deciding that no session work remains. The CLI first makes the four paths other than the reviewer final and completion marker absent, then atomically promotes that final into the marker. The reviewer removes the marker; the completion controller observes that acknowledgement.
10. The implementor message present when the lock is created remains unchanged until the reviewer decides.
11. The reviewer message remains unchanged after unlock until the implementor consumes it.
12. A new lock is never created while a temp file or reviewer final remains.
13. `NO_FINDINGS` means only that the submitted snapshot is clean. It does not end the loop while planned work remains.
14. The first implementor message identifies the fixed coordination directory, repository, and every needed context directory by absolute path, and supplies the full task text unless an identified context source already contains it.
15. Neither role asks for confirmation of the opposite role's status; a valid invocation starts its assigned behavior immediately.
16. Neither role launches, creates, delegates to, or simulates the opposite role. Only the external caller launches agents.
17. Agents never inspect or mutate protocol files and never perform their own polling or cleanup. A role remains active and silent while its blocking wait process is running and advances only after the script emits a ready result.
18. Completing a reviewed work item does not close a caller-owned session. Only the implementor's resolved completion authority decides between acknowledging the clean response to continue and publishing session completion.

---

# Role: implementor

Follow this section only for the `implementor` role.

## No reviewer-launch authority

The implementor role does not include orchestration authority. **Never call `spawn_agent`, a subagent tool, an agent CLI, a wrapper, or another model to create or act as the reviewer.** “Two externally launched roles” means the external caller launches two independent agents; it never means the implementor launches its counterpart. After reporting startup cleanup, continue implementing and eventually block in `wait-for-review`; reviewer absence is not permission to manufacture one.

## One-time startup cleanup

Before inspecting or changing the implementation, treat all existing working files as stale and run:

~~~text
python3 "<skill-dir>/scripts/implementor_loop.py" startup-cleanup --coordination-dir "<coordination-dir>"
~~~

The command removes only the six protocol paths, removes the completion marker last, verifies that all six are absent, and emits `startup_cleanup_complete`. Report that startup cleanup in the captured coordination directory is complete, then begin implementation work. Do not ask whether the reviewer is running or wait for confirmation about it.

Perform this cleanup exactly once. It removes stale files but cannot stop an old agent, which is why the external caller must ensure that no reviewer from a previous loop remains active.

## Implement and prepare context

1. Understand the task and existing behavior.
2. Implement the requested change.
3. Run relevant tests, linters, type checks, static analysis, or other practical checks.
4. Inspect staged, unstaged, and relevant untracked changes and make the tree coherent and reviewable.
5. Do not create the lock while still editing or testing.

### Publish the initial context handoff

Before the first review request, publish a mandatory, self-contained implementor message while the lock is absent. Its body must include:

- **Coordination directory:** the resolved absolute path captured from the implementor's initial current working directory. State explicitly that role scripts use protocol state only there.
- **Repository:** the resolved absolute path to the repository being reviewed. Do not use `~`, environment-variable shorthand, or a relative path.
- **Context directories:** the resolved absolute path of every directory the reviewer needs beyond the repository, with a short statement of what it contains. Include relevant evidence, log, crash-dump, reproduction, task-bundle, fixture, or other data directories. Write `None` when no additional directory is needed.
- **Task:** either the full task text or the resolved absolute path to the exact context file or files that contain the full task. A directory path alone is not a task source; identify the file and where the operative task can be found. Include the full text directly when it exists only in conversation or was not supplied through a context directory.
- **Review target and evidence:** what implementation or snapshot is being submitted, the relevant base or comparison when known, checks already run, and the evidence most useful for judging it.
- **Implementor notes:** constraints, preserved behavior, known limitations, uncertain assumptions, responses to prior discussion, or any other information the implementor considers important for this review.

Point to large logs, dumps, or evidence by absolute directory and useful filenames instead of copying their full contents into the channel. Do not omit task-relevant context merely because it is large; give the reviewer enough location and interpretation detail to inspect it.

Feed the complete body to the publication command through standard input:

~~~text
python3 "<skill-dir>/scripts/implementor_loop.py" publish-context --coordination-dir "<coordination-dir>" --message-stdin
~~~

The command atomically publishes and verifies the context. Alternatively pass `--message-file <absolute-path>` for an existing UTF-8 source or `--message <text>` for a short body. Do not create, inspect, or verify the protocol files yourself.

### Maintain context on later requests

The implementor context remains present for every later request. If the stable context and current notes remain accurate, leave it unchanged. If anything material changes, replace it after acknowledging the prior feedback by running `publish-context` with one complete updated body. A replacement must preserve the coordination-directory path, repository path, context-directory paths, and task source or full task text from the initial handoff while adding the current diff explanation, validation evidence, feedback response, disagreement, or other round-specific notes.

## Request review

After the implementation and published context are complete and current, request review only through:

~~~text
python3 "<skill-dir>/scripts/implementor_loop.py" request-review --coordination-dir "<coordination-dir>"
~~~

The command validates all preconditions, creates the empty lock, and is replay-safe if its ready output was lost. After `review_requested`, freeze the implementation and context until the reviewer decides.

## Wait for review

While the lock exists, do not modify the implementation or either channel. Run this command in the foreground and remain in the loop until it finishes:

~~~text
python3 "<skill-dir>/scripts/implementor_loop.py" wait-for-review --coordination-dir "<coordination-dir>"
~~~

The command waits once per second without returning control after each poll. It exits ready only when the lock is absent and complete feedback exists. It also recreates a missing lock for the same frozen request when no reviewer publication exists and reports invalid transitional states as protocol errors. Stay completely silent while it runs. After `review_result`, take the complete feedback from the JSON `message` field into account before editing; do not read a protocol file.

Only a result whose JSON `result_kind` is `no_findings` is clean; text that merely mentions `NO_FINDINGS` is ordinary feedback.

## Handle reviewer feedback

For every finding or nit:

1. Understand the underlying issue.
2. Apply feedback that is correct, relevant, safe, and consistent with the task.
3. Do not blindly implement incorrect, contradictory, unsafe, misunderstood, or out-of-scope feedback.
4. If a suggestion is unsuitable but identifies a real issue, fix the underlying issue appropriately.
5. Preserve intended behavior and project conventions unless the feedback establishes a reason to change them.

After fully consuming findings, or after fully consuming `NO_FINDINGS` when another session work item remains, acknowledge the reviewer final through the script:

~~~text
python3 "<skill-dir>/scripts/implementor_loop.py" acknowledge-feedback --coordination-dir "<coordination-dir>"
~~~

Then:

1. Complete the next phase if applicable, run relevant checks, and inspect the tree.
2. Keep the implementor context unchanged when it remains current, or replace it with a complete updated message through `publish-context`.
3. Run `request-review`, freeze the snapshot, and run `wait-for-review` again.

Repeat until the current work item is complete and the latest response is `NO_FINDINGS`. Then apply the completion-authority rule below.

## Finish or hand back the session

After `wait-for-review` returns `result_kind: no_findings`, choose the next transition according to the implementor's resolved completion authority:

- With `completion-authority=implementor`, decide whether session work remains. If it does, run `acknowledge-feedback` and continue. If it does not, close the session as described below.
- With `completion-authority=caller`, do not decide or close the session. Leave protocol state unchanged, report that the work item is clean, and return control to the caller. The caller must then make exactly one of these transitions through the implementor CLI: run `acknowledge-feedback` before starting the next work item, or run `complete` to close the whole session. Until the caller makes that choice, do not edit implementation files, publish context, request review, or publish completion.

To continue a caller-owned session, the caller must run `acknowledge-feedback` and resume the same already-initialized implementor role in the same coordination directory. The resumed role continues with the next work item and must not repeat one-time startup cleanup. Do not launch a fresh implementor role into a live session; if the existing role cannot be resumed, close the session and start a new one using the required launch order.

Only the declared completion authority may close the session. After it has consumed `NO_FINDINGS` and decided that no session work remains, it runs:

~~~text
python3 "<skill-dir>/scripts/implementor_loop.py" complete --coordination-dir "<coordination-dir>"
~~~

The command requires the unlocked reviewer final to contain exactly `NO_FINDINGS` on its first run, performs final cleanup, empties that retained response, and atomically renames it to the completion marker after the other four paths are absent. A replay resumes from the retained final, an already-published marker, or an already-acknowledged all-absent state. This is why caller-owned work returns before acknowledging its final clean response: the caller must retain the choice between continuing and closing. After `complete`, make no further mutation and block for acknowledgement:

~~~text
python3 "<skill-dir>/scripts/implementor_loop.py" wait-for-completion --coordination-dir "<coordination-dir>"
~~~

Exit the session only after the command emits `completion_acknowledged` and verifies that all six protocol files are absent. In caller-owned mode, the caller performs both `complete` and `wait-for-completion`; the implementor work-item invocation has already returned without terminating the reviewer.

## Implementor must never

- Spawn, create, delegate to, invoke, or simulate a reviewer or reviewer substitute by any means. Request review only through `request-review`.
- Ask whether the reviewer is running, ready, or launched, or wait for confirmation of its status.
- Inspect, list, search for, read, create, write, truncate, rename, or remove any protocol file directly.
- Publish completion without being the declared completion authority, before consuming `NO_FINDINGS`, while session work remains, or except through the CLI's ordered cleanup and atomic reviewer-final promotion.
- Edit implementation files or replace the implementor context while `wait-for-review` is active.
- Poll protocol state, sleep between checks, or duplicate a protocol-script transition.
- Emit status or progress messages while a wait command remains active and unchanged.
- Interpret missing feedback, an empty message, `NO_CHANGES`, or text merely containing `NO_FINDINGS` as the clean sentinel.

---

# Role: reviewer

Follow this section only for the `reviewer` role.

## Wait for a request

Start immediately without asking whether the implementor is running, ready, or finished with startup. Do not review speculatively or inspect any other directory for protocol state.

Before accepting the first request, run this foreground command:

~~~text
python3 "<skill-dir>/scripts/reviewer_loop.py" wait-for-request --coordination-dir "<coordination-dir>" --fresh
~~~

After accepting any request in this invocation, use `--participated` instead of `--fresh` for every later wait:

~~~text
python3 "<skill-dir>/scripts/reviewer_loop.py" wait-for-request --coordination-dir "<coordination-dir>" --participated
~~~

Each command remains blocked and checks once per second until it emits `review_request`, `review_ready_to_release`, or, only for a participating reviewer, `completion`. A fresh reviewer never acknowledges a completion marker from a loop it did not join; a marker that remains in that state for 90 seconds produces a protocol error.

Remain completely silent while either waiter is active and unchanged. On `review_request`, remember that this invocation has participated and review exactly one frozen snapshot using the complete handoff in the JSON `message` field. `review_ready_to_release` means a prior reviewer invocation atomically published a complete response but was interrupted before unlocking. Do not inspect or repeat that response; remember participation, run `release-review`, and return silently to `wait-for-request --participated`. On `completion`, run:

~~~text
python3 "<skill-dir>/scripts/reviewer_loop.py" acknowledge-completion --coordination-dir "<coordination-dir>" --participated
~~~

Then verify the ready result and terminate.

## Review a request

Treat the submitted implementation and context as frozen until response publication succeeds or aborts.

1. Take the coordination-directory path, repository path, context paths, task, constraints, evidence, and notes from the script-returned message into account. Evaluate them against the code and requirements; do not assume they are correct.
2. Confirm that the message's coordination-directory path is exactly the directory captured at invocation. If it differs, do not publish; report an invalid snapshot. Never switch directories or search for another protocol state.
3. Inspect the repository identified in the message; do not assume it is the coordination directory. Read its version-control state, staged and unstaged changes relative to the appropriate base, relevant untracked implementation files, and enough surrounding code and tests as text to understand the effect. Use only non-mutating inspection. For Git, disable optional locks, pagers, fsmonitor, external diffs, and textconv helpers: use the execution environment to set `GIT_OPTIONAL_LOCKS=0`, pass `--no-pager -c core.fsmonitor=false` before the Git subcommand, and pass `--no-ext-diff --no-textconv` to diff-producing subcommands. Do not invoke a configured helper merely to inspect text.
4. Never modify repository or context files and never execute project code or a validation tool against it.

This is a completely static review. Do not run tests, builds, compilers, linkers, type-checkers, linters, formatters, code generators, package-manager commands, migrations, benchmarks, fuzzers, project scripts, project binaries, or any command intended to determine whether the implementation executes or validates successfully. Read existing test code and implementor-supplied results as evidence, but leave all compilation and dynamic validation to the implementor.

Concentrate review effort on substantive correctness: whether the implementation fundamentally satisfies the task, preserves required behavior and invariants, and handles data flow, state transitions, boundaries, failure modes, concurrency, security, and compatibility correctly. Potential syntax, type, linking, or compilation issues are **trivial** in this workflow. Classify any such note as `Trivial` and mention it briefly only when it is obvious; do not spend material time mentally compiling the source, reconstructing toolchain diagnostics, or making compilation confidence a review-completion gate.

Review until the frozen snapshot has no substantive comment or genuine static nit you would reasonably ask the implementor to address. Do not invent findings to keep the loop running.

## Publish reviewer feedback

Every accepted request produces exactly one response. With findings, use the complete findings as the message body. With no findings or nits, make the entire body exactly `NO_FINDINGS` with no other commentary. Feed it through standard input to:

~~~text
python3 "<skill-dir>/scripts/reviewer_loop.py" publish-response --coordination-dir "<coordination-dir>" --message-stdin
~~~

The command owns temporary-file cleanup, atomic publication, validation, and unlock. Alternatively pass `--message-file <absolute-path>` for an existing UTF-8 source or `--message <text>` for a short body. On `response_published`, return silently to `wait-for-request --participated`. On `response_aborted`, the request was withdrawn before publication; also return silently to the waiter without inspecting protocol files or publishing again unless a new request arrives.

Publishing before unlocking is mandatory for both findings and `NO_FINDINGS`. If review or publication cannot finish, leave the lock in place. Neither `NO_FINDINGS` nor unlocking terminates the reviewer.

## Reviewer must never

- Spawn, delegate to, invoke, or simulate an implementor.
- Ask whether the implementor is running, ready, or launched, or wait for confirmation of its status.
- Inspect, list, search for, read, create, write, truncate, rename, or remove any protocol file directly.
- Modify implementation files or apply its own suggestions.
- Run tests, builds, compilation, linking, type-checking, linting, formatting, generation, package operations, project scripts or binaries, or any other dynamic validation.
- Write to the repository or any context/evidence path; its only writes are protocol transitions performed internally by the reviewer script.
- Poll protocol state, sleep between checks, or duplicate a protocol-script transition.
- Emit status or progress messages while a wait command remains active and unchanged.
- Use `NO_CHANGES`, an empty file, or missing feedback instead of the exact `NO_FINDINGS` body.

---

# State-machine summary

~~~text
IMPLEMENTOR removes all stale working files once
IMPLEMENTOR edits/tests and publishes the complete initial context atomically
IMPLEMENTOR creates an empty lock and freezes
REVIEWER reads the mandatory context and performs a static read-only review
REVIEWER atomically publishes findings or NO_FINDINGS
REVIEWER releases the lock and starts the next blocking waiter
IMPLEMENTOR reads and consumes the response

if session work remains:
  IMPLEMENTOR implements the next phase and requests another review

if the current work item is clean and control returns to an enclosing caller:
  IMPLEMENTOR leaves the unlocked NO_FINDINGS response in place
  CALLER either acknowledges it and starts another work item, or closes the session

if the session controller decides the session is complete after NO_FINDINGS:
  CONTROLLER invokes the implementor CLI to remove the other files
  CONTROLLER atomically promotes the emptied clean response to the completion marker last
  REVIEWER removes the marker and exits
  CONTROLLER observes the acknowledgement and exits the session
~~~

# Failure behavior

- Any files at implementor startup: `startup-cleanup` removes the exact six paths, completion marker last.
- Lock disappears without reviewer temp or final: the running `wait-for-review` process confirms the state on its next one-second poll, recreates the lock for the same frozen request, and keeps waiting.
- Lock disappears with reviewer temp: `wait-for-review` keeps polling internally for up to 90 seconds, then reports a protocol error if the temp remains.
- A participating reviewer restarts after lock loss with only its unpublished temp remaining: `wait-for-request --participated` removes that owned orphan temp and continues waiting; a fresh reviewer never claims or removes it.
- A complete reviewer final remains under the lock after reviewer interruption: `wait-for-request` emits `review_ready_to_release`; the reviewer releases that existing decision without replacing or repeating it.
- Implementor temp exists with a lock: reviewer leaves state unchanged and reports an invalid snapshot.
- Implementor final is missing with a lock: reviewer leaves state unchanged and reports an invalid snapshot.
- Implementor message names a different coordination directory: reviewer leaves state unchanged and reports an invalid snapshot.
- Reviewer cannot finish: leave the lock and do not publish a decision.
- `NO_FINDINGS` with session work remaining: the implementor authority acknowledges it and continues; a caller authority chooses whether to acknowledge it and continue or close the session.
- Completion acknowledgement has not arrived: `wait-for-completion` remains blocked; do not exit merely because time passed.
- Reviewer sees completion before accepting any lock: `wait-for-request --fresh` leaves the marker unchanged and reports a protocol error if it remains for 90 seconds.
- A wait command is still running or the execution tool yields a live session: continue that same process; this is not a reason to terminate the role.
- A wait process is known to have been externally terminated without a ready or error record: restart the same wait against the unchanged protocol state.
- A role script exits nonzero with a JSON error: stop the affected transition and report it; do not imitate the failed cleanup manually. Restart a non-JSON failure only when the execution environment confirms external waiter termination; otherwise report the launcher or runtime failure.
- Missing or invalid role: stop and request `implementor` or `reviewer`. An omitted implementor completion authority defaults to `implementor`; the reviewer accepts no completion-authority argument.

# Formal verification

This protocol is modeled in the checked [TLA+ source](verification/CodeReviewLoop.tla). The model uses clean abstract file names without the skill's `.hive_skills_` prefix.

The model covers arbitrary stale-file startup cleanup, delayed external reviewer launch, mandatory implementor context on every request with a required initial publication and later reuse or atomic refresh, incoming-message read gates, snapshot freezing, findings-or-`NO_FINDINGS` publication before unlock, bounded lock loss and same-snapshot retry, another planned phase after `NO_FINDINGS`, final cleanup and completion publication through the implementor CLI, reviewer acknowledgement, and clean termination. The caller-versus-implementor decision authority is a control-plane choice outside the file-state model; both choices use the same verified completion transition. TLC verifies the common file transition after an authorized close decision, not authority selection, caller handback, or the promise that an implementor will not close a caller-owned session.

The Python role scripts are the concrete implementation of the model's wait, recovery, cleanup, unlock, and completion-acknowledgement transitions. The model abstracts the scripts' internal one-second polls because those polls do not change protocol state.

The model assumes both agents follow the protocol and that external orchestration does not overlap a new loop with an old reviewer. It treats the fixed coordination directory as one abstract file namespace and a reviewer decision as an abstract transition; absolute-path equality, static-only inspection, agent noncompliance, process termination by the execution environment, old-agent interference, semantic understanding of messages, and documented timeout/failure branches remain outside the abstraction as detailed in the [verification README](verification/README.md).

When changing protocol states, file ownership, message lifecycle, publication order, recovery, or cleanup, update the model and run `verification/run-tlc.sh`, `verification/check-state-space.sh`, `verification/check-early-unlock.sh`, `verification/check-temp-file-unlock.sh`, and `verification/check-cleanup-order.sh`. The change is incomplete until the normal model passes, state-space statistics match, and all negative checks report their expected violations.
