import type { LinkItem } from "@/lib/content/types";
import { cx } from "@/lib/cx";
import { SmartLink } from "@/components/ui/SmartLink";

/** Presentational link list. Used on the server (no active state) and by ActiveNavLinks. */
export function NavLinks({ items, currentPath }: { items: LinkItem[]; currentPath?: string }) {
  return (
    <>
      {items.map((item) => {
        const active =
          currentPath !== undefined &&
          (item.href === "/" ? currentPath === "/" : currentPath.startsWith(item.href));
        return (
          <SmartLink
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={cx(active && "is-active")}
          >
            {item.label}
          </SmartLink>
        );
      })}
    </>
  );
}
