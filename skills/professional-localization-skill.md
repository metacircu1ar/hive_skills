# professional-localization

**What it does.** Tells you how to add localization (i18n) to a full-stack web product
_the professional way_ — so that the UI language can switch cleanly on both client and
server, the wire/DB contracts stay honest, and adding a second language later is a bounded
catalog + manifest + loader change, not a feature-by-feature rewrite. The central claim:
**localization is a boundary
discipline, not a translation task.** The hard part is drawing one line — _product copy is
translated, user/tenant data never is_ — and then building every seam (provider, storage,
API, config, CI) to respect it.

**When to reach for it.** Starting or reviewing a product that must support more than one UI
language; deciding a library and message format; wiring where the active locale is resolved
and persisted; adding a language picker; designing the DB/API columns for a language
preference; or auditing an "we added i18n" claim that you suspect is only half done (it
usually is — see Part 6).

**Stack this was distilled from.** React 19 + Vite + TypeScript (strict, `exactOptional`,
`noUncheckedIndexedAccess`) · Lingui 6 + ICU MessageFormat · platform `Intl` APIs · Fastify
5 + Zod + Drizzle + PostgreSQL with row-level security · a shared workspace package spanning
client and server. The _principles_ are framework-agnostic; each section names the principle
first, then the concrete mechanism we shipped.

---

## Part 0 — The one rule that determines everything

**Principle:** localize **product-owned copy** (labels, buttons, headings, validation
messages, notices, transactional emails). **Never** localize **user/tenant data** (names
people type, agent/entity names, knowledge content, free-text they authored). Translating
user data corrupts it; leaving product copy in one language ships an untranslatable UI.

Everything downstream is a consequence of this line:

- A translation catalog holds **only** product copy. If a string in the catalog came from a
  database row, the line was crossed.
- The client renders user data verbatim; only the _chrome around it_ goes through the i18n
  runtime.
- **`Intl` at the boundary, not translation.** Numbers, dates, relative times, lists, plural
  category, and _language display names_ are locale-formatted by the platform — they are not
  catalog entries. A date is user/derived data formatted for a locale, not copy to translate.

> **Anti-pattern that violates the rule:** putting a tenant name or an agent's title into a
> `msg(...)`/`t\`...\`` so it "shows up in the catalog." It should never be in the catalog.

Write this rule at the top of your own catalog file as a comment. It is the thing reviewers
forget first.

---

## Part 1 — Decisions to make up front

Get these right on day one; each is expensive to reverse later.

### 1.1 Library + message format: Lingui + ICU MessageFormat

- **Principle:** pick a format that handles **plurals, gender, and interpolation the way real
  languages need**, and a library that **extracts messages from source** so engineers don't
  hand-maintain a key list.
- **Do:** ICU MessageFormat (`{count, plural, one {# item} other {# items}}`) is the
  professional default — every serious translation tool understands it. Lingui compiles it,
  extracts messages from macros, and has first-class React + plain-TS (server) support.
- **Why:** hand-rolled `t('key')` maps rot — keys drift from usage, plurals get faked with
  `count === 1 ? ...`, and translators get a bag of context-free strings. ICU + extraction
  makes the message text _and its grammar_ the source of truth.

### 1.2 Explicit, stable message IDs — not auto-hashed

- **Principle:** every message gets a **human-readable, stable ID** you choose
  (`auth.login.title`), not a hash of the English source.
- **Do:** enable the lint rule that forces it (`lingui/require-explicit-id: 'error'`). Author
  copy as `msg({ id: 'auth.login.title', message: 'Sign in' })`.
- **Why:** (1) editing the English wording doesn't silently orphan every translation; (2) the
  **same ID can be shared by client and server** (Part 4.5); (3) diffs read as intent
  (`auth.login.title` moved) not noise (`a1b2c3` changed).

### 1.3 Store locale as **text**, validate in code — never a DB enum

- **Principle:** the set of supported locales is **application configuration**, not database
  schema.
- **Do:** columns are `text`; the API validates against the supported set (`isSupportedLocale`).
- **Why:** adding a language must not require an `ALTER TYPE ... ADD VALUE` migration on every
  deployment. Text + code-side validation keeps the database out of the rollout; the bounded
  application change is catalogs + loader + supported manifest + verification. (Migration
  comment we shipped: _"Tenant defaults are configuration, not a database enum: deployments
  may add supported locales without a schema migration."_)

### 1.4 One shared locale package spanning client **and** server

- **Principle:** the locale _policy_ (supported set, default, resolution, direction, and any
  server-owned human messages) lives in **one workspace package** both tiers import.
- **Why:** it is the only thing that prevents client/server copy drift and two different ideas
  of "what locales exist." See Part 2.

### 1.5 One message = one sentence — never assemble from fragments

- **Principle:** a translatable unit is a **whole phrase or sentence with placeholders**, not
  pieces glued together in code. The moment you concatenate a translated fragment with `${…}`
  in JS, you have frozen the word order to the authoring language.
- **Do:** put the variable _inside_ the message and let ICU hold the slot:

  ```tsx
  // GOOD — one message, translator controls word order around {revision}
  i18n._(msg({ id: 'map.node.activeRevisionSentence', message: 'Active revision {revision}.' }),
         { revision });
  <Trans id="map.node.memberCount">{count, plural, one {# agent} other {# agents}}</Trans>
  ```

- **Don't:** build the sentence in JavaScript from translated parts:

  ```tsx
  // BAD — "Active revision" and the number are separate units; a language that
  // puts the number first, or needs a different particle, cannot express it.
  `${i18n._(msg({ id: "map.node.activeRevision", message: "Active revision" }))} ${revision}.`;
  ```

- **The worst offender is the assembled `aria-label`.** A screen-reader string built from five
  `msg()` fragments interleaved with data ("{name} agent. Lifecycle {x}. {rev}. {n} active…")
  is unreadable to a translator and ungrammatical in most languages. Make it **one** message
  with named placeholders.
- **Why it's insidious:** fragment-assembly **passes `no-unlocalized-strings`** — every piece
  _is_ wrapped. It looks migrated. It is not translatable. See Part 6.4.

---

## Part 2 — The shared locale package (single source of truth)

**Principle:** both tiers must agree on the supported set, the default, and how an untrusted
locale string is resolved. Put that agreement in code they both depend on.

```ts
// packages/localization/src/index.ts
export const supportedLocales = ["en"] as const; // the ONE list
export type SupportedLocale = (typeof supportedLocales)[number];
export type TextDirection = "ltr" | "rtl";
export const defaultLocale: SupportedLocale = "en";

export function isSupportedLocale(v: string): v is SupportedLocale {
  return (supportedLocales as readonly string[]).includes(v);
}

// Match one UNTRUSTED candidate without applying the fallback yet. This is
// essential when scanning an ordered Accept-Language/navigator.languages list:
// an unsupported first item must not hide a supported later item.
export function matchSupportedLocale(
  candidate?: string,
): SupportedLocale | undefined {
  if (candidate === undefined) return undefined;
  try {
    const canonical = Intl.getCanonicalLocales(candidate)[0];
    if (!canonical) return undefined;
    const normalized = canonical.toLowerCase();
    const exact = supportedLocales.find(
      (locale) => locale.toLowerCase() === normalized,
    );
    if (exact) return exact;
    const language = normalized.split("-")[0];
    return supportedLocales.find(
      (locale) => locale.toLowerCase().split("-")[0] === language,
    );
  } catch {
    return undefined;
  }
}

export function resolveSupportedLocale(candidate?: string): SupportedLocale {
  return matchSupportedLocale(candidate) ?? defaultLocale;
}

export function resolveSupportedLocaleCandidates(
  candidates: readonly (string | null | undefined)[],
): SupportedLocale {
  for (const candidate of candidates) {
    const matched = matchSupportedLocale(candidate ?? undefined);
    if (matched) return matched;
  }
  return defaultLocale;
}

export function textDirectionFor(locale: SupportedLocale): TextDirection {
  /* ltr/rtl */
}
```

Two non-obvious moves that make this professional:

- **`resolveSupportedLocale` swallows errors.** A user-controlled `Accept-Language` header or
  a corrupt stored value is _input_, not a crash site. Resolution is total: any string in,
  a supported locale out.
- **Matching and fallback are separate operations.** Do not call a resolver that immediately
  falls back while walking an ordered browser-language list. `['ar-EG', 'en-US']` must select
  `en`, not let unsupported `ar-EG` collapse the whole list to the default before `en-US` is
  considered. Also prefer exact supported tags before base-language matching when a deployment
  eventually ships regional variants.
- **The package can also own server-emitted human messages** (transactional email subjects/
  bodies) behind a single function, so there is exactly one place a later real catalog
  replaces the interim English (Part 4.5). Keeping it here prevents server adapters from
  inventing separate locale policy or scattering human copy.

> **Anti-pattern:** a `SUPPORTED_LOCALES` array in the frontend and a different enum in the
> backend. They _will_ diverge, and the bug surfaces as "the UI offers French, the API 400s
> on `fr`."

---

## Part 3 — Client architecture

### 3.1 A provider, not a mutable global

- **Principle:** the active locale is **context state**, injected — never a module-level
  mutable singleton. (Same inversion-of-control discipline that makes UIs testable.)
- **Do:** a `LocalizationProvider` owns `locale`, `availableLocales`, `textDirection`, and the
  mutators. Consumers read via `useLocale()`; the raw i18n engine is provided to children.
- **Why:** tests swap locale by rendering the provider with a prop; nothing monkey-patches a
  global; a future lazy-loaded catalog slots in at _one_ boundary.

```tsx
// The catalog-loading seam. English is static today; other locales lazy-load HERE
// without any consumer changing.
const i18n = useMemo(() => {
  const next = setupI18n();
  next.loadAndActivate({ locale, messages }); // ← swap for dynamic import per locale later
  return next;
}, [locale]);
```

### 3.2 The resolution chain — and why in-session override must win

- **Principle:** the active locale is resolved from several sources in **strict priority
  order**, and a choice the user _just made_ must not be clobbered by an async load that
  finishes later.

The order we shipped (highest wins):

```
in-session switch  >  principal preferred_locale (/me)  >  tenant default_locale
                   >  Accept-Language (navigator)  >  deployment defaultLocale
```

Plus **localStorage seeds first paint** (before any network) so there's no language flash on
reload.

The subtle correctness bug this prevents: `/me` resolves asynchronously. If a user opens the
picker and switches to French while `/me` (saying `en`) is still in flight, the late response
must **not** overwrite their choice. Track an in-session override flag and let it win:

```tsx
const sessionOverride = useRef(false);

const setLocale = useCallback(
  (next: SupportedLocale) => {
    // explicit user action
    if (!availableLocales.includes(next)) return;
    sessionOverride.current = true; // ← this choice now wins
    persistLocale(next);
    setLocaleState(next);
  },
  [availableLocales],
);

const applyServerLocale = useCallback(
  (next: string | undefined) => {
    // async, lower priority
    if (sessionOverride.current) return; // ← never clobber a live switch
    const resolved = resolveSupportedLocale(next);
    if (!availableLocales.includes(resolved)) return;
    persistLocale(resolved);
    setLocaleState(resolved);
  },
  [availableLocales],
);
```

### 3.3 Keep the chain in a tiny sync component, not the provider

- **Principle:** the provider owns _mechanism_ (state + mutators); a small effect-only
  component owns _policy_ (which source feeds it, and when).
- **Why:** the provider must mount before `QueryClient`/`ApiClient` exist, but the preference
  comes from `/me`. Split them: a `LocaleSync` renders `null`, runs after the API is
  available, and pushes values in.

```tsx
export function LocaleSync(): null {
  const configuration = useRuntimeConfiguration();
  const { applyServerLocale, configureDeploymentLocales } = useLocale();
  const authenticatedRoute = !anonymousPathnames.has(location.pathname);
  const me = useMeQuery({ enabled: authenticatedRoute });

  useEffect(() => { configureDeploymentLocales(configuration); }, [configuration, ...]);

  useEffect(() => {
    // A disabled React Query can still expose cached data, so anonymous routes
    // must ignore me.data explicitly rather than relying on enabled:false.
    const principal = authenticatedRoute ? me.data : undefined;
    if (principal?.preferredLocale) {
      applyServerLocale(principal.preferredLocale);
      return;
    }

    // If an authenticated principal has tenants, this root-level effect MUST
    // yield. It does not know the selected route tenant, and tenants[0] is not
    // necessarily active. The tenant shell applies the routed tenant default.
    if (principal && principal.tenants.length > 0) return;

    applyServerLocale(resolveSupportedLocaleCandidates([
      ...navigator.languages,
      navigator.language,
      configuration.defaultLocale,
    ]));
  }, [applyServerLocale, configuration.defaultLocale, me.data]);
  return null;
}

// Mounted by the routed tenant shell, where the selected tenant is known.
export function TenantLocaleSync({ defaultLocale, preferredLocale }): null {
  const { applyServerLocale } = useLocale();
  useEffect(() => {
    if (preferredLocale === null) applyServerLocale(defaultLocale);
  }, [applyServerLocale, defaultLocale, preferredLocale]);
  return null;
}
```

Note it **skips `/me` on anonymous routes** (`/login`, `/bootstrap`, `/recover`) — there is
no principal there, so the picker + Accept-Language + deployment default carry those screens.
Also note the two-effect race: a root browser-fallback effect and a child tenant-fallback
effect may run in an order you did not expect. Make the root return no candidate when the routed
tenant owns fallback; do not let two effects race to write different authoritative values.

### 3.4 The reusable picker that disappears when it's pointless

- **Principle:** one small `<LanguagePicker />` used everywhere a switch belongs, that
  **renders nothing while only one locale is available** — so a single-locale deployment shows
  no dead control, and the day a second catalog ships, every placement lights up at once.

```tsx
export function LanguagePicker({
  className,
}: {
  readonly className?: string | undefined;
}) {
  const { i18n } = useLingui();
  const { availableLocales, locale, setLocale } = useLocale();
  if (availableLocales.length <= 1) return null; // ← self-hides
  return (
    <select
      aria-label={i18n._(productCopy.preferences.languageSelectorLabel)}
      className={className}
      value={locale}
      onChange={(e) => setLocale(e.target.value as SupportedLocale)}
    >
      {availableLocales.map((l) => (
        <option key={l} value={l}>
          {formatLocaleName(l, locale)}
        </option>
      ))}
    </select>
  );
}
```

Language names come from an `Intl.DisplayNames` wrapper in the _current_ locale — never a
hand-kept map of `{ en: 'English', fr: 'Français' }`, and never an inline formatter that
bypasses the shared formatting boundary.

> **strict-TS gotcha:** with `noUncheckedIndexedAccess`, `styles.x` from a CSS module is
> `string | undefined`. A prop typed `className?: string` then rejects it under
> `exactOptionalPropertyTypes`. Type reusable props as `className?: string | undefined`.

### 3.5 Set `lang`/`dir` on the document; use CSS logical properties

- **Principle:** the document must declare its language and direction; layout must be written
  so RTL is a data flip, not a re-layout.
- **Do:** in a layout effect, set `documentElement.lang = locale` and `.dir = textDirection`
  (restore previous values on unmount so tests/embeds are clean). Write CSS with **logical
  properties** — `margin-inline-start`, `padding-block-end`, `justify-self: end` — not
  `margin-left`/`right`. Then RTL is `dir="rtl"` with zero new CSS.
- **Why:** accessibility (screen readers announce the language), correct hyphenation/quotes,
  and RTL support that already works before you have an RTL translation.

### 3.6 `Intl` at the platform boundary

Wrap the platform formatters once and require the caller to pass the active locale — never
hand-roll and never silently fall back to a process/global locale:

```ts
formatNumber(v, locale, opts); // Intl.NumberFormat
formatRelativeTime(v, unit, locale); // Intl.RelativeTimeFormat
formatList(values, locale); // Intl.ListFormat
formatLocaleName(tag, locale); // Intl.DisplayNames  (language names)
pluralCategory(v, locale); // Intl.PluralRules
```

Components obtain `locale` from `useLocale()` and pass it explicitly. Requiring it in the
wrapper signature turns a missed migration into a type error; an optional/default locale hides
call sites that still format according to the host machine or an English default.

These are the correct home for everything that is _derived/user data shaped for a locale_ —
which, per Part 0, is exactly the stuff that must **not** be in the translation catalog.

---

## Part 4 — Server architecture

The server has four jobs: **persist** a preference, **default** per tenant, **advertise** what
the deployment supports, and **emit** its own human copy in the right language.

### 4.1 Persist the principal preference — RLS actor-scoped, append-safe

- **Principle:** a display-language preference belongs to the **authenticated principal**, not
  to a tenant, and it must be isolated so one principal can never read/write another's.
- **Do:** a dedicated table, RLS `FORCE`d, policy scoped to the **actor** (not a tenant), and
  the application role **cannot DELETE** (preferences are upserted, not deleted).

```sql
CREATE TABLE app.principal_preferences (
  principal_id text PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  preferred_locale text,
  updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE app.principal_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.principal_preferences FORCE ROW LEVEL SECURITY;

CREATE POLICY actor_isolation ON app.principal_preferences FOR ALL TO app_application
  USING       (principal_id = NULLIF(current_setting('app.actor_id', true), ''))
  WITH CHECK  (principal_id = NULLIF(current_setting('app.actor_id', true), ''));

GRANT SELECT, INSERT, UPDATE ON app.principal_preferences TO app_application;
REVOKE DELETE ON app.principal_preferences FROM app_application;   -- append-safe
```

**Hard-won RLS lesson (the trap):** scope the policy to the identity that is _stable across
the operation_. A preference is keyed by `principal_id`, so both `USING` and `WITH CHECK`
key on `app.actor_id`. (In a sibling table we once scoped `USING` to `tenant_id`; an
`ON CONFLICT` upsert that _changed_ the tenant was blocked because the pre-update row failed
the tenant-scoped `USING` check. Rule: **`USING` must pass for the row as it exists before the
write; `WITH CHECK` validates the row after.** Scope each to the column that actually
identifies ownership.)

### 4.2 Tenant default as configuration text

```sql
ALTER TABLE app.tenants ADD COLUMN default_locale text NOT NULL DEFAULT 'en';
```

Text, not enum (Part 1.3). Return it from the same function that lists a principal's tenants
so the client resolves fallback **without a second round-trip**:

```sql
-- projection also carries the non-sensitive default_locale
RETURNS TABLE (tenant_id uuid, tenant_name text, default_locale text, role app.role)
```

### 4.3 Surface + mutate the preference through the API

- `/me` returns `preferredLocale` (read via `getPreferredLocale`, which **validates** the
  stored value against the supported set and returns `null` if unknown).
- A dedicated `PATCH /v1/me/preferences { locale }` upserts it. **Validate the enum in the
  route schema** and re-validate in the service:

```ts
// Fastify route body schema — import the enum from the shared supported set
properties: { locale: { type: 'string', enum: supportedLocales } }, required: ['locale']

// service re-validates before writing, and after reading back
if (!isSupportedLocale(input.locale)) throw badRequest(...);
```

### 4.4 Advertise deployment locales via runtime config

- **Principle:** the bundle has a packaged capability manifest, while the deployment decides
  which subset it offers. The browser must not guess the deployment offer; it **asks** a public,
  credential-free config endpoint and validates the answer against its packaged catalogs.
- **Do:** `/runtime-config.json` returns `availableLocales` + `defaultLocale` (both from the
  shared package / install config), which feed `configureDeploymentLocales` (Part 3.3).

```ts
return reply.send({
  availableLocales: supportedLocales,
  defaultLocale: config.web.defaultLocale, // ← install-time env, resolved (Part 5.1)
  /* ...no credentials, no tenant data... */
});
```

### 4.5 The server emits its **own** copy — through one shared owner

- **Principle:** copy the _server_ generates (password-reset / verification emails, etc.) is
  product copy too. It needs one explicit owner and recipient-locale resolution; do not scatter
  English email subjects/bodies through auth adapters.
- **Do now for an English-only foundation:** one shared function owns those strings, keyed by
  locale + kind, so a later real catalog replaces the interim English in exactly one place:

```ts
localizedAuthEmail(locale, 'verification' | 'password_reset', url)
  -> { subject, text }   // shared package; the ONE server-copy owner
```

- **Before a second locale ships:** replace/extend that interim function with a compiled ICU
  catalog or server Lingui runtime and prove every advertised locale has server-side messages.
  A shared _owner_ is not yet a shared compiled catalog. Do not claim server localization is
  complete merely because English copy was centralized.

### 4.6 Pin the invariants with a drift/contract check

- **Principle:** the security properties above (RLS enabled+forced, actor-scoped policy,
  no-DELETE for the app role) are **invariants**, so assert them in a startup/CI contract
  check — not just in a migration that could later be edited.

```ts
// assertIdentityCurrentIntegrity: fail boot/CI if any invariant regressed
if (
  !row.enabled ||
  !row.force ||
  row.application_delete /* app can DELETE! */ ||
  !policy.using_expression?.includes("current_setting('app.actor_id'")
)
  throw new Error(
    "Principal preferences must be RLS-isolated and append-safe.",
  );
```

The contract should assert the **positive and negative** capability matrix, not only one
privilege: application has exactly the required `SELECT/INSERT/UPDATE`, not `DELETE`; migration
can maintain the table; queue/model-gateway/PUBLIC have no data access; both `USING` and
`WITH CHECK` remain actor-scoped. A migration proves what happened once. A current-schema
contract proves what must still be true after later migrations and production drift.

---

## Part 5 — The three tiers of language selection

A professional product lets the language be chosen at **three** moments. All three drive the
_same_ provider seam; they differ only in _who_ chooses and _when_.

### 5.1 Tier 1 — install-time default (operator, deploy time)

An env var resolved through the shared resolver, carried in server config, advertised in
runtime-config as `defaultLocale`. Unsupported/absent → packaged default. This is the locale a
brand-new deployment speaks before any user or tenant exists.

```ts
// config schema — env in, supported locale out, never invalid
defaultLocale: z.string().optional().transform((v) => resolveSupportedLocale(v)),
// mapping:  defaultLocale: env['WEB_DEFAULT_LOCALE']
```

### 5.2 Tier 2 — first-run / bootstrap (the founding user)

The bootstrap/setup screen carries the compact `<LanguagePicker />` (it's a public route, so
it shares the auth layout). This switches the **live** UI immediately.

> **Contract gotcha:** persisting the bootstrap choice to the server (→ tenant `default_locale`
> and owner `preferred_locale`) means the _request payload_ must carry `locale`. If your create
> endpoints use `additionalProperties: false` (they should), you **cannot** just add a field
> client-side — it needs the input type + OpenAPI regen + server storage together. Treat
> "picker flips live UI" and "bootstrap persists the choice" as two separate, sequenced
> pieces of work, not one.

**Closing it cleanly (the pattern that worked):**

- **Write both fallbacks in one atomic step.** Bootstrap sets _two_ locale values — the
  tenant's `default_locale` and the founder's `preferred_locale`. Do both inside the single
  `SECURITY DEFINER` bootstrap function/transaction so a half-bootstrapped deployment can't
  exist.
- **Make the old signature unreachable, don't just add to it.** When you extend the bootstrap
  routine to take `locale`, create the **new** function signature and `REVOKE EXECUTE` on the
  **old** one from the application role. Now a route physically cannot call the version that
  skips locale persistence — the new path is the only path. (Adding an optional arg and hoping
  every caller passes it is not the same guarantee.)
- **The endpoint falls back to Tier 1, not to a hardcoded `'en'`:**
  `locale: request.body.locale ?? config.web.defaultLocale` — so an API client that omits
  `locale` still lands on the operator's install-time default. The tiers compose.

### 5.3 Tier 3 — any time, in-app (every user)

- The **compact picker on every public/anonymous screen** (sign-in, recover) — one insertion
  into the shared auth layout covers them all.
- A **full switcher in account preferences** for signed-in users, which calls
  `PATCH /v1/me/preferences` so the choice **persists server-side** across devices.

The preferences switcher must state the boundary in its own copy: _"Changes the interface
language only. Your content and data are never translated."_ Users need to know a switch won't
mangle their data — say so.

---

## Part 6 — Guardrails that keep it professional over time

### 6.1 Extraction drift gate in CI

- **Principle:** the compiled catalog must always match the source. Make CI fail if someone
  adds a `msg(...)` without re-extracting.
- **Do:** `i18n:check = extract && compile && git diff --exit-code -- <catalog dir>`. A new
  string that isn't in the catalog fails the build.

### 6.2 `require-explicit-id: error` from day one

Cheap, and it's the rule that makes IDs shareable and diffs legible (Part 1.2). Turn it on
before you have a second string.

### 6.3 `no-unlocalized-strings`: stage it, and know its false positives

- **Principle:** the rule that flags raw user-facing strings is the finish line, but it is
  **noisy** — turning it to `error` on a half-migrated codebase buries you.
- **Reality:** it flags a lot that is _not_ UI copy — permission keys (`'knowledge.publish'`),
  slugs (`'operator-note'`), route paths (`/t/${id}/map`), enum discriminants
  (`type: 'agent'`), `throw new Error('dev message')`, even some JSX attribute values. On our
  codebase a forced run showed **955 hits across 48 files**; a large fraction was this noise.
- **Do:** keep it **off** while migrating; migrate feature area by feature area; then flip it
  to `error` (with a curated ignore list for the genuinely-technical strings) as the _gate_
  that says migration is actually done.

### 6.4 "We added i18n" is a claim to **verify**, not trust

The single most important lesson: **a migration is not done until the gate is green.** We were
told "all strings were migrated"; a forced `no-unlocalized-strings` run found real,
user-facing English still sitting in whole feature workspaces (execution/runs views, graph
editors, knowledge notices). Auth + shell + settings were done; the feature core was not.

When someone (including you) says the UI is fully localized, **prove it**: run the rule, then
_read the flagged lines_ to separate real copy from noise. Report the honest residue. "It
compiles and the visible screens look translated" is not evidence — untranslated copy hides in
the routes you didn't click.

**But a green gate is necessary, not sufficient.** `no-unlocalized-strings` proves every
string is _wrapped_ — it does **not** prove the wrapping is well-formed. Two defects sail
straight through it and only surface when a real translation lands:

- **fragment-assembled sentences** (Part 1.5) — each piece is wrapped, so the gate is happy,
  but the word order is frozen to English;
- **missing plurals** — `` `${n} agents` `` is wrapped and passes, yet renders "1 agents".
  (Watch for the tell-tale `(s)`, and for the _same_ file pluralizing some counts with ICU
  `.one`/`.other` and hardcoding others — inconsistency is the smell.)

So the real finish line is: gate green **and** a read-through confirming no sentence is built
by concatenation and every count uses ICU `plural`. Run `no-expression-in-message` (below) to
automate most of that second check.

### 6.5 `no-expression-in-message`: the rule that catches fragment-assembly

- **Principle:** placeholders in a message should be **named identifiers**, not member
  expressions or calls — because Lingui turns `{data.count}` into an opaque positional
  `{0}` (useless context for a translator), and because interpolating a _translated fragment_
  trips this rule too.
- **Do:** enable `lingui/no-expression-in-message`. When it fires, hoist to a local:
  `const count = data.memberCount;` then `<Trans>{count, plural, …}</Trans>` → the placeholder
  is named `{count}`. It's the automated backstop for the Part 1.5 rule.
- **Pragmatics:** it's reasonable to start this at `warn` (it flagged ~50 sites for us, all
  member-expression interpolation) and burn it down toward `error`. Unlike `no-unlocalized`,
  its hits are almost never false positives — they're genuine placeholder-quality debt.

### 6.6 Product-owned values are copy too; unknown evidence is not

An i18n sweep often migrates headings and buttons but leaves API values such as
`embed_page_version`, `broad_communication`, `can_request`, `waiting_approval`, or
`tenant_export.requested` rendered verbatim. Those are **product-owned vocabulary**, not tenant
data, and should have static message descriptors.

Use one bounded mapping rather than dynamically translating the value:

```ts
const productValueMessages: Readonly<Record<string, MessageDescriptor>> = {
  embed_page_version: msg({
    id: "values.embedPageVersion",
    message: "Embed page version",
  }),
  can_request: msg({ id: "values.canRequest", message: "Can request" }),
};

export function formatProductValue(i18n: I18n, value: string): string {
  const descriptor = productValueMessages[value];
  return descriptor ? i18n._(descriptor) : value;
}
```

The fallback is deliberate: operator evidence, forward-compatible codes, and tenant-authored
values may be unknown and must remain exact. Never manufacture a message ID from untrusted data
(`i18n._('values.' + value)`) and never humanize unknown codes by replacing underscores; both
blur the product-copy/data boundary and can make audit evidence dishonest.

Audit more than obvious JSX literals. Search rendered fields and interpolated locals named
`status`, `kind`, `mode`, `policyClass`, `eventType`, `lifecycle`, `controlHolder`, and similar.
Lint rules usually treat these as expressions/data, so a green literal-string rule will not
catch them. Include ARIA labels: localizing the visible badge but leaving raw lifecycle/runtime
codes in the accessible name is an incomplete migration.

### 6.7 Problem responses are a localization and data-leak boundary

Do not render server-authored `title`, `detail`, validator text, or arbitrary structured
`details`. Besides being untranslatable, those fields can contain internal or tenant-derived
text. The browser should map a stable machine `code` (with a conservative HTTP-status fallback)
to local message descriptors and preserve only safe correlation data such as `requestId`.

- Parse `details` as a bounded non-null object at the API-client boundary; reject arrays and
  malformed shapes.
- Treat `details` as typed parameters only for an explicitly-known code. Never stringify the
  object into UI copy.
- Test with conspicuous raw/private server strings and assert none reaches rendered output.
- Keep server detail for logs/compatibility if required, but make the display helper incapable of
  selecting it.

This is stronger than “translate error messages”: it establishes that localized client copy is
the only human-text authority for browser errors.

### 6.8 The locale manifest and catalog loader form one fail-closed contract

`runtime-config.json` may advertise only locales that the running browser bundle can actually
load. Validate every advertised locale and the default against the packaged `supportedLocales`,
require a non-empty list, and require the default to be in that list. If the server says `fr` but
the bundle contains only `en`, stop at runtime-configuration loading rather than activating
French with English messages.

The shared locale manifest should drive:

- server request/response schemas;
- runtime configuration;
- Lingui extraction/compile configuration;
- client locale types and resolver;
- server email locale resolution.

Adding a manifest entry before adding the compiled client catalog and catalog-loading branch is
an invalid rollout. Before the second locale, change the provider from a statically imported
English catalog to a bounded per-locale lazy loader, and add a contract test that every supported
locale resolves to one real catalog.

### 6.9 Mechanical formatting and RTL gates catch what copy lint cannot

Copy lint does not detect `new Intl.DateTimeFormat(...)`, `.toLocaleString()`, `margin-left`,
`right: 0`, or `text-align: left`. Add a separate source gate that scans UI code outside the
approved formatting module for direct `Intl`/`toLocale*` usage and scans CSS for physical
directional properties. Prefer an AST/parser when the codebase already has one; a small explicit
regex gate is still materially better than a review convention when its scope is narrow and
tested.

Remember that `dir="rtl"` plus logical CSS is **foundation**, not proof. Before advertising a
real RTL locale, run a pseudo-RTL visual/browser pass that exercises overlays, portals, graphs,
icons/arrows, keyboard navigation, and third-party components whose positional props may still
be physically named.

### 6.10 Give locale catalogs their own bundle budget

Moving hundreds of strings into a compiled catalog changes chunk accounting even when
application behavior is unchanged. Do not silently raise the existing application-JS ceiling.
Identify the locale chunk, keep the old application budget excluding that chunk, and add a
separate maximum for exactly one active locale catalog. The gate should fail if zero or multiple
locale chunks appear unexpectedly. This preserves the original performance ratchet while making
translation cost visible.

### 6.11 Preference writes need transactional-feeling UI behavior

The in-app picker should update immediately, persist asynchronously, disable duplicate submits,
surface a localized problem on failure, and roll back to the previous active locale if the write
fails. Update the cached `/me` preference after success so a refetch/sync effect does not restore
the old value. Test the failure path; “the selector moved” is not proof that the principal
preference was stored.

### 6.12 Verify the whole boundary, not only component tests

A credible localization verification matrix includes:

1. catalog extraction is drift-free and strict compilation has zero missing messages;
2. formatting, lint, typecheck, build, and a diff-whitespace check;
3. focused locale-resolution/provider/error/product-value tests;
4. the complete UI suite, because accessible names and exact copy assertions will change;
5. API/OpenAPI regeneration twice with byte-identical hashes, plus generated-client tests;
6. migration-history validation and a real-PostgreSQL identity test proving bootstrap,
   preference RLS, role isolation, and schema contracts;
7. runtime-config mismatch tests (server advertises an unavailable client catalog);
8. bundle, route/import-boundary, release, and compatibility gates.

Keep documentation honest about the current phase. An English-only release with an interim email
owner and logical CSS must not claim pseudo-localization, real RTL validation, lazy per-locale
loading, translator workflow, or compiled multilingual server catalogs are already complete.

---

## Part 7 — Anti-patterns grab-bag

- **User data in the catalog** — the cardinal sin (Part 0).
- **Sentences assembled from translated fragments** (`` `${_('Active revision')} ${n}.` ``) —
  one message with placeholders instead; passes the gate, breaks translation (Part 1.5).
- **Positional `{0}` placeholders** from interpolating `data.x`/`fn()` into a message — hoist
  to a named local (Part 6.5).
- **Two locale lists** (frontend array + backend enum) that drift — share one package (Part 2).
- **DB enum for locale** — forces a migration per language (Part 1.3).
- **Hand-rolled plurals** (`count === 1 ? 'item' : 'items'`, or `{n} run(s)`) — use ICU
  `plural`; watch for one file that pluralizes some counts and hardcodes others (Part 1.1, 6.4).
- **Hardcoded language names** (`{ en: 'English' }`) — use `Intl.DisplayNames` (Part 3.4).
- **Physical CSS** (`margin-left`) that breaks RTL — use logical properties (Part 3.5).
- **A mutable locale global** — inject via provider (Part 3.1).
- **Async server preference clobbering a live switch** — session override wins (Part 3.2).
- **Resolving each browser language with an immediate fallback** — an unsupported first entry
  masks a supported later entry; match candidates first, fall back only after exhausting the
  ordered list (Part 2).
- **Using `me.tenants[0].defaultLocale`** — the first membership is not necessarily the routed
  tenant; root locale sync must yield and let the selected-tenant shell apply its default (Part
  3.3).
- **Competing root and tenant locale effects** — effect ordering is not an authority model;
  ensure only one layer owns fallback for a given state (Part 3.3).
- **Resolver that throws** on a bad `Accept-Language` — resolution must be total (Part 2).
- **Rendering server `title`/`detail` or stringified `details`** — localize stable codes and keep
  raw server human text out of the display path (Part 6.7).
- **Rendering product enum/event codes as if they were tenant data** — map known values through
  static descriptors, while preserving unknown evidence exactly (Part 6.6).
- **Advertising a locale before its client catalog exists** — fail closed at runtime config and
  make manifest/catalog/loader changes atomic (Part 6.8).
- **Raising the old JS budget to absorb catalogs** — preserve the app budget and account for the
  active locale chunk separately (Part 6.10).
- **Sneaking `locale` into an `additionalProperties:false` payload** without the contract
  change — it 400s (Part 5.2).
- **RLS policy scoped to the wrong (mutable) column**, breaking upserts (Part 4.1).
- **Extending a persistence routine by adding an optional arg** instead of revoking the old
  signature — the bypass path still exists; make the new path the _only_ path (Part 5.2).
- **Flipping `no-unlocalized-strings` to error mid-migration** — you'll drown in noise (Part 6.3).
- **Trusting a "fully localized" claim** without running the gate (Part 6.4).
- **Treating a green gate as "done"** — it proves _wrapped_, not _translatable_ (Part 6.4).
- **Tests asserting raw pre-migration copy** — migrating copy breaks them; and they must render
  through the real i18n provider, or `getByRole({ name })` matches message IDs/fallbacks, not
  rendered text (Part 6).

---

## Definition of done

- [ ] One shared package: supported set, default, total resolver, direction, server copy owner.
- [ ] Ordered locale matching checks every browser preference before falling back; exact tags
      win before base-language matches.
- [ ] Product copy authored with **explicit stable IDs**; `require-explicit-id: error`.
- [ ] **No sentence assembled from fragments**; every count uses ICU `plural`;
      `no-expression-in-message` clean (placeholders named, not positional).
- [ ] Locale stored as **text**; validated in API + service against the supported set.
- [ ] Client: provider (no global) + catalog-loading seam + `LocaleSync` chain
      (session > preferred > tenant > Accept-Language > deployment) + localStorage first paint.
- [ ] Root sync never guesses `tenants[0]`; selected-tenant fallback has one authoritative owner
      and cannot race the browser fallback effect.
- [ ] `<LanguagePicker />` that self-hides at ≤1 locale; names via `Intl.DisplayNames`.
- [ ] `document.lang`/`dir` set; layout uses CSS **logical properties**.
- [ ] `Intl` wrappers require an explicit active locale for number/date/relative/list/plural and
      language names — nothing formatted inline or by hand.
- [ ] Server: principal-preference table (RLS forced, **actor-scoped**, no app DELETE);
      tenant `default_locale`; `/me` surfaces it; `PATCH /me/preferences` validates + upserts.
- [ ] `runtime-config.json` advertises `availableLocales` + `defaultLocale`.
- [ ] Server-emitted copy (emails) has one shared owner; before locale two, every advertised
      locale has a compiled server-side catalog/message implementation.
- [ ] Browser problem display maps stable codes and never renders raw server title/detail/details.
- [ ] Product-owned statuses/modes/event kinds use static descriptors; unknown audit/operator
      evidence remains verbatim.
- [ ] Runtime-config locales are a non-empty subset of packaged catalogs and include the default;
      mismatches fail closed before tenant data loads.
- [ ] Startup/CI **contract check** pins the RLS + append-safe invariants.
- [ ] Three tiers wired: install env default · bootstrap picker · in-app (public picker +
      persisted account preference).
- [ ] Bootstrap persists **both** tenant default + owner preference atomically; the pre-locale
      function signature is **revoked** so the persisting path is the only path.
- [ ] CI **extraction drift gate** green; `no-unlocalized-strings` staged toward `error`.
- [ ] Direct `Intl`/`toLocale*` and physical-direction CSS gates green; locale chunk has a separate
      bundle budget without weakening the application-JS budget.
- [ ] Preference mutation is optimistic but rolls back and displays a localized problem on error;
      successful writes update authoritative client cache.
- [ ] Generated API artifacts reproduce byte-for-byte; migration history and real-PostgreSQL RLS/
      bootstrap tests pass.
- [ ] Migration claim **verified by running the gate AND reading the residue** — remembering a
      green gate proves _wrapped_, not _translatable_ (no fragment-assembly, no faked plurals).
