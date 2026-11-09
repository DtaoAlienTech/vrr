"use client";

import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { Modal } from "./Modal";

type Toast = { id: number; kind: "ok" | "error"; text: string };
type ConfirmOptions = { title: string; message: ReactNode; confirmLabel?: string; danger?: boolean };

type Feedback = {
  ok: (text: string) => void;
  error: (text: string) => void;
  confirm: (options: ConfirmOptions) => Promise<boolean>;
};

const Context = createContext<Feedback | null>(null);

export function FeedbackProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [asking, setAsking] = useState<(ConfirmOptions & { resolve: (answer: boolean) => void }) | null>(null);
  const nextId = useRef(1);

  const add = useCallback((kind: Toast["kind"], text: string) => {
    const id = nextId.current++;
    setToasts((all) => [...all.slice(-3), { id, kind, text }]);
    window.setTimeout(() => setToasts((all) => all.filter((t) => t.id !== id)), kind === "error" ? 9000 : 4500);
  }, []);

  const value = useMemo<Feedback>(
    () => ({
      ok: (text) => add("ok", text),
      error: (text) => add("error", text),
      confirm: (options) => new Promise<boolean>((resolve) => setAsking({ ...options, resolve })),
    }),
    [add],
  );

  const answer = (result: boolean) => {
    asking?.resolve(result);
    setAsking(null);
  };

  return (
    <Context.Provider value={value}>
      {children}
      <div className="atoasts" role="status" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className={`atoast atoast-${toast.kind}`}>
            {toast.text}
          </div>
        ))}
      </div>
      <Modal
        open={asking !== null}
        onClose={() => answer(false)}
        title={asking?.title ?? ""}
        footer={
          <>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => answer(false)}>
              Cancel
            </button>
            <button type="button" className={asking?.danger ? "btn btn-danger btn-sm" : "btn btn-primary btn-sm"} onClick={() => answer(true)}>
              {asking?.confirmLabel ?? "OK"}
            </button>
          </>
        }
      >
        <div>{asking?.message}</div>
      </Modal>
    </Context.Provider>
  );
}

export function useFeedback(): Feedback {
  const value = useContext(Context);
  if (!value) throw new Error("useFeedback needs a FeedbackProvider");
  return value;
}
