"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

type Option = { value: string; label: string };

/**
 * Filter buttons for any list. The items stay in the server-rendered page (so search engines see
 * everything); each item carries data-cat="<value>" and this component only hides the others.
 */
export function FilterGroup({
  options,
  label,
  children,
}: {
  options: Option[];
  label: string;
  children: ReactNode;
}) {
  const [active, setActive] = useState("all");
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    container.current?.querySelectorAll<HTMLElement>("[data-cat]").forEach((item) => {
      item.hidden = active !== "all" && item.dataset.cat !== active;
    });
  }, [active]);

  return (
    <>
      <div className="chips" role="group" aria-label={label}>
        {[{ value: "all", label: "All" }, ...options].map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={active === option.value}
            onClick={() => setActive(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
      <div ref={container}>{children}</div>
    </>
  );
}
