import { Fragment } from "react";
import { Section, SectionHead } from "@/components/ui/Section";
import type { EmbeddedSection, TwoColumnData } from "@/lib/content/types";
import { cx } from "@/lib/cx";
import { renderEmbedded } from "./EmbeddedBlocks";

const isVisible = (section: EmbeddedSection) => section.isVisible !== false;

/** Main column plus a narrower side column. Used by About, Admissions, News and Contact. */
export function TwoColumnBlock({ data }: { data: TwoColumnData }) {
  const aside = data.aside.filter(isVisible);
  return (
    <Section tone={data.tone}>
      {data.heading && <SectionHead title={data.heading} intro={data.intro} />}
      <div className={cx("split", aside.length === 0 && "solo")}>
        <div className="stack">
          {data.main.filter(isVisible).map((section) => (
            <Fragment key={section.id}>{renderEmbedded(section)}</Fragment>
          ))}
        </div>
        {aside.length > 0 && (
          <aside className="stack">
            {aside.map((section) => (
              <Fragment key={section.id}>{renderEmbedded(section)}</Fragment>
            ))}
          </aside>
        )}
      </div>
    </Section>
  );
}
