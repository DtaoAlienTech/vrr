import type { ReactNode } from "react";
import { cx } from "@/lib/cx";
import { SmartLink } from "./SmartLink";

type Props = {
  href: string;
  variant?: "primary" | "ghost" | "light" | "accent";
  size?: "sm";
  className?: string;
  children: ReactNode;
};

export function LinkButton({ href, variant = "primary", size, className, children }: Props) {
  return (
    <SmartLink href={href} className={cx("btn", `btn-${variant}`, size === "sm" && "btn-sm", className)}>
      {children}
    </SmartLink>
  );
}
