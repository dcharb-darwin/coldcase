import type { ReactNode } from "react";
import ErrorState from "./ErrorState";
import LoadingState from "./LoadingState";
import SectionCard from "./SectionCard";

type DataPanelProps = {
  title?: string;
  isLoading?: boolean;
  isError?: boolean;
  loadingText?: string;
  errorText?: string;
  marginTop?: string;
  children: ReactNode;
};

export default function DataPanel({
  title,
  isLoading = false,
  isError = false,
  loadingText = "Loading...",
  errorText = "Something went wrong.",
  marginTop,
  children,
}: DataPanelProps) {
  return (
    <SectionCard title={title} marginTop={marginTop}>
      {isLoading ? <LoadingState text={loadingText} /> : null}
      {!isLoading && isError ? <ErrorState text={errorText} /> : null}
      {!isLoading && !isError ? children : null}
    </SectionCard>
  );
}
