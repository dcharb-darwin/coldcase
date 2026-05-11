/**
 * ViewModeToggle — two-button segmented control for switching a
 * collection view between cards and list. Pair with `useViewMode`
 * (src/lib/useViewMode.ts) for localStorage persistence.
 *
 * Launchpad P2: "Cards + list toggle" across every collection view.
 *
 * Visual spec: two icon+label buttons in a rounded group. Active
 * button uses `--color-primary-soft` background + `--color-primary`
 * text; inactive uses `--color-surface-hover` / `--color-text-secondary`.
 */

import type { CSSProperties } from "react";

export type ViewMode = "cards" | "list";

interface Props {
  value: ViewMode;
  onChange: (next: ViewMode) => void;
  /** Optional custom labels (defaults: "Cards" / "List"). */
  cardsLabel?: string;
  listLabel?: string;
  className?: string;
}

export function ViewModeToggle({
  value,
  onChange,
  cardsLabel = "Cards",
  listLabel = "List",
  className,
}: Props) {
  return (
    <div
      role="group"
      aria-label="View mode"
      className={className}
      style={containerStyle}
    >
      <ToggleButton
        active={value === "cards"}
        onClick={() => onChange("cards")}
        aria-label="Card view"
      >
        <CardsIcon />
        <span>{cardsLabel}</span>
      </ToggleButton>
      <ToggleButton
        active={value === "list"}
        onClick={() => onChange("list")}
        aria-label="List view"
      >
        <ListIcon />
        <span>{listLabel}</span>
      </ToggleButton>
    </div>
  );
}

interface ToggleButtonProps {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  "aria-label": string;
}

function ToggleButton({ active, onClick, children, "aria-label": ariaLabel }: ToggleButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      aria-label={ariaLabel}
      style={{
        ...buttonStyle,
        background: active ? "var(--color-primary-soft)" : "transparent",
        color: active ? "var(--color-primary)" : "var(--color-text-secondary)",
        fontWeight: active ? 600 : 500,
      }}
    >
      {children}
    </button>
  );
}

function CardsIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
      <rect x="1" y="1" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="9" y="1" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="1" y="9" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="9" y="9" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function ListIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
      <line x1="2" y1="4" x2="14" y2="4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="2" y1="8" x2="14" y2="8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="2" y1="12" x2="14" y2="12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

const containerStyle: CSSProperties = {
  display: "inline-flex",
  gap: 4,
  padding: 3,
  borderRadius: "var(--radius-md)",
  border: "1px solid var(--color-border)",
  background: "var(--color-surface)",
};

const buttonStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  padding: "4px 10px",
  border: "none",
  borderRadius: "var(--radius-sm)",
  fontSize: "0.8125rem",
  cursor: "pointer",
  transition: "background var(--transition-fast), color var(--transition-fast)",
};
