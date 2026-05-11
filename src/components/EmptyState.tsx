type EmptyStateProps = {
  text?: string;
};

export default function EmptyState({ text = "No data available." }: EmptyStateProps) {
  return <p className="text-secondary">{text}</p>;
}
