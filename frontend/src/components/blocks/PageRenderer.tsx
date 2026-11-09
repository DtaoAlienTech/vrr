import type { Section } from "@/lib/content/types";
import { CardGridBlock } from "./CardGridBlock";
import { CollectionListBlock } from "./CollectionListBlock";
import { DocListBlock } from "./DocListBlock";
import { EnquiryCtaBlock } from "./EnquiryCtaBlock";
import { HeroBlock } from "./HeroBlock";
import { MediaGalleryBlock } from "./MediaGalleryBlock";
import { NoticeStripBlock } from "./NoticeStripBlock";
import { PageHeaderBlock } from "./PageHeaderBlock";
import { QuoteBlock } from "./QuoteBlock";
import { RichTextBlock } from "./RichTextBlock";
import { StatsBlock } from "./StatsBlock";
import { TwoColumnBlock } from "./TwoColumnBlock";

/** Maps a section's `type` to its component. TypeScript fails the build if a type is missing. */
function renderSection(section: Section) {
  switch (section.type) {
    case "hero":
      return <HeroBlock data={section.data} />;
    case "stats":
      return <StatsBlock data={section.data} />;
    case "notice_strip":
      return <NoticeStripBlock data={section.data} />;
    case "page_header":
      return <PageHeaderBlock data={section.data} />;
    case "card_grid":
      return <CardGridBlock data={section.data} />;
    case "collection_list":
      return <CollectionListBlock data={section.data} />;
    case "doc_list":
      return <DocListBlock data={section.data} />;
    case "rich_text":
      return <RichTextBlock data={section.data} />;
    case "quote":
      return <QuoteBlock data={section.data} />;
    case "media_gallery":
      return <MediaGalleryBlock data={section.data} />;
    case "enquiry_cta":
      return <EnquiryCtaBlock data={section.data} />;
    case "two_column":
      return <TwoColumnBlock data={section.data} />;
    default: {
      const unhandled: never = section;
      throw new Error(`Unknown section type: ${JSON.stringify(unhandled)}`);
    }
  }
}

/** Renders a page from its list of sections. A new page needs data, not code. */
export function PageRenderer({ sections }: { sections: Section[] }) {
  return (
    <>
      {sections
        .filter((section) => section.isVisible !== false)
        .map((section) => (
          <div key={section.id} data-section={section.type}>
            {renderSection(section)}
          </div>
        ))}
    </>
  );
}
