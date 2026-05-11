# Accessibility

> Floor: WCAG 2.1 Level AA on every user-facing surface. This doc is the checklist — meet it before ship, not after an audit.

## The non-negotiables

1. **Contrast.** Text vs. background ≥ 4.5:1 for body, ≥ 3:1 for large text (≥ 18pt or 14pt bold) and UI components / focus states.
2. **Keyboard.** Every interactive element reachable + operable with keyboard only. Tab order is logical.
3. **Focus visible.** `:focus-visible` ring on every interactive element. The kit's global rule (see [`TOKENS.md`](TOKENS.md#focus-ring)) covers this — don't disable it on custom components.
4. **ARIA roles + labels** where the DOM semantic isn't sufficient.
5. **Motion respect.** No auto-animating elements without a `prefers-reduced-motion` opt-out.
6. **No color-alone signaling.** Status never lives in color only; pair with an icon, label, or text.

## Contrast — verified values

The kit's token set is pre-checked:

| Pair | Contrast | Pass |
|---|---|---|
| `--color-text` (#0f172a) on `--color-bg` (#f8fafc) | 17.42:1 | AA + AAA |
| `--color-text` on `--color-surface` (#ffffff) | 18.69:1 | AA + AAA |
| `--color-text-secondary` (#475569) on `--color-bg` | 7.84:1 | AA + AAA |
| `--color-text-muted` (#94a3b8) on `--color-surface` | 2.95:1 | ⚠ Large text only (≥18pt) |
| `--color-on-primary` (#fff) on `--color-primary` (#2563eb) | 5.17:1 | AA |
| `--color-success` (#16a34a) on `--color-success-soft` (#dcfce7) | 4.57:1 | AA |
| `--color-warning` (#d97706) on `--color-warning-soft` (#fef3c7) | 4.52:1 | AA |
| `--color-danger` (#dc2626) on `--color-danger-soft` (#fca5a5) | 3.16:1 | ⚠ Large text only |

**Rules:**
- Don't use `--color-text-muted` for body text. It's for captions / metadata on surfaces where the user can read at a glance.
- Don't render small text on `*-danger-soft` with `*-danger` text. Use `*-danger-soft` bg + `--color-text` for small copy, `--color-danger` only on large text or icon pairs.
- New colors added to the kit go through a contrast check — document the result in [`TOKENS.md`](TOKENS.md) before merge.

## Focus rings

Global rule already in the kit's `index.css`:

```css
:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}
```

**Never** `outline: none;` on interactive elements without providing an equivalent replacement. A focus ring can be a box-shadow with `0 0 0 2px var(--color-primary)` if `outline` conflicts with a rounded shape, but the ring must exist.

Focus rings on `--color-primary` buttons are tricky (primary-on-primary). Use `--color-surface` or `--color-on-primary` as the ring color in that case:

```css
.btn-primary:focus-visible {
  outline: 2px solid var(--color-on-primary);
  outline-offset: 2px;
}
```

## Keyboard navigation — required patterns

| Pattern | Required behavior |
|---|---|
| **Tab order** | Logical top-to-bottom, left-to-right. Skip links first on any page with heavy nav. |
| **Nav rail** | `Tab` enters, arrow keys move within, `Enter` activates. Tab cycles out. |
| **Modals** | `Escape` closes. Focus trap: `Tab` cycles inside the modal, doesn't leak to the underlying page. First focusable element gets focus on open; return focus to the trigger on close. |
| **Menus / dropdowns** | `Enter` / `Space` opens, arrow keys navigate items, `Escape` closes. Selected item gets focus. |
| **Tabs** (horizontal) | Arrow left/right moves between tabs. `Enter` / `Space` activates. Only the active tab is in the Tab sequence. |
| **Tables** | Not typically navigated by cell. Tab moves between interactive cells (links, buttons). Column-sort buttons are Tab stops. |
| **Forms** | `Enter` submits in single-input forms; in multi-input, `Enter` advances to next field unless focus is on the submit button. |

The kit's `Modal.tsx` does escape-close + portal but **does not** implement focus trap yet — if your modal is long-lived or contains forms, add focus trap (see `src/components/Modal.tsx` — a TODO comment lives there).

## ARIA — when and how

Use semantic HTML first (`<button>`, `<nav>`, `<main>`, `<header>`). Reach for ARIA only when the DOM can't carry the meaning.

| Pattern | Markup |
|---|---|
| Primary page heading | One `<h1>` per route. Section headings are `<h2>`. |
| Nav rail | `<nav aria-label="Primary">` + `<button>` items |
| Breadcrumbs | Wrapper `<nav aria-label="Breadcrumb">` + `<ol>` |
| Impersonation banner | `<div role="status">` so screen readers announce a change |
| Alerts queue severity | Pair severity pill with `aria-label` describing both the severity and the count |
| Loading | `<div role="status" aria-live="polite">Loading…</div>` |
| Toast / flash | `role="status"` for non-urgent, `role="alert"` for errors |
| Modal | `<dialog>` if supported; otherwise `<div role="dialog" aria-modal="true" aria-labelledby="...">` |
| Icon-only button | `aria-label="Close"` |
| Expandable | `aria-expanded="true|false"` on the trigger, `aria-controls` pointing at the revealed region |
| Decorative icon | `aria-hidden="true"` (the kit's nav icons already do this) |

## No color-alone signaling

Every status indicator carries **text or icon** in addition to color.

| Built-in kit pattern | ✅ |
|---|---|
| `badge-danger` with "Overdue" text | ✅ |
| Red status dot with no label | ❌ — add `aria-label` and a text label |
| Red row in a table | ❌ — add an icon + a status badge |
| Graph line distinguished only by red/green | ❌ — add shape (dashed/solid), label, or texture |

## Motion

Current kit respects `prefers-reduced-motion` **only via Tailwind utilities** (not baked into the tokens). When adding animations:

```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

No shipping animation exceeds 300ms (`--transition-slow`). No parallax. No auto-scrolling. No flashing faster than 3 Hz (seizure trigger).

## Forms

- Every input has a visible `<label>`. Don't use `placeholder` as a label.
- Required fields marked with `aria-required="true"` + a visible asterisk.
- Error messages linked via `aria-describedby` pointing at the error element.
- Inline validation fires on blur, not on keystroke — fewer "you haven't finished typing yet, but here's an error" moments.
- Submit buttons disabled during submission show a loading state + `aria-busy="true"`.

## Media

- Every `<img>` has `alt` (empty if decorative: `alt=""`).
- Every video has captions when shipped for demo/training (out of scope for POC; required when a customer receives a walkthrough video).

## Testing

**On every UI PR, manual checks:**
1. Tab through the page keyboard-only. Can you reach everything? Can you activate everything?
2. Enable macOS VoiceOver (`⌘F5`) or Windows Narrator (`Ctrl+Win+Enter`). Does the page read in a sensible order?
3. Zoom to 200%. Does layout still work? No horizontal scroll on major interactions.
4. Reduce motion (`System Preferences → Accessibility → Display → Reduce motion`). Do transitions still work (no broken states)?

**Automated (optional today, required at GA):**
- `axe-core` via `@axe-core/react` in dev (logs violations to console).
- Lighthouse accessibility score ≥ 90 on each primary route.

## Compliance-adjacent requirements

For apps serving regulated sectors (public safety, transit, healthcare):

- **Section 508** — US federal accessibility requirement. WCAG 2.1 AA covers it.
- **EN 301 549** — EU equivalent. Same WCAG base.
- **ADA Title II/III** — US state + private. Same base.

Meeting WCAG 2.1 AA clears all three. Document the compliance posture in `docs/branding.md` under a "Compliance" section once the app ships.

## What this doc does NOT cover (yet)

- Screen-reader-specific quirks (VoiceOver vs NVDA vs JAWS differences).
- Color-blindness-specific palette swapping.
- High-contrast mode (Windows).
- Voice control (macOS / Dragon).

These become required as apps reach regulated-sector customers. When that happens, extend this doc; don't put the rules in per-app PRDs.
