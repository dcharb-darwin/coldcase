type KeyValueItem = {
  label: string;
  value: string;
};

type KeyValueGridProps = {
  items: KeyValueItem[];
};

export default function KeyValueGrid({ items }: KeyValueGridProps) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "var(--space-md)" }}>
      {items.map((item) => (
        <p key={item.label}>
          <strong>{item.label}:</strong> {item.value}
        </p>
      ))}
    </div>
  );
}
