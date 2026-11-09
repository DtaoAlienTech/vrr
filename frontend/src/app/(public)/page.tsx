import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PageRenderer } from "@/components/blocks/PageRenderer";
import { JsonLd } from "@/components/ui/JsonLd";
import { getPage, getSiteSettings } from "@/lib/content/api";
import { buildMetadata, collegeJsonLd } from "@/lib/seo";

export async function generateMetadata(): Promise<Metadata> {
  const [page, settings] = await Promise.all([getPage("home"), getSiteSettings()]);
  return page ? buildMetadata(page, settings, "/") : {};
}

export default async function HomePage() {
  const [page, settings] = await Promise.all([getPage("home"), getSiteSettings()]);
  if (!page) notFound();
  return (
    <>
      <JsonLd data={collegeJsonLd(settings)} />
      <PageRenderer sections={page.sections} />
    </>
  );
}
