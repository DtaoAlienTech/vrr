import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PageRenderer } from "@/components/blocks/PageRenderer";
import { getPageBySlug, getPageSlugs, getSiteSettings } from "@/lib/content/api";
import { buildMetadata } from "@/lib/seo";

// One route for every standard page (about, courses, faculty, admissions, activities, gallery,
// news, contact, privacy). The page is looked up by its slug, so a new page needs data, not code.

export async function generateStaticParams() {
  const slugs = await getPageSlugs();
  return slugs.map((slug) => ({ slug }));
}

export async function generateMetadata(props: PageProps<"/[slug]">): Promise<Metadata> {
  const { slug } = await props.params;
  const [page, settings] = await Promise.all([getPageBySlug(slug), getSiteSettings()]);
  return page ? buildMetadata(page, settings, `/${slug}`) : {};
}

export default async function StandardPage(props: PageProps<"/[slug]">) {
  const { slug } = await props.params;
  const page = await getPageBySlug(slug);
  if (!page) notFound();
  return <PageRenderer sections={page.sections} />;
}
