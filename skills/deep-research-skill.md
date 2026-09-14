# deep-research

**What it does.** Answers a hard factual question with a cited report you can trust. It
splits your question into five search angles, runs them in parallel, fetches the best
sources, pulls out *falsifiable* claims with supporting quotes, then puts every claim in
front of three skeptical verifiers whose job is to kill it. Two refutations and the claim
is dropped. What survives gets merged, ranked by confidence, and cited.

**How to use it.** It's a workflow, not a slash command:

```
Workflow({ name: 'deep-research', args: '<your question>' })
```

Narrow the question first. "What car should I buy" gets you nothing; "reliable 7-seat
hybrid under €40k, available in the EU in 2026" gets you a report. If the question is
vague, ask 2–3 clarifying questions and fold the answers into the args string.

**When to reach for it.** Questions where sources disagree and being wrong is expensive —
technology selection, benchmark claims, anything where vendor marketing pollutes the
search results. Expect roughly 100 agent calls per run, so it is not for quick lookups.

**One thing to know.** Its verifiers default to *refuting* when uncertain, the opposite of
`/code-review`'s. Claims are guilty until proven innocent here, so a thin result often
means the evidence really was thin — not that the harness failed.

---

> Description: *Deep research harness — fan-out web searches, fetch sources, adversarially
> verify claims, synthesize a cited report.*
>
> When to use: *When the user wants a deep, multi-source, fact-checked research report on
> any topic. BEFORE invoking, check if the question is specific enough to research directly
> — if underspecified (e.g., "what car to buy" without budget/use-case/region), ask 2-3
> clarifying questions to narrow scope. Then pass the refined question as args, weaving the
> answers in.*
>
> This is **not a slash command** — it is a Workflow, invoked as
> `Workflow({ name: 'deep-research', args: '<question>' })`.
>
> Unlike `/simplify` and `/code-review`, which are prompts, this is an executable
> orchestration script. The source comments note it was **"Ported from bughunter
> architecture. WebSearch/WebFetch instead of git/grep."** — the same lineage as
> `/code-review`.

---

## Pipeline

```
Scope → pipeline(Search → URL-dedup → Fetch+Extract) → 3-vote Verify → Synthesize
```

| Phase | Detail |
| --- | --- |
| Scope | Decompose question (from args) into 5 search angles |
| Search | 5 parallel WebSearch agents, one per angle |
| Fetch | URL-dedup, fetch top 15 sources, extract falsifiable claims |
| Verify | 3-vote adversarial verification per claim (need 2/3 refutes to kill) |
| Synthesize | Merge semantic dupes, rank by confidence, cite sources |

Note the **barrier placement**: Search → Fetch is a streaming pipeline with *no* barrier
(sources are fetched as each searcher returns), but Verify is deliberately gated. The
source comment says: *"Barrier here is intentional — claim pool must be fully assembled
before ranking/verification."*

### Budget constants

```js
const VOTES_PER_CLAIM = 3
const REFUTATIONS_REQUIRED = 2
const MAX_FETCH = 15
const MAX_VERIFY_CLAIMS = 25
```

Total agent calls: `1 + angles + sources + (claims × 3) + 1`. For a typical run that is
roughly 1 + 5 + 15 + 75 + 1 ≈ **97 agent calls**.

---

## Structured-output schemas

Every agent in the pipeline returns structured output against a JSON schema — there is no
free-text parsing anywhere in the harness.

```js
const SCOPE_SCHEMA = {
  type: "object", required: ["question", "angles", "summary"],
  properties: {
    question: { type: "string" },
    summary: { type: "string" },
    angles: { type: "array", minItems: 3, maxItems: 6, items: {
      type: "object", required: ["label", "query"],
      properties: {
        label: { type: "string" },
        query: { type: "string" },
        rationale: { type: "string" },
      },
    }},
  },
}

const SEARCH_SCHEMA = {
  type: "object", required: ["results"],
  properties: {
    results: { type: "array", maxItems: 6, items: {
      type: "object", required: ["url", "title", "relevance"],
      properties: {
        url: { type: "string" },
        title: { type: "string" },
        snippet: { type: "string" },
        relevance: { enum: ["high", "medium", "low"] },
      },
    }},
  },
}

const EXTRACT_SCHEMA = {
  type: "object", required: ["claims", "sourceQuality"],
  properties: {
    sourceQuality: { enum: ["primary", "secondary", "blog", "forum", "unreliable"] },
    publishDate: { type: "string" },
    claims: { type: "array", maxItems: 5, items: {
      type: "object", required: ["claim", "quote", "importance"],
      properties: {
        claim: { type: "string" },
        quote: { type: "string" },
        importance: { enum: ["central", "supporting", "tangential"] },
      },
    }},
  },
}

const VERDICT_SCHEMA = {
  type: "object", required: ["refuted", "evidence", "confidence"],
  properties: {
    refuted: { type: "boolean" },
    evidence: { type: "string" },
    confidence: { enum: ["high", "medium", "low"] },
    counterSource: { type: "string" },
  },
}

const REPORT_SCHEMA = {
  type: "object", required: ["summary", "findings", "caveats"],
  properties: {
    summary: { type: "string" },
    findings: { type: "array", items: {
      type: "object", required: ["claim", "confidence", "sources", "evidence"],
      properties: {
        claim: { type: "string" },
        confidence: { enum: ["high", "medium", "low"] },
        sources: { type: "array", items: { type: "string" } },
        evidence: { type: "string" },
        vote: { type: "string" },
      },
    }},
    caveats: { type: "string" },
    openQuestions: { type: "array", items: { type: "string" } },
  },
}
```

---

## Phase 0 — Scope

```
Decompose this research question into complementary search angles.

## Question
{QUESTION}

## Task
Generate 5 distinct web search queries that together cover the question from different angles. Pick angles that suit the question's domain. Examples:
- broad/primary · academic/technical · recent news · contrarian/skeptical · practitioner/implementation
- For medical: anatomy · common causes · serious differentials · authoritative refs · red flags
- For tech: state-of-art · benchmarks · limitations · industry adoption · cost/tradeoffs

Make queries specific enough to surface high-signal results. Avoid redundancy.
Return: the question (verbatim or lightly normalized), a 1-2 sentence decomposition strategy, and the angles.

Structured output only.
```

If no question is passed, the harness returns an error rather than guessing.

---

## Phase 1 — Search (one agent per angle)

```
## Web Searcher: {angle.label}

Research question: "{QUESTION}"

Your angle: **{angle.label}** — {angle.rationale}
Search query: `{angle.query}`

## Task
Use WebSearch with the query above (or a refined version). Return the top 4-6 most relevant results.
Rank by relevance to the ORIGINAL question, not just the search query. Skip obvious SEO spam/content farms.
Include a short snippet capturing why each result is relevant.

Structured output only.
```

### URL dedup and fetch budget

Results are sorted by relevance, then filtered through shared state that accumulates
*across* searchers as they complete:

```js
const normURL = u => {
  try {
    const p = new URL(u)
    return (p.hostname.replace(/^www\./, "") + p.pathname.replace(/\/$/, "")).toLowerCase()
  } catch { return u.toLowerCase() }
}
```

- Already-seen normalized URL → dropped as a dupe (recorded, not silently lost).
- Fetch budget exhausted (`fetchSlots <= 0`) **and** relevance is medium or low → dropped
  as budget-dropped. High-relevance results can still exceed the budget.

---

## Phase 2 — Fetch + Extract (one agent per novel source)

```
## Source Extractor

Research question: "{QUESTION}"

Fetch and extract key claims from this source:
**URL:** {source.url}
**Title:** {source.title}
**Found via:** {angle} search

## Task
1. Use WebFetch to retrieve the page content.
2. Assess source quality: primary research/institution? secondary reporting? blog/opinion? forum? unreliable?
3. Extract 2-5 FALSIFIABLE claims that bear on the research question. Each claim must:
   - be a concrete, checkable statement (not vague generalities)
   - include a direct quote from the source as support
   - be rated central/supporting/tangential to the research question
4. Note publish date if available.

If the fetch fails or the page is irrelevant/paywalled, return claims: [] and sourceQuality: "unreliable".

Structured output only.
```

### Claim ranking before verification

Claims are ranked by importance first, then source quality, and truncated to
`MAX_VERIFY_CLAIMS`:

```js
const impRank  = { central: 0, supporting: 1, tangential: 2 }
const qualRank = { primary: 0, secondary: 1, blog: 2, forum: 3, unreliable: 4 }
```

---

## Phase 3 — Verify (3-vote adversarial)

```
## Adversarial Claim Verifier (voter {v+1}/3)

Be SKEPTICAL. Try to REFUTE this claim. ≥2/3 refutations kill it.

## Research question
{QUESTION}

## Claim under review
"{claim.claim}"

**Source:** {claim.sourceUrl} ({claim.sourceQuality})
**Supporting quote:** "{claim.quote}"

## Checklist
1. Is the claim actually supported by the quote, or is it an overreach/misread?
2. WebSearch for contradicting evidence — does any credible source dispute or heavily qualify this?
3. Is the source quality sufficient for the claim's strength? (extraordinary claims need primary sources)
4. Is the claim outdated? (check dates — old claims about fast-moving fields are suspect)
5. Is this a marketing claim / press release / cherry-picked benchmark / forum speculation?

**refuted=true** if: unsupported by quote / contradicted / low-quality source for strong claim / outdated / marketing fluff.
**refuted=false** ONLY if: claim is well-supported, current, and source quality matches claim strength.
Default to refuted=true if uncertain.

Structured output only. Evidence MUST be specific.
```

Note the polarity: this verifier **defaults to refuting**, the opposite of `/code-review`'s
recall-biased verifier which defaults to PLAUSIBLE. Research claims are guilty until proven
innocent; code findings are innocent until proven guilty.

### Three-outcome tally

The harness distinguishes *refuted on merit* from *could not verify*. A null vote (user-skip
or agent error) counts as **no vote cast**, not as a refutation:

```js
const valid     = verdicts.filter(Boolean)
const refuted   = valid.filter(v => v.refuted).length
const errored   = VOTES_PER_CLAIM - valid.length
const survives  = valid.length >= REFUTATIONS_REQUIRED && refuted < REFUTATIONS_REQUIRED
const isRefuted = refuted >= REFUTATIONS_REQUIRED
```

The source comment is explicit about why: *"infra failure must not read as 'refuted'"*.

- **survives** — quorum of valid votes AND fewer than 2 refuting
- **isRefuted** — ≥2 refute votes (adjudicated against on merit)
- **otherwise** — unverified: too few valid votes to adjudicate (verifier agents errored)

If *every* verifier panel failed, the report says so in as many words:

> "Could not verify any claims — all N verifier panels failed (likely rate-limiting or API
> errors). This is an infrastructure failure, not a research finding. Raw extracted claims
> returned below; retry or verify manually."

---

## Phase 4 — Synthesize

Confirmed claims are formatted into a block (each with its vote tally, source, quality,
supporting quote, and the highest-confidence non-refuting verifier's evidence), followed by
a refuted block "for transparency" and an unverified block, then:

```
## Synthesis: research report

**Question:** {QUESTION}

{N} claims survived 3-vote adversarial verification. Merge semantic duplicates and synthesize.

## Confirmed claims
{block}
{killedBlock}{unverifiedBlock}

## Instructions
1. Identify claims that say the same thing — merge them, combine their sources.
2. Group related claims into coherent findings. Each finding should directly address the research question.
3. Assign confidence per finding: high (multiple primary sources, unanimous votes), medium (secondary sources or split votes), low (single source or blog-quality).
4. Write a 3-5 sentence executive summary answering the research question.
5. Note caveats: what's uncertain, what sources were weak, what time-sensitivity applies.
6. List 2-4 open questions that emerged but weren't answered.

Structured output only.
```

---

## Failure handling

The harness has a salvage path at every stage rather than throwing away the run:

| Failure | Behavior |
| --- | --- |
| No question in args | Error return, no agents spawned |
| Scope agent returns nothing | Error return |
| A source fetch throws | Recorded as `sourceQuality: "unreliable"`, `claims: []`; run continues |
| A source fetch is user-skipped | Dropped entirely (not mislabeled "unreliable") |
| Zero claims extracted | Returns stats and source list, no findings |
| Zero claims survive | Distinguishes "all refuted" from "all verifiers errored" |
| Synthesis agent fails | Returns the verified claims **raw and unmerged** rather than discarding the run |

## Returned payload

```js
{
  question, summary, findings, caveats, openQuestions,
  refuted:    [{ claim, vote, source }],
  unverified: [{ claim, erroredVotes, validVotes, source }],
  sources:    [{ url, quality, angle, claimCount }],
  stats: {
    angles, sourcesFetched, claimsExtracted, claimsVerified,
    confirmed, killed, unverified, afterSynthesis,
    urlDupes, budgetDropped, agentCalls,
  },
}
```
