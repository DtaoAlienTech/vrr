"use client";

import { createContext, useContext, useState, type ReactNode } from "react";
import { Icon } from "@/components/ui/Icon";

type NavState = { open: boolean; toggle: () => void; close: () => void };
const NavContext = createContext<NavState | null>(null);

function useNav(): NavState {
  const ctx = useContext(NavContext);
  if (!ctx) throw new Error("Mobile nav components must be inside MobileNavProvider");
  return ctx;
}

export function MobileNavProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const value: NavState = { open, toggle: () => setOpen((o) => !o), close: () => setOpen(false) };
  return <NavContext.Provider value={value}>{children}</NavContext.Provider>;
}

export function MobileNavButton() {
  const { open, toggle } = useNav();
  return (
    <button
      type="button"
      className="menu-btn"
      aria-label={open ? "Close menu" : "Open menu"}
      aria-expanded={open}
      aria-controls="mobile-nav"
      onClick={toggle}
    >
      <Icon name="menu" />
    </button>
  );
}

/** The dropdown menu for phones. Closes when a link inside it is tapped. */
export function MobileNavPanel({ children }: { children: ReactNode }) {
  const { open, close } = useNav();
  return (
    <nav
      id="mobile-nav"
      className="mnav"
      aria-label="Mobile"
      hidden={!open}
      onClick={(event) => {
        if ((event.target as HTMLElement).closest("a")) close();
      }}
    >
      {children}
    </nav>
  );
}
