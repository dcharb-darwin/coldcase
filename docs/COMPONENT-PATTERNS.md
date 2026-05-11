# Component Patterns

> How and when to use the kit's primitives. When to reach for one, when to compose, when to extract a new one.

## The extraction rule

Don't pre-extract. Inline JSX with tokens is fine. Extract when **at least one** is true:

1. **Three or more sites use the same shape.** The rule of three.
2. **Meaningful variance pressure.** The shape is stable but prop surface is shifting — pulling it into one place stops copy-paste drift.
3. **Accessibility requires it.** E.g. a focus-trap modal isn't something you want duplicated.
4. **It's in the kit already.** Don't recreate — import from `@/components` or extend.

Signals you should NOT extract:
- Used once.
- "Someone might need this later."
- It's already `<PageSection><SectionCard>…</SectionCard></PageSection>` — that's composed primitives, not a new primitive.

## Layout primitives

### `PageFrame`

Outer wrapper for every route-level page. Gives max-width and consistent padding.

```tsx
import { PageFrame } from "@/components";

export default function MyPage() {
  return (
    <PageFrame>
      {/* everything */}
    </PageFrame>
  );
}
```

### `PageHeader`

First thing inside `PageFrame`. Title + subtitle + optional action. Per `PRINCIPLES.md §P3` breadcrumbs live in the app shell, not inside PageHeader.

```tsx
<PageHeader
  title="Employees"
  subtitle="All hires — status + next step"
  action={<button className="btn btn-primary">+ New Hire</button>}
/>
```

### `PageSection`

Vertical spacing wrapper between logical regions on a page. Accepts `marginTop` override.

```tsx
<PageSection marginTop="var(--space-lg)">
  <SectionCard>…</SectionCard>
</PageSection>
```

### `SectionCard`

The `.darwin-card` surface with consistent padding. Doesn't own its own title — put `SectionHeader` inside if you need one.

### `SectionHeader`

Title + optional controls row inside a `SectionCard`. Used when a card has a toolbar (filter, sort, bulk actions).

### `PageActionRow`

Left/right split for top-of-page action controls that don't fit in `PageHeader`'s `action` prop. Back buttons, breadcrumb extras.

### `KeyValueGrid`

Two-column summary — label / value pairs. Used on detail pages for profile / metadata.

```tsx
<KeyValueGrid items={[
  { label: "Department", value: "Operations" },
  { label: "Hire date", value: "2026-04-20" },
]} />
```

### `StatGrid`

Three-column stat cards. Clickable if `navigateTo` is set (per `PRINCIPLES.md §P1` — every visible number drills somewhere).

```tsx
<StatGrid
  items={[
    { label: "Employees", value: 18, navigateTo: "/employees" },
    { label: "Open tasks", value: 60, navigateTo: "/employees?filter=open" },
  ]}
  onNavigate={setHashPath}
/>
```

### `PageBadges`

Row of semantic badges above a page header. Scope / environment / status hints.

## Data-state primitives (Empty / Loading / Error)

These three are the **required pattern** for every async data panel. `DataPanel` composes them.

### `DataPanel`

One-stop wrapper for a card that fetches data. Chooses between loading, error, and rendered states based on props.

```tsx
<DataPanel
  title="Tasks"
  isLoading={tasksQuery.isLoading}
  isError={tasksQuery.isError}
  loadingText="Loading tasks..."
  errorText="Unable to load tasks."
>
  {items.length === 0 ? (
    <EmptyState text="No tasks match this filter." />
  ) : (
    <TaskTable tasks={items} />
  )}
</DataPanel>
```

### `EmptyState`

Not a blank card. Always says **what the user should do next**. Per `PRINCIPLES.md` tone.

```tsx
<EmptyState text="No emails in the queue. Intake a new hire to generate one." />
```

**Anti-patterns:**
- "Nothing here." (says nothing)
- "No data." (says nothing)
- A sad face with no text (accessibility + tone fail)

### `LoadingState`

Simple text + subtle spinner. Use inside `DataPanel` via the `isLoading` prop; direct use only when rendering outside a panel.

### `ErrorState`

Red-tinted text + retry suggestion when available. Always says **what might fix it**.

```tsx
<ErrorState text="Could not reach the email service. Is the backend running?" />
```

## Action primitives

### `.btn` — button base

Shipped in `index.css`. Composes with variants.

| Class | Use | Example |
|---|---|---|
| `.btn .btn-primary` | Primary action, one per page/form | Submit, Save, + New Hire |
| `.btn .btn-secondary` | Secondary + tertiary actions | Cancel, Edit, Preview |
| `.btn .btn-ghost` | Tertiary, low-emphasis | Clear, Reset |
| `.btn .btn-danger` | Destructive | Delete |

Rules:
- **One `.btn-primary` per page region.** Two primaries compete for attention; demote one.
- **Destructive actions require confirm.** Per `PRINCIPLES.md §P6`. Use `confirm()` for POC, a confirm modal for production.
- **Icon-only buttons need `aria-label`.** Per `ACCESSIBILITY.md`.
- **Disabled state uses `opacity: 0.6`** (shipped in `.btn`). Don't re-style.

### Nav items (`.app-shell__nav-item`)

Inside the shell sidebar. Active state auto-applied from the route. Collapsible-mode icon-only layout is in the CSS; don't override.

### `PaginationControls`

Previous/Next + page indicator. Used inside any `DataPanel` that paginates.

```tsx
<PaginationControls
  page={page}
  totalPages={totalPages}
  isBusy={query.isFetching}
  onPrevious={() => setPage(p => p - 1)}
  onNext={() => setPage(p => p + 1)}
/>
```

## Dialog primitives

### `Modal`

Portal-rendered (escapes CSS transform traps per `PATTERNS.md §9`). Size tiers `sm | md | lg`. Escape closes.

```tsx
<Modal open={isOpen} onClose={() => setIsOpen(false)} title="Edit template" size="lg">
  {/* form */}
</Modal>
```

Rules:
- **Use for real modals only.** Not for popovers, tooltips, menus. Those are different primitives (not yet in the kit — add when the first real use lands).
- **Focus trap is not yet implemented** (TODO in `src/components/Modal.tsx`). Long-lived or form-heavy modals should add one locally until the kit patches.
- **Don't stack modals.** If a modal spawns another modal, the UX is wrong — restructure.
- **Don't put primary actions in the modal body.** Footer only (border-top, right-aligned, secondary-then-primary order).

### Confirm dialog

Not a separate primitive today; use `window.confirm()` for POC destructive actions. When the first real customer-facing destructive flow lands, extract a `ConfirmModal` component.

## Form patterns

Not extracted into kit primitives today — apps hand-build forms with Tailwind utilities. When three apps have the same form shape, extract.

Rules that apply regardless:

- **Field layout:** `<label>` above input. Don't use placeholder as label (a11y).
- **Required marker:** visible `*` + `aria-required="true"`.
- **Error placement:** below the field, red text, linked via `aria-describedby`. Not in a tooltip.
- **Validation timing:** on blur, not on keystroke. Immediate on submit-attempt.
- **Submit button:** `.btn-primary` at form end. Disabled during submission with `aria-busy="true"`.
- **Cancel button:** `.btn-secondary` to the left of submit.
- **Inline error at page top:** only for cross-field or network errors. Use `ErrorState` or a dedicated banner.

Example:

```tsx
<form onSubmit={onSubmit}>
  <label className="flex flex-col gap-1">
    <span className="font-medium">Email <span className="text-danger">*</span></span>
    <input
      type="email"
      required
      aria-required="true"
      aria-describedby={emailError ? "email-error" : undefined}
      className={input}
      value={email}
      onChange={(e) => setEmail(e.target.value)}
    />
    {emailError ? (
      <span id="email-error" className="text-sm text-danger">{emailError}</span>
    ) : null}
  </label>
  {/* more fields */}
  <div className="flex justify-end gap-2 pt-4 border-t">
    <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
    <button type="submit" className="btn btn-primary" disabled={submitting} aria-busy={submitting}>
      {submitting ? "Saving…" : "Save"}
    </button>
  </div>
</form>
```

## Table patterns — `.darwin-table`

Shipped in `index.css`. Apps use it directly for tabular data.

Rules:

- **Columns have meaningful headers.** Every `<th>` has text. Icon-only headers are forbidden.
- **Sort UX:** clickable column headers with ascending/descending arrow + `aria-sort`. The kit doesn't ship a sortable-table component today; implement locally, extract when the third app needs it.
- **Row click behavior:** if entire rows are clickable, cursor changes to `pointer` + `:hover` background. Action buttons inside a row `stopPropagation()` to avoid double-triggers.
- **Zebra striping:** off by default. Turn on with a local modifier if density demands it — usually doesn't.
- **Empty-table:** inside the `<tbody>` render an `<EmptyState />` inside a row that spans all columns.
- **Pagination:** `PaginationControls` below the table, not above.

## Icons

Kit uses **inline SVGs** (see `src/shell/AppShell.tsx` nav icons). Rules:

- **Size standard:** `18×18` for nav + top bar, `16×16` for inline-with-text, `24×24` for feature illustrations.
- **`stroke="currentColor"` + `fill="none"`** — inherits text color, works in light + dark mode without overrides.
- **`aria-hidden` on decorative icons** (paired with a text label).
- **`aria-label` on icon-only buttons.**
- **No icon library dependency yet.** If you need an icon not in the kit, write the SVG inline. When the fifth "I need an icon" lands in one session, propose adding Lucide-React (or equivalent) as a discrete kit upgrade.

## Toast / flash / inline notification

Not yet in the kit. Top-bar bell is a planned slot (HR Coordinator has one; not generic yet).

Until extracted, transient feedback lives in:
- `<ErrorState>` for panel-level failures
- `alert()` for destructive confirmation (POC only)
- Inline status text next to the action button (mutations render "Saving…" on the button + error text next to it)

When adding toasts: use `role="status"` for non-urgent (per `ACCESSIBILITY.md`), auto-dismiss after 4s, max 3 stacked.

## When to add a new kit primitive

1. Third app hits the same shape.
2. Accessibility need isn't portable.
3. Variance pressure (prop surface, responsive rules).

Process:
1. Propose in a kit PR with the current three call sites.
2. Extract into `templates/src/components/<Name>.tsx`.
3. Update `components/index.ts` barrel.
4. Document in this file with usage example.
5. Refactor the three call sites to use the new primitive.
6. Bump kit minor version in CHANGELOG.

## What this doc does NOT cover

- Charts / data visualization (no apps use them yet).
- Drag-and-drop (no apps use it yet).
- Calendar / date-picker UI (HR Coordinator uses native `<input type="date">` — when we need a richer picker, extract).
- Rich-text editor (SOP Builder has one; not portable yet).
- Photo / file upload UI (simple `<input type="file">` works today; extract when three apps need the same pattern).

See also:
- [`PRINCIPLES.md`](PRINCIPLES.md) — P1–P6 + agentic principles
- [`TOKENS.md`](TOKENS.md) — value reference
- [`ACCESSIBILITY.md`](ACCESSIBILITY.md) — a11y floor
- [`CONVENTIONS.md`](CONVENTIONS.md) — coding conventions
