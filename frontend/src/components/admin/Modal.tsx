"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { cx } from "@/lib/cx";

type Props = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
};

/** A dialog on the browser's own <dialog>: focus stays inside, Escape closes, the page behind is inert. */
export function Modal({ open, onClose, title, children, footer, wide }: Props) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className={cx("amodal", wide && "amodal-wide")}
      aria-label={title}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === ref.current) onClose(); // a click on the dark area
      }}
    >
      {open && (
        <div className="amodal-box">
          <div className="amodal-head">
            <h2>{title}</h2>
            <button type="button" className="aclose" onClick={onClose} aria-label="Close">
              ×
            </button>
          </div>
          <div className="amodal-body">{children}</div>
          {footer && <div className="amodal-foot">{footer}</div>}
        </div>
      )}
    </dialog>
  );
}
