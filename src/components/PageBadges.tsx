export type PageBadgeItem = {
  text: string;
  variant: "primary" | "success" | "warning" | "danger" | "neutral";
};

type PageBadgesProps = {
  items: PageBadgeItem[];
};

export default function PageBadges({ items }: PageBadgesProps) {
  return (
    <div style={{ display: "flex", gap: "var(--space-sm)", marginBottom: "var(--space-lg)", flexWrap: "wrap" }}>
      {items.map((item) => (
        <span key={`${item.variant}-${item.text}`} className={`badge badge-${item.variant}`}>
          {item.text}
        </span>
      ))}
    </div>
  );
}
