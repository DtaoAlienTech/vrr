import { Media } from "@/components/ui/Media";
import { Section, SectionHead } from "@/components/ui/Section";
import type { QuoteData } from "@/lib/content/types";
import { cx } from "@/lib/cx";

/** Principal / chairman message. Shows the portrait only when a photo has been added. */
export function QuoteBlock({ data }: { data: QuoteData }) {
  return (
    <Section>
      <SectionHead title={data.heading} />
      <div className={cx("msg", !data.image && "solo")}>
        {data.image && (
          <div className="arch sm">
            <Media media={data.image} sizes="300px" />
          </div>
        )}
        <div>
          <div className="quote">{data.text}</div>
          <div className="sign">
            {data.name}
            <small>{data.role}</small>
          </div>
        </div>
      </div>
    </Section>
  );
}
