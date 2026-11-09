import { jsonLdString } from "@/lib/json-ld";

/**
 * The only place structured data is written into the page (escaping is in lib/json-ld.ts and
 * covered by tests). RichText is the only other place that may render raw HTML; the lint rule
 * react/no-danger forbids it everywhere else.
 */
export function JsonLd({ data }: { data: Record<string, unknown> }) {
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdString(data) }} />;
}
