// GENERATED from the backend API schema. Do not edit by hand.
// Update with: ./scripts/generate-types.sh   (it is checked by ./scripts/check.sh)
//
// A field that may be empty is optional here and never null: the public API leaves out empty
// values instead of sending null (response_model_exclude_none), so `cover?: MediaOut` is accurate.

export type ActivityOut = {
  slug: string;
  group: string;
  groupKey: string;
  year?: string;
  title: string;
  summary: string;
  cover: MediaOut;
  photos: ActivityPhotoOut[];
};

export type ActivityPhotoOut = {
  media: MediaOut;
  caption?: string;
};

export type ContactOut = {
  address: string;
  phone: string;
  whatsapp: string;
  email: string;
  hours: string;
  mapLink: string;
  mapEmbedUrl: string;
};

export type CourseOut = {
  slug: string;
  tab: string;
  name: string;
  department: string;
  duration: string;
  affiliation?: string;
  summary: string;
  description?: Record<string, unknown>;
  subjects?: string[];
  eligibility?: string;
  seats?: string;
  fees?: string;
  syllabus?: DocItem;
};

export type DocItem = {
  title: string;
  note?: string;
  href?: string;
};

export type FacultyOut = {
  id: number;
  name: string;
  designation: string;
  qualification: string;
  department: string;
  departmentKey: string;
  photo?: MediaOut;
};

export type GalleryOut = {
  id: number;
  media: MediaOut;
  caption: string;
  category: string;
  categoryLabel: string;
};

export type Link = {
  label: string;
  href: string;
};

export type MediaOut = {
  url: string;
  alt: string;
  width: number;
  height: number;
  variants?: MediaVariantOut[];
  cropBottom?: boolean;
};

export type MediaVariantOut = {
  url: string;
  width: number;
};

export type NewsOut = {
  slug: string;
  title: string;
  category: string;
  publishedAt: string;
  summary: string;
  body: Record<string, unknown>;
  pinned?: boolean;
  attachments: DocItem[];
  cover?: MediaOut;
};

export type PageOut = {
  key: string;
  slug: string;
  title: string;
  seo: PageSeoOut;
  sections: SectionOut[];
};

export type PageSeoOut = {
  title: string;
  description: string;
  ogImage?: MediaOut;
  noindex?: boolean;
};

export type PageSummaryOut = {
  key: string;
  slug: string;
  title: string;
  noindex?: boolean;
};

export type PreviewOut = {
  kind: "page" | "news";
  page?: PageOut;
  news?: NewsOut;
};

export type RedirectPublicOut = {
  fromPath: string;
  toPath: string;
  statusCode: number;
};

export type SectionOut = {
  id: number;
  type: string;
  data: Record<string, unknown>;
};

export type SeoSettingsOut = {
  defaultTitle: string;
  titleTemplate: string;
  description: string;
  ogImage: MediaOut;
};

export type SettingsOut = {
  name: string;
  shortName: string;
  tagline: string;
  established: number;
  topBar: string;
  logo: MediaOut;
  contact: ContactOut;
  social: Link[];
  menu: Link[];
  footerCourses: Link[];
  affiliationText: string;
  copyright: string;
  seo: SeoSettingsOut;
};
