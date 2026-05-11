type PaginationControlsProps = {
  page: number;
  totalPages: number;
  isBusy?: boolean;
  onPrevious: () => void;
  onNext: () => void;
};

export default function PaginationControls({
  page,
  totalPages,
  isBusy = false,
  onPrevious,
  onNext,
}: PaginationControlsProps) {
  return (
    <div style={{ marginTop: "var(--space-md)", display: "flex", justifyContent: "space-between" }}>
      <span className="text-secondary">
        Page {page} of {totalPages}
      </span>
      <div style={{ display: "flex", gap: "var(--space-xs)" }}>
        <button className="btn btn-ghost" disabled={page <= 1 || isBusy} onClick={onPrevious}>
          Previous
        </button>
        <button className="btn btn-ghost" disabled={page >= totalPages || isBusy} onClick={onNext}>
          Next
        </button>
      </div>
    </div>
  );
}
