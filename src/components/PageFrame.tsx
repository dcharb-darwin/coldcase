import type { ReactNode } from "react";

type PageFrameProps = {
  children: ReactNode;
  maxWidth?: number;
};

export default function PageFrame({ children, maxWidth = 1100 }: PageFrameProps) {
  return (
    <div
      style={{
        padding: "var(--space-xl)",
        background: "var(--color-bg)",
        color: "var(--color-text)",
      }}
    >
      <div className="animate-fade-in" style={{ maxWidth, margin: "0 auto" }}>
        {children}
      </div>
    </div>
  );
}
