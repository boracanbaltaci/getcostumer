# <Name> Module

One document per backend service or frontend feature area, written when the module
is created and updated whenever its contract changes. Copy this file to
`docs/systems/<name>.md`, delete this preamble, and fill every section — a
section with nothing to say gets `None`, it is not deleted.

## Scope

This document governs `backend/app/services/<name>.py` (or the named frontend
area). Always apply root `AGENTS.md` and `README.md` first.

## Responsibilities

- <!-- what the module owns, one bullet each -->

## Does NOT Own

- <!-- explicit exclusions; boundary conflicts are resolved here, not in code -->

## Surface Exposed

| Endpoint / export | Purpose | Consumers |
|---|---|---|
| `GET/POST /api/<x>` or `<export>` | <!-- --> | <!-- --> |

## Dependencies Consumed

- <!-- settings keys, other services, external APIs, DB tables -->

## Integration Points

- <!-- how it is wired: celery tasks, importers, api.ts functions, env vars -->

## Guardrails

### Do Not Place Here

- <!-- e.g. endpoint logic inside a service, other modules' data shaping -->

### Do Not Modify Without Request

- <!-- frozen surfaces: schema fields, shared types, cost-bearing external calls -->

### Forbidden Patterns

- <!-- module-specific forbidden patterns, on top of the global ones -->

## Data & State

- <!-- tables/files/caches this module owns; idempotency expectations -->

## Testing

- Backend: <!-- pure logic to cover with pytest -->
- Frontend: <!-- behavior to cover / manual path -->

## Verification Gates

Before closing any change to this module:

- [ ] Backend imports clean / frontend `typecheck` + `lint` clean — evidence, not assumption
- [ ] Contract surface unchanged OR all consumers updated in the same change
- [ ] Verified through the real user path (HTTP request / running app)
- [ ] No Immutable Rule violation in touched scope
