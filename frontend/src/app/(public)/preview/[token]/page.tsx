import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { PageRenderer } from "@/components/blocks/PageRenderer";
import { NewsArticle } from "@/components/NewsArticle";
import { PreviewBanner } from "@/components/PreviewBanner";
import { getPreview } from "@/lib/content/api";

// Draft preview: opened with a signed link made in the admin panel. It is read fresh on every
// visit (never cached) and kept out of search engines. Layout, sections and styles are the same as
// the real pages, so what the editor sees here is what visitors will see.

export const metadata: Metadata = {
  title: "Draft preview",
  robots: { index: false, follow: false, nocache: true },
};

export default function PreviewPage(props: PageProps<"/preview/[token]">) {
  // The address is only known per visit, so it is read inside Suspense (the rest of the page
  // frame stays part of the fast pre-built shell).
  return (
    <Suspense fallback={null}>
      <PreviewBody params={props.params} />
    </Suspense>
  );
}

async function PreviewBody({ params }: { params: PageProps<"/preview/[token]">["params"] }) {
  const { token } = await params;
  const preview = await getPreview(token);
  if (!preview) notFound();

  if (preview.kind === "news") {
    return (
      <>
        <PreviewBanner what="news item" />
        <NewsArticle item={preview.news} />
      </>
    );
  }
  return (
    <>
      <PreviewBanner what="page" />
      <PageRenderer sections={preview.page.sections} />
    </>
  );
}
