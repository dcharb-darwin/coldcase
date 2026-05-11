export type StatItem = {
  label: string;
  value: string | number;
  navigateTo?: string;
};

type StatGridProps = {
  items: StatItem[];
  onNavigate?: (path: string) => void;
};

export default function StatGrid({ items, onNavigate }: StatGridProps) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
        gap: "var(--space-md)",
        marginBottom: "var(--space-xl)",
      }}
    >
      {items.map((item) => {
        const body = (
          <>
            <p className="text-secondary" style={{ marginBottom: "var(--space-xs)" }}>
              {item.label}
            </p>
            <h2 style={{ fontSize: item.navigateTo && typeof item.value === "string" ? "1rem" : undefined, lineHeight: 1.35 }}>
              {item.value}
            </h2>
            {item.navigateTo ? (
              <p className="text-muted" style={{ marginTop: "var(--space-sm)", fontSize: "0.75rem" }}>
                Click to open
              </p>
            ) : null}
          </>
        );
        const key = item.label;
        if (item.navigateTo && onNavigate) {
          return (
            <button
              key={key}
              type="button"
              className="darwin-card"
              style={{
                padding: "var(--space-lg)",
                textAlign: "left",
                width: "100%",
                cursor: "pointer",
                font: "inherit",
                color: "inherit",
                border: "none",
                background: "var(--color-surface)",
              }}
              onClick={() => onNavigate(item.navigateTo!)}
              aria-label={`${item.label}: ${item.value}. Open related view.`}
            >
              {body}
            </button>
          );
        }
        return (
          <div key={key} className="darwin-card" style={{ padding: "var(--space-lg)" }}>
            {body}
          </div>
        );
      })}
    </div>
  );
}
