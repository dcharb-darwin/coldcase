import type { ReactNode } from "react";

type SectionCardProps = {
  title?: string;
  children: ReactNode;
  marginTop?: string;
};

export default function SectionCard({ title, children, marginTop }: SectionCardProps) {
  return (
    <div className="darwin-card" style={{ padding: "var(--space-lg)", ...(marginTop ? { marginTop } : {}) }}>
      {title ? <h3 style={{ marginBottom: "var(--space-md)" }}>{title}</h3> : null}
      {children}
    </div>
  );
}
