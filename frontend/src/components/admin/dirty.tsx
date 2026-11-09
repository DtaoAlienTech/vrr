"use client";

import { createContext, useContext, useEffect, useRef, type MutableRefObject, type ReactNode } from "react";

const Context = createContext<MutableRefObject<boolean> | null>(null);

export const LEAVE_MESSAGE = "You have unsaved changes. If you leave now they will be lost. Leave this page?";

/** Warns before leaving a page with unsaved changes: closing the tab, reloading, or following a link. */
export function DirtyGuard({ children }: { children: ReactNode }) {
  const dirty = useRef(false);

  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (!dirty.current) return;
      event.preventDefault();
      event.returnValue = "";
    };
    const onClick = (event: MouseEvent) => {
      if (!dirty.current || event.defaultPrevented || event.button !== 0) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const link = (event.target as Element | null)?.closest?.("a");
      const href = link?.getAttribute("href");
      if (!link || !href || href.startsWith("#") || link.target === "_blank" || link.hasAttribute("download")) return;
      if (!window.confirm(LEAVE_MESSAGE)) {
        event.preventDefault();
        event.stopPropagation();
      } else {
        dirty.current = false;
      }
    };
    window.addEventListener("beforeunload", beforeUnload);
    document.addEventListener("click", onClick, true); // before the router's own handler
    return () => {
      window.removeEventListener("beforeunload", beforeUnload);
      document.removeEventListener("click", onClick, true);
    };
  }, []);

  return <Context.Provider value={dirty}>{children}</Context.Provider>;
}

/** Tell the guard whether the current screen has unsaved changes. */
export function useDirty(isDirty: boolean): void {
  const ref = useContext(Context);
  useEffect(() => {
    if (!ref) return;
    ref.current = isDirty;
    return () => {
      ref.current = false;
    };
  }, [ref, isDirty]);
}
