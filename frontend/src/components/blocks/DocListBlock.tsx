import { DocList } from "@/components/ui/DocList";
import { Section, SectionHead } from "@/components/ui/Section";
import type { DocListData } from "@/lib/content/types";

export function DocListBlock({ data }: { data: DocListData }) {
  return (
    <Section tone={data.tone}>
      {data.heading && <SectionHead title={data.heading} intro={data.intro} />}
      <DocList docs={data.docs} />
    </Section>
  );
}
