# Microskill catalogue

Starting points for generation. None applies by default except `errors-and-logging`.
Keep a family only when the code shows it applies. Specialize every item to the
project's own APIs and conventions, and split a family when its items need different
tracing. Items here are generic on purpose; a generated microskill must not be.

## errors-and-logging (always)

Error checking and logging are easiest to check and fix together.

1. **Errors are checked.** Follow every operation that can fail to where the failure
   is handled: exceptions, error returns, exit codes, partial writes and background
   tasks. Flag:
   - swallowed errors and catch-all handlers;
   - failures turned into success;
   - one error reported as another;
   - "log it and carry on" where carrying on is not safe.
2. **Each failure is recorded once.** Some layer logs it with enough context to
   diagnose. Every layer need not, but nobody may assume that an unseen caller will.
3. **Important non-error events are visible:** start and finish, state changes,
   retries, fallbacks and commits, without logging noise.
4. **Logs are good and safe.** They use useful structured fields and correct levels.
   Flag secrets, personal data and raw payloads in logs, duplicate records and log
   floods.

Split it into two microskills (error checking, and logging quality) only when the
codebase is large and both halves have many sites.

## Concurrency and async

**Applies when:** threads, an async runtime, worker pools, queues or shared mutable
state.

Typical split:

- **Shared-state races:** unsynchronized read-modify-write, and check-then-act across
  threads or tasks.
- **Locks held across await or blocking calls:** inconsistent lock ordering, and
  locks held during I/O.
- **Lost background failures:** spawned tasks, futures, promises or callbacks whose
  errors or panics nobody observes; detached work outliving its owner.
- **Cancellation and shutdown:** cancellation leaves partial state; shutdown drops
  queued work or skips cleanup; timeouts cancel without rollback.

## External resources

**Applies when:** files, sockets, database connections, transactions, locks,
temporary files or child processes.

- The resource is released on every path, including errors and early returns.
- A transaction is committed or rolled back on every path. Its scope matches the
  invariant it protects.
- A cleanup failure never replaces or hides the primary error.
- Temporary files and directories are removed, or ownership is handed off explicitly.

## Network calls

**Applies when:** HTTP or RPC clients, sockets, or external services.

- Every call has a timeout: connect, read and total.
- Retries are used only for idempotent operations, with backoff and a bound.
- The response status and body are checked before use. Partial responses are not
  treated as complete.
- TLS verification is never disabled outside tests. Redirects and proxies follow
  policy.

## Trust boundaries

**Applies when:** the code takes input from users, files, the network, the
environment, plugins, or models and tools.

- Input is validated at the boundary, before side effects.
- No injection: SQL, shell, path traversal, templates or deserialization.
- Authorization is enforced on every endpoint or operation, including on objects
  reached by ID.
- Untrusted text is escaped or encoded where it reaches logs, HTML or commands.

## Money, time and units

**Applies when:** prices, balances, quotas, schedules, durations or measurements.

- Money is never kept in floating point. Rounding is explicit and consistent.
- Time zones and daylight-saving changes are handled. Stored times carry their zone
  or are UTC.
- Durations use a monotonic clock, not wall time.
- Units are explicit: seconds versus milliseconds, bytes versus kilobytes or
  kibibytes. No silent conversion.

## Persistence and durability

**Applies when:** the code writes files, databases or state that must survive a
crash.

- Writes that must be atomic use a temporary file, then a rename, with fsync where
  required. No partial file is ever visible.
- Multi-step updates are in one transaction, or are idempotent and recoverable.
- Migrations are ordered and repeatable. A failed migration leaves the old state
  usable.
- Read paths reject corrupt or partial data instead of guessing.

## Numeric safety

**Applies when:** sizes, offsets, counters, conversions or arithmetic on external
values.

- No overflow, underflow or truncation in casts, sums or multiplications on
  untrusted sizes.
- Division by zero and empty-collection cases are handled.
- Signed and unsigned mixing does not change meaning.

## Bounds and growth

**Applies when:** queues, caches, buffers, pagination or collections fed by input.

- Every queue, cache and buffer that grows from input has a bound and an
  overflow policy.
- Queries and listings paginate or limit. No query loads an unbounded result.
- Retries, recursion and fan-out are bounded.

## Subprocesses

**Applies when:** the code launches other programs.

- The exit status is checked before output is used.
- Arguments are passed as a vector, never through a shell with untrusted text.
- The child's environment does not leak secrets. Inherited descriptors are
  intended.
- Children are reaped and killed on timeout. Process groups are cleaned up.

## Configuration and secrets

**Applies when:** environment variables, config files or credentials.

- Required configuration is validated at startup with a clear error.
- No secrets in code, logs, error messages or crash reports.
- Defaults are safe, and an unknown key is reported, not ignored.

## Contracts and compatibility

**Applies when:** public APIs, wire formats, stored formats or CLI flags.

- Parsing is strict. Unknown fields and values are rejected or deliberately allowed.
- Changes to stored or wire formats are versioned, with a migration or a refusal.
- Documented behavior matches the implementation and the tests.

## Project-specific families

Add one whenever the architecture has a hazard of its own. Examples: a custom
transaction or ledger layer, a plugin ABI, cache invalidation rules, a state machine
with illegal transitions, or a sandbox or permission model. Base each on the invariants
the project's docs and code state. Cite them as evidence.
