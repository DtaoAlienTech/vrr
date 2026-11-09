import type { RichDoc } from "@/lib/content/types";
import { renderRichText } from "@/lib/rich-text";

/** Draws editor content. It is built from React elements, never from HTML (see lib/rich-text.ts). */
export function RichText({ doc }: { doc: RichDoc }) {
  return <div className="prose">{renderRichText(doc)}</div>;
}
