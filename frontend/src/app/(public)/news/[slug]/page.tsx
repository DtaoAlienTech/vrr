import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { NewsArticle } from "@/components/NewsArticle";
import { JsonLd } from "@/components/ui/JsonLd";
import { getNews, getNewsItem, getSiteSettings } from "@/lib/content/api";
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

  return (
    <>
      <JsonLd data={newsJsonLd(item, settings)} />
      <NewsArticle item={item} />
    </>
  );
}
