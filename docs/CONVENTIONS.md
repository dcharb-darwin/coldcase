# Coding Conventions

## Python

- **PEP 8** formatting. Type hints on every public function. Google-style docstrings when the "why" isn't obvious from the signature.
- **No file over 500 lines.** Refactor at the cap. See `PATTERNS.md` §12.
- **Async FastAPI handlers** for I/O. Sync for pure compute.
- **MongoEngine ODM** for persistence. Documents live at `server-py/models/documents.py` (or a folder for very large apps). One class per collection.
- **`pydantic-settings`** for config. Every env-readable knob is a `Field(...)` with `validation_alias=AliasChoices(...)`.
- **Pydantic body models are module-scope**, never nested inside a factory. Nested definitions confuse FastAPI and produce 422s.
- **Routers**: one file per domain entity. `prefix="/<entity>"` at construction, not on each route. Enum validation via `Query(default=None, pattern="^(a|b|c)$")`.
- **Services**: business logic lives in `server-py/services/*.py`. Routers call services; services call models. Routers don't write DB directly except for trivial CRUD.

## TypeScript / React

- **React 19, Vite, strict TS.** `noUncheckedIndexedAccess` on.
- **Never `any`.** Use `unknown` + narrow, or define the type.
- **Axios, not fetch.** Single client in `src/lib/api/client.ts` with interceptors (impersonation header + FastAPI `detail`→`error.message` rewrite).
- **TanStack Query 5.** React Query keys centralized in `src/lib/queryKeys.ts`. No raw `useEffect` data loading.
- **Feature scopes** (`src/features/<name>/`) own their pages, components, hooks, types. Cross-feature code in `src/lib/` or `src/components/`.
- **Hash routing.** Routes in `src/shell/routes.ts` as `ROUTES = { ... } as const`. Guards via `is<X>Route(path)` helpers. Never hardcode a route string in a component.
- **Design tokens only.** CSS custom properties from `src/index.css`. Raw hex/rgb in components is a review-block.

## Naming

- Files: `kebab-case.ts` / `kebab-case.tsx`. Components are `PascalCase.tsx` where the file name matches the exported component.
- Python: `snake_case.py`. Classes `PascalCase`. Constants `SCREAMING_SNAKE`.
- Git branches: `feat/<short-description>`, `fix/<short>`, `chore/<short>`.
- Commit trailers: `[trace: <slug>]`. Slug is `<app-short>-<concern>` e.g. `rtchr-alerts`, `kit-bootstrap`.

## Commit hygiene

- Every feat/fix/chore ends with `[trace: <slug>]`. See `PATTERNS.md` §11.
- One concern per commit. Retrofits split: ports → named volume → admin pattern → scaffold files → governance → docs.
- Git identity: `dcharb-darwin <daniel.charboneau@darwingov.com>` for all Launchpad work.
- Never `--amend` a pushed commit. Never `--no-verify`. Never force-push to `main`.

## Testing

- **Backend:** pytest (or `unittest` for kit-simple). One test file per router minimum. Integration tests hit real Mongo (env-driven URL) — no mocks for the DB layer.
- **Frontend:** type safety via `tsc --noEmit` (`npm run check`) is the floor. Component tests when the component has branching logic; not required for presentation-only.
- **CI:** out of scope for the kit. Each app wires its own.

## Logging

- Backend: stdlib `logging`. `logger = logging.getLogger(__name__)` at module top. WARN for unexpected-but-recoverable, ERROR for bugs. No `print(...)` in checked-in code.
- Frontend: `console.error(...)` for network / mutation failures. No `console.log` in checked-in code except during active debugging.

## Environment

- **Ports from `.env`.** Durable rule. See `PATTERNS.md` §6.
- **Python venv at `.venv/`.** Gitignored.
- **Node modules at `node_modules/`.** Gitignored.
- **Secrets never committed.** `.env` gitignored; `.env.example` ships the shape.

## Documentation

- Every app has: `README.md`, `AGENTS.md`, `CLAUDE.md`, `STRUCTURE.md`, `SESSION_STATE.md`, `docs/comprehensive-prd.md`, `docs/architecture.md`, `docs/branding.md`.
- The PRD is a living doc; regenerate via the `regenerate-full-prd` workflow when behavior materially changes.
- `SESSION_STATE.md` is rewritten at end of every Claude Code / Cowork session.
- Architecture diagram auto-generated — see `PATTERNS.md` §10.

## Comments

- Default to writing no comments. Let the code name itself.
- Comment the *why* when it's non-obvious — a constraint, a workaround, a hidden invariant. Don't comment the *what*.
- Never reference the current task / ticket / feature in a comment ("used by X", "added for Y") — that rots; it belongs in the PR description.

## Dependencies

- **Python**: pin minor versions in `requirements.txt` (`fastapi>=0.115.0,<1.0.0`). Editable installs for local darwin-* packages in `requirements-local.txt`.
- **Node**: caret-pinned (`^19.0.0`). Lock file committed.

Upgrades are discrete commits with a trace slug (`[trace: <slug>-deps-react-20]`).
