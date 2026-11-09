"use client";

import { usePathname } from "next/navigation";
import type { LinkItem } from "@/lib/content/types";
import { NavLinks } from "./NavLinks";

/** Same links, with the current page marked (aria-current). Needs the browser URL. */
export function ActiveNavLinks({ items }: { items: LinkItem[] }) {
  return <NavLinks items={items} currentPath={usePathname()} />;
}
