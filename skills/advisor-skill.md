# advisor

**What it does.** Lets a smaller main model phone a friend. When Claude hits a hard call —
a complex decision, an ambiguous failure, a problem it keeps circling — it escalates to a
stronger model for guidance, then carries on with its answer. The escalation happens
server-side and costs extra tokens.

**How to use it.**

```
/advisor            # open the picker
/advisor opus       # set Opus as the advisor
/advisor off        # disable
```

The setting persists across sessions. The intended pairing is **Sonnet as your main model
with Opus as advisor** — near-Opus quality on some workloads at lower token cost.

**When to reach for it.** Only when you're running a smaller main model. The advisor must
be *more capable* than your main model or it silently never activates, so on Opus-main
there is nothing to escalate to and this does nothing.

**One thing to know.** This file is thin on purpose. Unlike the other skills here, there's
no prompt to extract — the client only validates the model name, checks the capability
ordering, and saves a setting. How the advisor is consulted and what it's asked lives on
the server.

---

> Description: *Let Claude consult a stronger model at key moments.*
> Argument hint: `[<model>|off]` · marked **experimental** in the UI.
>
> **This one is not a prompt.** Unlike every other skill in this set, `/advisor` has no
> extractable instruction text — it is a persisted setting (`advisorModel` in
> `userSettings`) that enables a server-side escalation path. There is nothing in the
> client binary describing *how* the advisor is consulted or what it is asked; that logic
> lives on the server. What follows is everything the client actually contains.

---

## What it does

The dialog's own description, verbatim:

> When Claude needs stronger judgment — a complex decision, an ambiguous failure, a problem
> it's circling without progress — it escalates to the advisor model for guidance, then
> resumes. The advisor runs server-side and uses additional tokens.

Recommended setup, verbatim from the dialog:

> **Recommended setup:** Sonnet as the main model with Opus as the advisor. For certain
> workloads this gives near-Opus performance with reduced token usage.

Linked reading: <https://claude.com/blog/the-advisor-strategy>

---

## Usage

| Command | Effect |
| --- | --- |
| `/advisor` | Open the picker dialog |
| `/advisor <model>` | Set that model as advisor |
| `/advisor off` (or `unset`) | Disable — clears `advisorModel` |

The setting persists to `userSettings` as `advisorModel`, so it survives across sessions.

---

## Activation rules

The advisor only fires when **both** conditions hold. The client checks these at set time
and warns you rather than failing silently:

1. **The main model must support the advisor.** Otherwise:

   > `Note: the current main model ({main}) does not support the advisor. It will activate
   > when you switch to a supported main model.`

2. **The advisor must be more capable than the main model.** Otherwise:

   > `Note: {advisor} is less capable than the current main model ({main}), so the advisor
   > will not activate. Choose a more capable advisor, or switch to a smaller main model.`

Invalid input produces `Invalid advisor model: {error}` or
`{model} cannot be used as an advisor. Valid options: {list}, off`.

---

## Why this is thin

The escalation decision, the prompt sent to the advisor, and how its guidance is folded
back into the main model's context are all server-side. The client's entire contribution
is: validate the model name, check the capability ordering against the current main model,
persist the setting, and render a dialog. There is no prompt to extract because the client
never writes one.

**Practical consequence:** if you are already running Opus as your main model, there is
nothing above it to escalate to, and rule 2 means the advisor will not activate. This is a
Sonnet-main feature.
