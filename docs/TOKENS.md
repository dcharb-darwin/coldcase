# Design Tokens — Actual Values

> Source of truth: `templates/src/index.css`. This doc names what each token **resolves to** so you can recognize values in reviews and debug tools. Never put raw hex / rem values in components — always `var(--token-name)`.
>
> Per [`PRINCIPLES.md §P5`](PRINCIPLES.md#p5-consistent-design-tokens).

---

## Colors — light mode

### Brand

| Token | Value | Use |
|---|---|---|
| `--color-primary` | `#2563eb` (blue-600) | Primary actions, active nav, focus rings, link color |
| `--color-primary-hover` | `#1d4ed8` (blue-700) | Hover state on primary |
| `--color-primary-soft` | `#dbeafe` (blue-100) | Primary badge bg, hover glow |
| `--color-on-primary` | `#ffffff` | Text on primary surfaces |

### Semantic status

| Token | Value | Use |
|---|---|---|
| `--color-success` | `#16a34a` (green-600) | Success badges, confirmed status |
| `--color-success-soft` | `#dcfce7` (green-100) | Success badge bg |
| `--color-warning` | `#d97706` (amber-600) | Warn badges, pre-due alerts |
| `--color-warning-soft` | `#fef3c7` (amber-100) | Warn badge bg |
| `--color-danger` | `#dc2626` (red-600) | Destructive actions, error text, overdue |
| `--color-danger-soft` | `#fca5a5` (red-300) | Danger badge bg (muted) |
| `--color-info` | `#0ea5e9` (sky-500) | Info, neutral-positive |
| `--color-info-soft` | `#e0f2fe` (sky-100) | Info badge bg |

### Surfaces + borders

| Token | Value | Use |
|---|---|---|
| `--color-bg` | `#f8fafc` (slate-50) | Page background |
| `--color-surface` | `#ffffff` | Cards, panels, nav rail |
| `--color-surface-hover` | `#f1f5f9` (slate-100) | Hover states on surfaces |
| `--color-surface-raised` | `#ffffff` | Modals, elevated cards |
| `--color-border` | `#e2e8f0` (slate-200) | Dividers, card borders |
| `--color-border-light` | `#f1f5f9` (slate-100) | Subtler dividers |
| `--color-overlay` | `rgba(15, 23, 42, 0.5)` | Modal backdrops |

### Text

| Token | Value | Use |
|---|---|---|
| `--color-text` | `#0f172a` (slate-900) | Body text, H1–H4 |
| `--color-text-secondary` | `#475569` (slate-600) | Secondary paragraphs, subtitles |
| `--color-text-muted` | `#94a3b8` (slate-400) | Captions, metadata, placeholder |

### Navigation

| Token | Value | Use |
|---|---|---|
| `--color-nav-active-bg` | `var(--color-primary)` | Active nav item background |
| `--color-nav-active-text` | `#ffffff` | Active nav item text |
| `--color-nav-hover-bg` | `#e2e8f0` | Nav item hover |
| `--color-nav-inactive-text` | `#475569` | Nav item rest state |

### Badges

| Token | Value | Use |
|---|---|---|
| `--color-badge-bg` | `#f1f5f9` (slate-100) | Neutral badge background |
| `--color-badge-text` | `#475569` (slate-600) | Neutral badge text |

Semantic badges combine `*-soft` bg + core text color:
- `badge-success` → `--color-success-soft` bg + `--color-success` text
- `badge-warning` → `--color-warning-soft` + `--color-warning`
- `badge-danger` → `--color-danger-soft` + `--color-danger`
- `badge-info` → `--color-info-soft` + `--color-info`
- `badge-neutral` → `--color-badge-bg` + `--color-badge-text`

---

## Colors — dark mode

Activated by `class="dark"` on `<html>` (manual toggle) or `prefers-color-scheme: dark` (future; not wired in POC). Overrides only the subset below; brand + semantic colors stay.

| Token | Value |
|---|---|
| `--color-bg` | `#0c1222` |
| `--color-surface` | `#162032` |
| `--color-surface-hover` | `#1e2e46` |
| `--color-surface-raised` | `#1e2e46` |
| `--color-border` | `#2a3a52` |
| `--color-border-light` | `#1e2e46` |
| `--color-overlay` | `rgba(0, 0, 0, 0.65)` |
| `--color-text` | `#e8edf5` |
| `--color-text-secondary` | `#94a3b8` |
| `--color-text-muted` | `#64748b` |
| `--color-nav-hover-bg` | `#1e2e46` |
| `--color-nav-inactive-text` | `#cbd5e1` |
| `--color-badge-bg` | `#1e2e46` |
| `--color-badge-text` | `#94a3b8` |

---

## Typography

### Font families

| Token | Stack |
|---|---|
| `--font-heading` | `"Space Grotesk", "Inter", system-ui, -apple-system, sans-serif` |
| `--font-body` | `"Inter", system-ui, -apple-system, sans-serif` |
| `--font-mono` | `"IBM Plex Mono", "Menlo", monospace` |

### Type scale

| Element | Size | Weight | Line height | Tracking |
|---|---|---|---|---|
| `h1` | `1.875rem` (30px) | 700 | 1.25 | -0.02em |
| `h2` | `1.5rem` (24px) | 700 | 1.25 | -0.02em |
| `h3` | `1.25rem` (20px) | 700 | 1.25 | -0.02em |
| `h4` | `1rem` (16px) | 700 | 1.25 | -0.02em |
| body | `0.875rem` (14px) | 400 | 1.6 | default |
| code / mono | `0.8125rem` (13px) | 400 | 1.5 | 0.02em |

`html { font-size: 16px }`; all `rem` values resolve against that.

---

## Spacing

Base unit: 4px. Scale:

| Token | rem | px | Common use |
|---|---|---|---|
| `--space-xs` | `0.25rem` | 4 | Icon-text gap, inline chip padding |
| `--space-sm` | `0.5rem` | 8 | Compact row padding, gap between related items |
| `--space-md` | `1rem` | 16 | Default padding, section spacing within a card |
| `--space-lg` | `1.5rem` | 24 | Card padding, section breaks |
| `--space-xl` | `2rem` | 32 | Page padding, major section gaps |
| `--space-2xl` | `3rem` | 48 | Large vertical rhythm (rare — hero sections) |

**Rule:** don't invent in-between values. If `--space-md` (16) feels too big and `--space-sm` (8) too small, the answer is "pick one."

---

## Border radius

| Token | rem | px | Use |
|---|---|---|---|
| `--radius-sm` | `0.375rem` | 6 | Inputs, small buttons |
| `--radius-md` | `0.625rem` | 10 | Default buttons, inputs, badges |
| `--radius-lg` | `0.75rem` | 12 | Cards (small) |
| `--radius-xl` | `1rem` | 16 | `.darwin-card` (primary card), panels |
| `--radius-full` | `9999px` | — | Pills, avatars, status chips |

---

## Shadows

| Token | Value | Use |
|---|---|---|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` | Cards at rest |
| `--shadow-md` | `0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -1px rgba(0,0,0,0.06)` | Cards on hover, dropdowns |
| `--shadow-lg` | `0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -2px rgba(0,0,0,0.05)` | Modals, popovers |
| `--shadow-xl` | `0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04)` | Major elevation (rare) |

---

## Motion

| Token | Value | When |
|---|---|---|
| `--transition-fast` | `150ms ease` | Color on hover, focus-ring appearance, link color |
| `--transition-base` | `200ms ease` | Most interactions — card lifts, nav collapse, panel open |
| `--transition-slow` | `300ms ease` | Major layout changes (sidebar width), page-level transitions |

**Rule:** prefer `--transition-base`. Reach for `--transition-fast` on high-frequency events (hover) and `--transition-slow` only when the user needs to track a larger visual change.

---

## Layout

| Token | Value | Use |
|---|---|---|
| `--nav-width` | `240px` | Sidebar expanded |
| `--nav-width-collapsed` | `64px` | Sidebar collapsed |
| `--topbar-height` | `56px` | Top bar fixed height |

Shell breakpoints live per-component today. When a responsive pass lands, it will extend this table.

---

## Focus ring

Defined globally on `:focus-visible`:

```css
outline: 2px solid var(--color-primary);
outline-offset: 2px;
```

This is the a11y floor. Custom focus rings must match contrast; see [`ACCESSIBILITY.md`](ACCESSIBILITY.md).

---

## Verifying tokens at build

1. `npm run build` — fails fast if a CSS var is referenced but not declared.
2. Search for hex literals: `rg '#[0-9a-fA-F]{3,6}' src/components/ src/features/` — should return empty. Matches are review-blocks.

---

## Extending tokens

Rare. Most "I need a new color" situations are solved by using the existing semantic palette differently. Before adding a token:

1. Check if a semantic mapping covers it (`danger-soft` often fills "muted red" requests).
2. If it's truly new, add to `index.css` **and** this doc in the same commit, with a use-case description.
3. Never fork per-app — if it belongs in the kit, upstream it.
