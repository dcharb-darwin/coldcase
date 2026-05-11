# Branding — Cold Case

> Per-app branding contract. Tokens in `src/index.css` are the source; this doc is the reference for what they encode.

## Colors

App accent: `--color-primary` (default: Darwin emerald `#10b981`).

Override by editing `src/index.css` `:root` declaration — never raw hex in components. Per P5.

## Logo

Location: `src/assets/logo.*` (add as needed).

Usage: top bar of `AppShell` renders `Cold Case` as text when no logo is present. Drop a 40×40 SVG at `src/assets/logo.svg` and update `AppShell.tsx` to render it.

## Typography

Heading font: `var(--font-heading)` — default `'Inter', system-ui, sans-serif`.
Body font: `var(--font-body)` — same stack.
Monospace: `ui-monospace, 'JetBrains Mono', monospace` (used for codes / IDs).

## Tone

Copy style:
- Sentence case, not title case.
- No exclamation points in navigation.
- Errors explain what happened + what to do.
- Empty states say what the user should do next, not "nothing here."

## Dark mode

Tokens ship with dark mode via `prefers-color-scheme: dark`. Override not supported (would break consistency across Launchpad apps).

## Out of scope

- Custom fonts beyond the system stack.
- Per-tenant logo upload (future feature, not at MVP).
- App icon for PWA (until the app is packaged).
