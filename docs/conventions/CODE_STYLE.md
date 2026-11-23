# Code Style

Snapshot of how this repo is written today. Follow it; if you must deviate, ask first.

## Python (backend)

- Python 3.12, `from __future__ import annotations`, type hints everywhere.
- Pydantic v2 models live in `app/schemas.py`; endpoints declare `response_model`,
  errors go out as `HTTPException` with Turkish `detail`.
- Stateless service modules under `app/services/`; module-level
  `logger = logging.getLogger(__name__)`.
- Tunables/secrets via `settings` (`app/config.py`) — never hardcoded.
- Turkish inline comments only where they explain a non-obvious why; no comment noise.

## TypeScript (frontend)

- Next.js App Router; `"use client"` only where interactivity requires it.
- Imports via the `@/` alias; all backend access through typed functions in
  `src/lib/api.ts` — no `fetch` inside components.
- Tailwind utility classes for layout; Turkish UI strings.
- Client-side `dynamic(..., { ssr: false })` for browser-only widgets (e.g. Leaflet map).

## Both

- ASCII identifiers and file names — Turkish only in user-facing strings/comments.
- Commit subjects ASCII.
