import type { ReactNode } from "react";
import { cx } from "@/lib/cx";

type Tone = "default" | "alt" | "band";

/** Page section wrapper: background tone, centred content width, optional anchor id. */
export function Section({
  tone = "default",
  id,
  children,
}: {
  tone?: Tone;
  id?: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className={cx("sec", tone === "alt" && "alt", tone === "band" && "band")}>
      <div className="wrap">{children}</div>
    </section>
  );
}

/** Section heading with optional intro text and the accent rule. */
export function SectionHead({ title, intro }: { title: string; intro?: string }) {
  return (
    <div className="sec-head">
      <h2>{title}</h2>
      {intro && <p className="lead">{intro}</p>}
      <div className="rule" />
    </div>
  );
}
