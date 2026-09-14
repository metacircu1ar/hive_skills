# testable-frontend

**What it does.** Tells you how to build a frontend that is _testable by construction_ —
so that fast, deterministic tests (from pure-unit up to real-browser end-to-end) are cheap
to write and rarely flaky — and how to write each tier of tests once the code is shaped
right. The central claim: **testability is an architecture property, not a test-writing
effort.** If tests are hard to write, fix the code, not the test.

**When to reach for it.** Starting or reviewing a web frontend (SPA/control plane/dashboard)
where you want durable automated coverage instead of manual click-throughs; deciding how to
mock a backend; setting up component / browser-E2E / full-stack tiers; or auditing an
existing UI for why its tests are painful.

**Stack this was distilled from.** React + Vite + TypeScript (strict) + a generated
typed API client + React Query + MSW + Playwright + Vitest/RTL. The _principles_ are
framework-agnostic; each section names the principle first, then the concrete mechanism.

---

## Part 1 — Write the code so it is testable

These are in priority order. The first three matter most; get them wrong and no amount of
test tooling saves you.

### 1.1 One typed network seam — same-origin, contract-validated

- **Principle:** all server communication goes through a **single client object**, not
  scattered `fetch`/`axios` calls. There is exactly one place the app touches the network.
- **Do:**
  - Route every request through one `ApiClient` (or equivalent) injected into the app.
  - Make the base URL **same-origin** (`''`) in production. Same-origin means a test mocks
    `/v1/*` with zero CORS/base-URL gymnastics. Do not scatter absolute hosts.
  - **Validate every response against a generated schema/decoder** (OpenAPI → typed
    decoders, zod, io-ts). This makes the wire contract explicit and runtime-enforced.
- **Why it makes testing easy:** one seam = one mock point. The decoders double as a spec
  you read to build correct fixtures, and a test whose mock passes the decoder is exercising
  the _real_ response shape, not a hand-wave. (In practice, matching the decoders is ~80% of
  mock-building — treat that as a feature, not friction: it keeps mocks honest.)
- **Anti-pattern:** components calling `fetch` directly; per-feature bespoke clients;
  responses consumed as `any`.

### 1.2 Inversion of control — inject everything via context/props

- **Principle:** components depend on _abstractions passed in_, never on module-level
  singletons or global side effects.
- **Do:**
  - Provide the API client, query client, runtime config, router, toasts, analytics,
    auth/re-auth, clock — all through React Context providers (or props).
  - Build a `renderWithProviders(ui, { api, queryClient, route, me })` test helper that
    composes the _production_ provider stack with swappable dependencies.
  - No work at import time. App boot is an explicit function you can gate/intercept.
- **Why:** this is the single biggest enabler. A test swaps the entire backend by injecting
  one fake client or slotting one mock worker in at the boot gate. Nothing reaches for a
  global, so nothing needs monkey-patching.
- **Anti-pattern:** `import { apiClient } from './singleton'`; `window.__store__`; effects
  that fire on module load.

### 1.3 Server-authoritative thin client

- **Principle:** the UI invents as little business logic as possible. It renders as a
  (near) pure function of server state: `render(serverState) → UI`.
- **Do:**
  - Derive permissions/capabilities from the server (e.g. a `viewerCapabilities` object or
    a `/me` permissions list) and _gate UI on that_, not on client-side guesses.
  - Every status shown must correspond to real server state — no invented "probably fine"
    indicators.
  - Keep decisions (validation, authorization, concurrency) on the server; the client
    submits intent and reflects the result.
- **Why:** a pure `state → UI` function is the easiest thing in the world to test — feed a
  response, assert the render. Permission-gating tests become "return capabilities X, assert
  affordance Y hidden."
- **Anti-pattern:** client-side role logic that can diverge from the server; optimistic UI
  with no server-confirmation path to assert.

### 1.4 Isolate hard stateful logic into pure reducers/state machines

- **Principle:** the trickiest logic — live/streaming state, optimistic editing, undo/redo,
  reconnection — belongs in **pure `(state, action) → state` functions**, separated from
  I/O.
- **Do:**
  - Model live projections (SSE/websocket) as a reducer over events; model an editor as a
    plan/store with explicit actions (stage, validate, decide, commit, undo, rebase).
  - Keep these reducers free of fetch/timers/DOM. Feed them event/action fixtures.
  - Cover them with **property/model-based tests** (fast-check): generate adversarial event
    streams (duplicate, reordered, malformed) and assert invariants (idempotence, bounded
    windows, no negative counts, monotonic versions).
- **Why:** the hardest behavior becomes deterministic unit tests with zero browser. The
  costly integration tiers then only need to check the wiring, not the logic.

### 1.5 Standardize server state through a query cache

- **Do:** use one server-state library (React Query/SWR) for all reads. Disable retries and
  set an infinite gc time in tests for determinism. Tests can pre-seed the cache
  (`setQueryData`) _or_ let the network mock serve — both are trivial with one cache.
- **Why:** no ad-hoc data fetching or manual loading flags in components to reproduce.

### 1.6 URL-as-state, routes-as-data

- **Do:** put view state in the URL (`?q=`, `?view=`, `?mode=`); export route definitions as
  data; make everything deep-linkable and reload-safe. A command palette is a route registry.
- **Why:** navigation is testable by URL + real links; "state survives refresh" and
  "deep-link restores context" become real assertions, not mock theater.

### 1.7 Accessible, semantic markup — testability IS accessibility

- **Do:** label every input, use correct roles (`dialog`, `alert`, `searchbox`,
  `navigation`, `tab`, `option`), give regions accessible names, use `aria-live` for async
  status. Run axe in tests.
- **Why:** tests query by **role/label/text** (`getByRole('dialog')`,
  `getByLabel('Password')`) — stable, refactor-proof, and semantically meaningful — instead
  of brittle CSS/`data-testid`. The exact properties that make the app usable by a screen
  reader make it queryable by a test. Reach for `data-testid` only as a last resort.

### 1.8 Typed error contract + error boundaries

- **Do:** represent errors as a typed class/shape (e.g. `ApiProblemError` with
  status/code/detail); contain failures with error boundaries; give error states real
  semantics ("Page not found", `role="alert"`, a recover action).
- **Why:** the unhappy paths (401/403/409/500/malformed) become as assertable as the happy
  ones, and a thrown error never white-screens the app under test.

### 1.9 Deterministic seams for time, ids, randomness, workers

- **Do:** inject the clock (`clock?: () => number`), id generator, and RNG where behavior
  depends on them. Give web workers a main-thread fallback
  (`if (typeof Worker === 'undefined')`). Make idempotency keys stable/derivable.
- **Why:** deterministic tests. Non-injected `Date.now()`/`Math.random()`/workers are the
  usual flake sources.

### 1.10 Feature-sliced modules with enforced boundaries

- **Do:** organize by feature (`features/`, `routes/`, `app/`, `components/ui/`, `lib/`);
  enforce import boundaries and a file-size cap with lint rules (`no-restricted-imports`,
  `max-lines`); extract shared primitives/hooks.
- **Why:** cohesive, decomposed units are individually testable; boundaries stop a test for
  one feature from dragging in half the app.

### 1.11 The one hard island: imperative canvas / workers / animation

- **Reality:** graph canvases (React Flow), D3 layout in a **web worker**, and animations are
  the opposite of everything above — stateful, imperative, environment-sensitive. Synthetic
  data will trip them (a layout worker throws on a malformed/forest topology while the rest of
  the page renders fine).
- **Do:**
  - Push all decision logic _out_ of the canvas into pure functions (projection, selection,
    parent-derivation) and test _those_ directly.
  - For the imperative shell: in mock/E2E tests use an **empty-but-valid** or a **known-real**
    fixture, and assert the chrome around it (search, panels, empty state), not internal
    node geometry.
  - Test the visual island separately with **pixel/visual regression** (Playwright
    screenshots) and pin snapshots per-platform (skip off the baseline OS).
  - Keep the canvas out of critical-path assertions in functional tests.

---

## Part 2 — The test tiers, and when to use each

Think trophy, not pyramid: a fat middle of integration-style tests, thin ends.

| Tier | Path under test | Speed | Use it for |
| --- | --- | --- | --- |
| **Pure unit** | reducers, selectors, utils (no DOM) | instant | the hard state logic (§1.4), property tests |
| **Component / route** | click → **mocked** network, JSDOM | fast | the bulk of UI behavior, per route/feature |
| **Browser E2E (mock-backed)** | real browser → **mocked** network, no backend | fast-ish | real rendering + cross-component journeys, a11y, real SSE/EventSource shape |
| **Full-stack E2E** | real browser → **real server → real DB** | slow | a thin, curated deploy/seam gate |
| **Backend integration** | HTTP → **real DB** (no browser) | medium | correctness that lives in SQL/RLS/locks (complements the UI tiers) |

**Rules of thumb**

- Put **breadth** in component + browser-mock tiers. They prove _UI behavior_.
- Put the **hardest logic** in pure unit tests (property-based).
- Keep **full-stack thin** (single digits to low teens). It is your deploy/seam gate, not a
  coverage tier — a broad, flaky full-stack suite is _negative_ value.
- Remember what each tier does **not** prove: mock tiers prove UI behavior, **not
  persistence or RLS**. Only full-stack proves the whole vertical slice.

---

## Part 3 — Set up each tier

### 3.1 One shared mock backend, two runtimes

- Write request handlers **once** in a shared module and reuse them for **node** (component
  tests) and **browser** (E2E). MSW makes this literal: the same handlers run under
  `msw/node` and `msw/browser`.
- Use **same-origin relative paths** (`/v1/...`) so handlers match both.
- Make responses **schema-valid** — derive shapes from the contract/OpenAPI (respect
  `format: uuid`, required fields, enums). A response the decoder rejects will fail the query
  _after_ a 200, which looks like a render bug — so get the shape right first.

### 3.2 Component / route tier

- Render the real route through `renderWithProviders` with a mocked client (MSW-node or an
  injected fake), `userEvent` for interactions, and assertions by role/label/text.
- Pre-seed the query cache for state you don't want to fetch; let MSW serve the rest.
- This is where most "click X → expect Y" coverage lives.

### 3.3 Browser E2E, mock-backed (the fast full-UI tier)

The setup that works, with the traps called out:

1. **Generate the service worker** (`msw init public/`) and register it from a boot gate.
2. **Gate on the build MODE, not shell env.** Start the worker only when
   `import.meta.env.MODE === 'mock'` (`vite --mode mock`). Do **not** rely on a shell env var
   passed to the dev server — bundlers expose env from `.env` files/prefixes, and a shell
   `VITE_X=1` often does **not** reach `import.meta.env`. `MODE` is always exposed. Guard with a
   **dynamic import** so the whole mock module is tree-shaken out of production builds.
3. **Start the worker _before_ first render.** `await worker.start()` must resolve before the
   app makes its first request, or the initial `/me`/config calls escape the mock (and, if
   there's a dev proxy, 502 against a non-running backend).
4. **Separate config + port.** Give the mocked E2E its own Playwright config and dev-server
   port so it never collides with real-backend or visual runs.
5. **Make the mock stateful, with a control surface.** For anything beyond static reads, keep
   a small in-memory state model so a POST changes what the next GET returns (the test observes
   real refetch-driven transitions). Add a **test-only control endpoint**
   (e.g. `POST /__mock__/control`) to trigger: session expiry, require-recent-auth, delayed
   stream, topology bump / 409 conflict, approval expiry, arbitrary error injection. This
   unlocks concurrency, live-state, auth-expiry, and error scenarios that static mocks can't
   reach.
6. **Don't reuse a stale dev server** across mode changes while iterating (kill by port).

### 3.4 Full-stack E2E

- Gate behind an env flag (`RUN_WEB_SYSTEM_E2E`) + documented credentials/tenant; run against
  a **disposable** stack.
- Invest first in a rock-solid harness: deterministic seeding, per-test isolation,
  **guaranteed teardown** (no orphaned stack). One flaky full-stack test poisons trust in all.
- Keep the list small and curated (see §4.4 for what earns a slot).

---

## Part 4 — Write good scenarios

### 4.1 Query and assert like a user

- Prefer `getByRole`/`getByLabel`/`getByText`/`getByPlaceholder`. Avoid CSS selectors and
  default `data-testid`.
- Assert on the **server-confirmed outcome** (a refetch produced the new state / a success
  toast / a persisted value on reload), not merely the optimistic flash.

### 4.2 Cover the unhappy paths, not just the happy one

Use error injection (§3.5 control surface, or per-test handler overrides) to assert:
401/expiry teardown, 403 permission-gating, **409 optimistic-concurrency rebase**,
500/malformed → recoverable error state (never white screen), offline→reconnect.

### 4.3 The high-impact behaviors to always cover

Permission-gating (server capabilities hide affordances) · optimistic concurrency (409 →
rebase, no lost work) · idempotency (double-submit → one effect) · **live-state lifecycle**
(current → delayed → reconnecting → current only after a fresh snapshot at the recovered
generation; idle-heartbeat backpressure) · step-up re-auth (challenge, reject, clear on
success) · draft/session teardown on auth change · deep-link + refresh + unknown-route ·
axe on every route + keyboard-only nav.

### 4.4 What earns a **full-stack** slot

Only if the **seam itself** is the risk — behavior a mock cannot faithfully reproduce (real
cookies/session, real SSE stream, real concurrency/CAS, real RLS isolation, real
recovery/reconciliation) — **or** it doubles as a deployment/packaging smoke. A suggested
P0 core: boot-and-sign-in smoke; real commit persists + topology advances; real 409 across
two browser contexts; live update across two tabs; governance decide + step-up + terminal
CAS; cross-tenant RLS denial.

### 4.5 Determinism

Disable query retries; use fake timers for timing logic; seed all data and ids; pin visual
snapshots per platform; never assert on wall-clock or unseeded randomness.

---

## Part 5 — Pitfalls (hard-won)

- **Decoder strictness feels like friction but is a feature.** Non-UUID ids, a missing
  required field (`version`), or a wrong enum → the client rejects a 200 and the UI errors as
  if there's a render bug. Derive fixtures from the schema; don't guess.
- **Mock-gate via `MODE`, not shell env** (see §3.3.2). This is the #1 "why won't my mocks
  start" trap.
- **Service worker must be active before the first request** — start it before render.
- **A dev proxy will swallow unmocked requests** (502 to a dead backend). Either mock every
  endpoint the route hits or set the mock to bypass and accept the noise — but know that an
  unmocked _critical_ call breaks the page.
- **Canvas/worker islands won't render on synthetic data.** Use empty-valid or real
  fixtures; test the island with visual regression, not functional assertions.
- **Mock tiers don't prove persistence.** A green mock E2E means the UI behaves given a
  response; it says nothing about whether the server actually wrote anything. That's the
  full-stack tier's job — keep a thin set of those.
- **Full-stack flake is contagious.** Stabilize the harness (seed/isolate/teardown) before
  adding tests; a red-by-default suite gates nothing.

---

## Part 6 — Testability review checklist

Score an existing frontend; each "no" is a testability debt to fix in the code, not the tests.

1. Is there a **single** injected network client, same-origin, with response validation?
2. Are all dependencies (client, query cache, config, router, auth, clock) **injected via
   context**, with no import-time side effects?
3. Is the client **thin** — UI a function of server state, permissions server-driven?
4. Is the **hard stateful logic** (streams, editor) in pure reducers with property tests?
5. Is server state behind **one query cache**?
6. Is view state in the **URL**; are routes **data**; is everything deep-linkable/reload-safe?
7. Is the markup **accessible** (roles/labels/aria) so tests query by role, not CSS?
8. Are errors a **typed contract** behind **error boundaries** with assertable states?
9. Are **time/ids/randomness/workers** injected or fallback-able?
10. Are modules **feature-sliced** with **enforced import/size boundaries**?
11. Is the **imperative canvas/worker** isolated, with its logic extracted and pure?
12. Does the **mock backend** live in one shared, schema-valid, stateful module with a
    control surface — usable from both node and browser?
13. Is there a **thin, stable full-stack** gate, distinct from the broad mock tiers?

If most answers are "yes," writing tests — from pure unit to real-browser click-through — is
easy and the tests are stable. If they're "no," fix the architecture first; the tests will
follow.
