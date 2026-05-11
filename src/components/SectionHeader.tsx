import type { ReactNode } from "react";

type SectionHeaderProps = {
  title: string;
  controls?: ReactNode;
  marginBottom?: string;
};

export default function SectionHeader({ title, controls, marginBottom = "var(--space-md)" }: SectionHeaderProps) {
  return (
    <div
      style={{
        marginBottom,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "var(--space-sm)",
        flexWrap: "wrap",
      }}
    >
      <h3>{title}</h3>
      {controls ? <div>{controls}</div> : null}
    </div>
  );
}
