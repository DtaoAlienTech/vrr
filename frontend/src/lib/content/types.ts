// Shapes of the content that the admin edits. In Phase 1 the backend defines the same shapes
// once (Pydantic) and these types are generated from its OpenAPI schema.

export type MediaVariant = { url: string; width: number };
export type MediaRef = {
  url: string;
  alt: string;
  width: number;
  height: number;
  variants?: MediaVariant[];
  /** Hide a camera date stamp burned into the bottom edge of the photo. */
  cropBottom?: boolean;
};
export type LinkItem = { label: string; href: string };
export type DocItem = { title: string; note?: string; href?: string };

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

export type SiteSettings = {
  name: string;
  shortName: string;
  tagline: string;
  established: number;
  topBar: string;
  logo: MediaRef;
  contact: {
    address: string;
    phone: string;
    whatsapp: string;
    email: string;
    hours: string;
    mapLink: string;
    /** A Google Maps "embed" address (https://www.google.com/maps/embed?...). */
    mapEmbedUrl: string;
  };
  social: LinkItem[];
  menu: LinkItem[];
  footerCourses: LinkItem[];
  affiliationText: string;
  copyright: string;
  seo: {
    defaultTitle: string;
    titleTemplate: string;
    description: string;
    ogImage: MediaRef;
  };
};

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

export type PageSeo = {
  title: string;
  description: string;
  ogImage?: MediaRef;
  noindex?: boolean;
};
/** `slug` is the URL path without the leading slash ("" for the home page). */
export type PageData = {
  key: PageKey;
  slug: string;
  title: string;
  seo: PageSeo;
  sections: Section[];
};

// ---- Structured collections ----

export type Course = {
  slug: string;
  tab: string;
  name: string;
  department: string;
  duration: string;
  affiliation?: string;
  summary: string;
  description?: RichDoc;
  subjects?: string[];
  eligibility?: string;
  seats?: string;
  fees?: string;
  syllabus?: DocItem;
};
export type ActivityPhoto = { media: MediaRef; caption?: string };
export type Activity = {
  slug: string;
  group: string;
  groupKey: string;
  year?: string;
  title: string;
  summary: string;
  cover: MediaRef;
  photos: ActivityPhoto[];
};
export type NewsItem = {
  slug: string;
  title: string;
  category: string;
  /** ISO date, YYYY-MM-DD */
  publishedAt: string;
  summary: string;
  body: RichDoc;
  pinned?: boolean;
  attachments: DocItem[];
  cover?: MediaRef;
};
export type FacultyMember = {
  id: number;
  name: string;
  designation: string;
  qualification: string;
  department: string;
  departmentKey: string;
  photo?: MediaRef;
};
export type GalleryItem = {
  id: number;
  media: MediaRef;
  caption: string;
  category: string;
  categoryLabel: string;
};
