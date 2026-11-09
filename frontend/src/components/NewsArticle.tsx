import { PageHeaderBlock } from "@/components/blocks/PageHeaderBlock";
import { DocList } from "@/components/ui/DocList";
import { LinkButton } from "@/components/ui/LinkButton";
import { RichText } from "@/components/ui/RichText";
import { Section } from "@/components/ui/Section";
import type { NewsItem } from "@/lib/content/types";
import { dateParts } from "@/lib/format";

/** One news item. Shared by the public address (/news/slug) and the draft preview, so a preview
 * always looks exactly like the published result. */
export function NewsArticle({ item }: { item: NewsItem }) {
  const files = item.attachments.filter((file) => file.href);
  return (
    <>
      <PageHeaderBlock
        data={{
          title: item.title,
          subtitle: `${item.category} · ${dateParts(item.publishedAt).long}`,
          crumbs: [{ label: "News", href: "/news" }],
        }}
      />
      <Section>
        <article className="stack">
          <RichText doc={item.body} />
          {files.length > 0 && (
            <div>
              <h2>Attachments</h2>
              <DocList docs={files} />
            </div>
          )}
          <p>
            <LinkButton href="/news" variant="ghost">
              All news and notices
            </LinkButton>
          </p>
        </article>
      </Section>
    </>
  );
}
