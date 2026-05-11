import type { ReactNode } from "react";

type PageHeaderProps = {
  title: string;
  subtitle?: string;
  action?: ReactNode;
};

export default function PageHeader({ title, subtitle, action }: PageHeaderProps) {
  return (
    <>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "var(--space-md)", marginBottom: "var(--space-md)" }}>
        <h1 style={{ margin: 0 }}>{title}</h1>
        {action ? <div>{action}</div> : null}
      </div>
      {subtitle ? (
        <p style={{ color: "var(--color-text-secondary)", marginBottom: "var(--space-lg)" }}>{subtitle}</p>
      ) : null}
    </>
  );
}
