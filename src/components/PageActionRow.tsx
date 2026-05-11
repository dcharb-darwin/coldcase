import type { ReactNode } from "react";

type PageActionRowProps = {
  left?: ReactNode;
  right?: ReactNode;
  marginBottom?: string;
};

export default function PageActionRow({ left, right, marginBottom = "var(--space-md)" }: PageActionRowProps) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: "var(--space-sm)",
        flexWrap: "wrap",
        marginBottom,
      }}
    >
      <div>{left}</div>
      <div>{right}</div>
    </div>
  );
}
