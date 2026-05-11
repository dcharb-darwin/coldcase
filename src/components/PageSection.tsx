import type { ReactNode } from "react";

type PageSectionProps = {
  children: ReactNode;
  marginTop?: string;
};

export default function PageSection({ children, marginTop }: PageSectionProps) {
  return <div style={marginTop ? { marginTop } : undefined}>{children}</div>;
}
