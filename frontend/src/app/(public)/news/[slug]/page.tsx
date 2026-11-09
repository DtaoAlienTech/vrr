import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PageHeaderBlock } from "@/components/blocks/PageHeaderBlock";
import { DocList } from "@/components/ui/DocList";
import { JsonLd } from "@/components/ui/JsonLd";
import { LinkButton } from "@/components/ui/LinkButton";
import { RichText } from "@/components/ui/RichText";
import { Section } from "@/components/ui/Section";
import { getNews, getNewsItem, getSiteSettings } from "@/lib/content/api";
import { dateParts } from "@/lib/format";
import { buildPageMetadata, newsJsonLd } from "@/lib/seo";

export async function generateStaticParams() {
  const items = await getNews();
  return items.map((item) => ({ slug: item.slug }));
}

export async function generateMetadata(props: PageProps<"/news/[slug]">): Promise<Metadata> {
  const { slug } = await props.params;
  const [item, settings] = await Promise.all([getNewsItem(slug), getSiteSettings()]);
  if (!item) return {};
  return buildPageMetadata(settings, {
    title: item.title,
    description: item.summary,
    path: `/news/${slug}`,
    image: item.cover ?? settings.seo.ogImage,
    type: "article",
  });
}

export default async function NewsPage(props: PageProps<"/news/[slug]">) {
  const { slug } = await props.params;
  const [item, settings] = await Promise.all([getNewsItem(slug), getSiteSettings()]);
  if (!item) notFound();
  const files = item.attachments.filter((file) => file.href);

  return (
    <>
      <JsonLd data={newsJsonLd(item, settings)} />
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
