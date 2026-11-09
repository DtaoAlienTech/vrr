import Link from "next/link";
import type { ComponentProps } from "react";
import { safeHref } from "@/lib/safe-href";

type Props = Omit<ComponentProps<"a">, "href"> & { href: string };

/** The one link component: internal links use next/link, external links get safe rel/target. */
export function SmartLink({ href, children, ...rest }: Props) {
  const safe = safeHref(href);
  if (safe.startsWith("/") || safe.startsWith("#")) {
    return (
      <Link href={safe} {...rest}>
        {children}
      </Link>
    );
  }
  const external = /^https?:/i.test(safe);
  return (
    <a href={safe} {...rest} {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}>
      {children}
    </a>
  );
}
