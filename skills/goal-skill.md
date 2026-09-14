# goal

**What it does.** Keeps Claude working until a condition you name is actually met. Every
time Claude tries to end a turn, a separate judge model reads the transcript and rules on
whether your condition holds. If it doesn't, work continues. You get a live panel showing
elapsed time, turns, tokens, and why the last check failed.

**How to use it.**

```
/goal pnpm verify exits 0 and all tests pass    # set it, work starts immediately
/goal                                            # show current goal and last check
/goal clear                                      # stop early
```

**When to reach for it.** Any "keep going until it's green" loop you'd otherwise drive by
hand — fixing a failing suite, chasing a flaky build, grinding through type errors.

**One thing to know.** The judge only sees the transcript; it can't run commands. So phrase
the goal as something that leaves evidence in the conversation — `pnpm verify exits 0`
works, "the code is correct" doesn't. When evidence is unclear it returns *not met*, so a
vague goal costs you extra turns rather than finishing early. It won't loop forever: a
genuinely impossible condition terminates, and Claude can't escape just by claiming defeat
— the judge treats that as evidence, not proof.

---

> Description: *Set a goal Claude checks before stopping* (non-interactive variant: *Set a
> goal — keep working until the condition is met*).
>
> Argument hint: `[<condition> | clear]`
>
> Unlike the other extracted skills, `/goal` is **not a prompt injected into your context**.
> It installs a `Stop`-event hook that runs a separate judge model against the transcript
> every time Claude tries to finish a turn. If the judge says the condition isn't met,
> the turn continues. The interesting content is the judge's system prompt, below.
>
> Requires a trusted workspace: *"/goal is only available in trusted workspaces. Restart,
> accept the trust dialog, and try again."*

---

## Usage

| Command | Effect |
| --- | --- |
| `/goal <condition>` | Set the stopping condition and immediately start working toward it |
| `/goal` | Show current goal, turn count, and last check reason |
| `/goal clear` | Clear the active goal |

The condition is length-capped; over the limit you get
`Goal condition is limited to N characters (got M)`.

While a goal is active the UI shows a panel with the condition, elapsed time, turn count,
tokens consumed since the goal was set, and the last check's reason. On success it renders
**Goal achieved** with the same stats.

---

## The judge

Each `Stop` (and `SubagentStop`) event fires a prompt hook. The user message is:

```
Based on the conversation transcript above, has the following stopping condition been satisfied? Answer based on transcript evidence only.

Condition: {condition}
```

### System prompt (Stop / SubagentStop variant)

```
You are evaluating a stop-condition hook in Claude Code. Read the conversation transcript carefully, then judge whether the user-provided condition is satisfied.

Your response must be a JSON object with one of these shapes:
- {"ok": true, "reason": "<quote evidence from the transcript that satisfies the condition>"}
- {"ok": false, "reason": "<quote what is missing or what blocks the condition>"}
- {"ok": false, "impossible": true, "reason": "<explain why the condition can never be satisfied>"}

Always include a "reason" field, quoting specific text from the transcript whenever possible. If the transcript does not contain clear evidence that the condition is satisfied, return {"ok": false, "reason": "insufficient evidence in transcript"}.

Only use {"ok": false, "impossible": true} when the condition is genuinely unachievable in this session — for example: the condition is self-contradictory, it depends on a resource or capability that is unavailable, or the assistant has explicitly tried, exhausted reasonable approaches, and stated it cannot be done. Apply your own judgment when deciding this — the assistant claiming the goal is impossible is evidence, not proof; independently confirm the condition is genuinely unachievable rather than deferring to the assistant's self-assessment. Do not use it just because the goal has not been reached yet or because progress is slow. When in doubt, return {"ok": false} without "impossible".
```

### System prompt (all other hook events)

```
You are evaluating a hook condition in Claude Code. Judge whether the user-provided condition is met.

Your response must be a JSON object with one of these shapes:
- {"ok": true, "reason": "<reason the condition is met>"}
- {"ok": false, "reason": "<reason the condition is not met>"}

Always include a "reason" field.
```

### Verdict schema

```js
{
  ok:         boolean,   // Whether the condition was met
  reason:     string?,   // Reason, if the condition was not met
  impossible: boolean?,  // Whether the condition can never be satisfied
                         // (only meaningful when ok is false)
}
```

The judge runs with `thinkingConfig: { type: "disabled" }`, no tools, and a 30-second
default timeout (configurable per hook via `timeout`, in seconds). It must call its
result tool **exactly once**:

> "Use this tool to return your verification result. You MUST call this tool exactly once
> at the end of your response."

---

## Notes

- **"Evidence, not proof"** is the load-bearing design decision. The judge is explicitly
  told not to accept the working assistant's own claim that a goal is impossible — it has
  to independently confirm it. This is what stops a loop from being trivially escapable by
  the model announcing defeat.
- **Transcript-only adjudication.** The judge cannot run commands or read files; it judges
  from what is quoted in the transcript. So a goal phrased as an observable event
  (`pnpm verify exits 0`) works far better than one phrased as a property of the world
  (`the code is correct`) — the former leaves evidence in the transcript, the latter
  doesn't.
- **Default is not-met.** Absent clear evidence, the judge returns
  `{"ok": false, "reason": "insufficient evidence in transcript"}`, so an ambiguous goal
  produces extra turns rather than a false finish.
- Escape hatches: `/goal clear` stops it early, and the three-outcome design means a
  genuinely impossible condition terminates instead of looping forever.
