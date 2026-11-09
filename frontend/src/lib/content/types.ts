// The website's content types. Most of them come straight from the backend's API schema
// (./api.generated.ts, written by ./scripts/generate-types.sh), so they cannot drift from the API.
// Only what the API sends as free-form data is described here: the rich-text document, the page
// sections (20 block types) and the page keys. A check at the bottom proves the sections still fit
// the API's section shape, and backend/tests/test_blocks.py checks the block list.
import type * as Api from "./api.generated";

export type MediaVariant = Api.MediaVariantOut;
export type MediaRef = Api.MediaOut;
export type LinkItem = Api.Link;
export type DocItem = Api.DocItem;

// ---- Rich text: restricted editor JSON, drawn by React (never inserted as HTML) ----
export type RichMark = { type: string; attrs?: { href?: string } };
export type RichNode = {
  type: string;
  text?: string;
  attrs?: { level?: number };
  marks?: RichMark[];
  content?: RichNode[];
};
export type RichDoc = { type: "doc"; content: RichNode[] };

export type SiteSettings = Api.SettingsOut;

// ---- Page sections (reusable blocks) ----

type Tone = "default" | "alt";
type Block<T extends string, D> = { id: number; isVisible?: boolean; type: T; data: D };

export type HeroData = {
  label?: string;
  headline: string;
  highlight?: string;
  text: string;
  primaryCta: LinkItem;
  secondaryCta?: LinkItem;
  image: MediaRef;
};
export type StatsData = { items: { value: string; label: string }[] };
export type NoticeStripData = { label: string; items: string[] };
export type PageHeaderData = { title: string; subtitle?: string; crumbs?: LinkItem[] };
export type CardGridData = {
  variant: "numbered" | "tiles" | "steps";
  tone?: Tone;
  heading: string;
  intro?: string;
  cards: { title: string; text?: string }[];
};
export type CollectionName = "courses" | "activities" | "news" | "faculty" | "gallery";
export type CollectionListData = {
  collection: CollectionName;
  layout?: "cards" | "detailed" | "albums" | "list" | "grid" | "mosaic";
  tone?: Tone;
  heading?: string;
  intro?: string;
  limit?: number;
  cta?: LinkItem;
};
export type DocListData = { tone?: Tone; heading?: string; intro?: string; docs: DocItem[] };
export type QuoteData = {
  heading: string;
  text: string;
  name: string;
  role: string;
  image?: MediaRef;
};
export type MediaGalleryData = {
  heading: string;
  intro?: string;
  cta?: LinkItem;
  items: { media: MediaRef; caption: string }[];
};
export type EnquiryCtaData = { heading: string; text: string };

// Blocks that can sit inside the two-column layout.
export type RichTextData = { tone?: Tone; heading?: string; body: RichDoc };
export type TimelineData = { items: { label: string; text: string }[] };
export type KeyValueData = { rows: { label: string; value: string }[] };
export type FaqData = { items: { question: string; answer: string }[] };
export type PanelData = {
  title?: string;
  items?: { heading: string; text: string }[];
  list?: string[];
};
export type ImageData = { media: MediaRef };
export type EnquiryFormData = { title: string };
export type ContactInfoData = { heading?: string };
export type MapData = { title?: string };

export type EmbeddedSection =
  | Block<"rich_text", RichTextData>
  | Block<"timeline", TimelineData>
  | Block<"key_value", KeyValueData>
  | Block<"faq", FaqData>
  | Block<"panel", PanelData>
  | Block<"image", ImageData>
  | Block<"enquiry_form", EnquiryFormData>
  | Block<"contact_info", ContactInfoData>
  | Block<"map", MapData>
  | Block<"doc_list", DocListData>
  | Block<"collection_list", CollectionListData>;

export type TwoColumnData = {
  tone?: Tone;
  heading?: string;
  intro?: string;
  main: EmbeddedSection[];
  aside: EmbeddedSection[];
};

export type Section =
  | Block<"hero", HeroData>
  | Block<"stats", StatsData>
  | Block<"notice_strip", NoticeStripData>
  | Block<"page_header", PageHeaderData>
  | Block<"card_grid", CardGridData>
  | Block<"collection_list", CollectionListData>
  | Block<"doc_list", DocListData>
  | Block<"rich_text", RichTextData>
  | Block<"quote", QuoteData>
  | Block<"media_gallery", MediaGalleryData>
  | Block<"enquiry_cta", EnquiryCtaData>
  | Block<"two_column", TwoColumnData>;

export type SectionType = Section["type"];
export type PageKey =
  | "home"
  | "about"
  | "courses"
  | "faculty"
  | "admissions"
  | "activities"
  | "gallery"
  | "news"
  | "contact"
  | "privacy";

export type PageSeo = Api.PageSeoOut;
/** `slug` is the URL path without the leading slash ("" for the home page). */
export type PageData = Omit<Api.PageOut, "key" | "sections"> & {
  key: PageKey;
  sections: Section[];
};

// ---- Structured collections ----

export type Course = Omit<Api.CourseOut, "description"> & { description?: RichDoc };
export type ActivityPhoto = Api.ActivityPhotoOut;
export type Activity = Api.ActivityOut;
/** `publishedAt` is an ISO date, YYYY-MM-DD. */
export type NewsItem = Omit<Api.NewsOut, "body"> & { body: RichDoc };
export type FacultyMember = Api.FacultyOut;
export type GalleryItem = Api.GalleryOut;

/** What the draft preview address returns: one page or one news item, whatever its status. */
export type PreviewData = { kind: "page"; page: PageData } | { kind: "news"; news: NewsItem };

// ---- Compile-time guard: a mistake here fails `npm run typecheck` ----

type Assert<T extends true> = T;
/** Every section the website knows must still be a valid answer of the API's section shape. */
export type SectionsFitTheApi = Assert<Section extends Api.SectionOut ? true : false>;
/** A preview is one of the two answers the API can give. */
export type PreviewFitsTheApi = Assert<PreviewData extends Api.PreviewOut ? true : false>;
