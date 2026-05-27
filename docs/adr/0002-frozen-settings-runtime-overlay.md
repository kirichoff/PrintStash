# ADR-0002: Frozen settings + RuntimeOverlay, not mutable singleton

**Status:** accepted

The global `settings` singleton is split into two modules: a **frozen**
env-only `Settings` (never mutated after import) and a separate `RuntimeOverlay`
(DB-backed, mutable). A `ConfigResolver` provides the single read-path:
`effective = overlay[key] ?? frozen[key]`.

## Why

Before this decision, `settings` was mutated from three places:
environment variables at import time, `apply_overlay()` at startup, and
`update_config()` from API calls. Any module that imported `settings` was
implicitly coupled to runtime config mutations — a configuration change
touched every module simultaneously with no observable signal.

The split eliminates silent mutation. Callers that need runtime-overridable
values read through `ConfigResolver`. Callers that only need env-fixed values
read the frozen `Settings` directly.

## Considered Options

- **Mutable singleton** (current — rejected because non-local mutation makes
  configuration state impossible to reason about in tests and logs)
- **ConfigResolver with attribute access** (chosen — `get_config().data_dir`
  feels like the old `settings.data_dir`, minimizing migration churn at 16+
  call sites)
- **ConfigResolver with dict access** (rejected — `get_config()['data_dir']`
  is more explicit but adds friction at every call site for a benefit that
  hasn't materialized)

## Consequences

- `RuntimeOverlay` and `ConfigResolver` share a dict protected by `asyncio.Lock`
  for propagation. One write-path (overlay), one read-path (resolver).
- `settings` becomes a frozen module-level singleton — safe to import anywhere
  without coupling to runtime config.
- Tests can inject overlay values directly into the resolver for config-dependent
  test scenarios without touching env vars or the DB.
