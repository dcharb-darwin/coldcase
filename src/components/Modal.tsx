import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

type ModalProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  size?: "sm" | "md" | "lg";
};

export default function Modal({ open, onClose, title, children, size = "md" }: ModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, onClose]);

  if (!open) return null;

  const sizeClass = size === "sm" ? "modal-sm" : size === "lg" ? "modal-lg" : "modal-md";

  return createPortal(
    <div
      ref={overlayRef}
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      onMouseDown={(e) => {
        if (e.target === overlayRef.current) onClose();
      }}
    >
      <div className={`modal-content ${sizeClass}`} onMouseDown={(e) => e.stopPropagation()}>
        <div
          style={{
            padding: "var(--space-lg)",
            borderBottom: "1px solid var(--color-border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "var(--space-md)",
          }}
        >
          <h2 id="modal-title" style={{ margin: 0, fontSize: "1.125rem", fontWeight: 600, color: "var(--color-text)" }}>
            {title}
          </h2>
          <button type="button" className="btn btn-ghost" onClick={onClose} aria-label="Close dialog">
            Close
          </button>
        </div>
        <div style={{ padding: "var(--space-lg)" }}>{children}</div>
      </div>
    </div>,
    document.body,
  );
}
