import { RichText } from "@/components/ui/RichText";
import { Section, SectionHead } from "@/components/ui/Section";
import type { RichTextData } from "@/lib/content/types";

/** A full-width text section (for example the privacy policy). */
export function RichTextBlock({ data }: { data: RichTextData }) {
  return (
    <Section tone={data.tone}>
      {data.heading && <SectionHead title={data.heading} />}
      <RichText doc={data.body} />
    </Section>
  );
}
