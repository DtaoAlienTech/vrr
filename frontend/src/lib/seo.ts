import type { Metadata } from "next";
import { absoluteUrl, SITE_URL } from "./env";
import type { Course, MediaRef, NewsItem, PageData, SiteSettings } from "./content/types";

type MetaInput = {
  title: string;
  description: string;
  path: string;
  image: MediaRef;
  noindex?: boolean;
  /** Use the title exactly as written (home page) instead of the "%s | College" template. */
  absoluteTitle?: boolean;
  type?: "website" | "article";
};

/** Title, description, canonical address and share cards for any page. */
export function buildPageMetadata(settings: SiteSettings, input: MetaInput): Metadata {
  const { title, description, path, image, noindex, absoluteTitle, type = "website" } = input;
  return {
    title: absoluteTitle ? { absolute: title } : title,
    description,
    alternates: { canonical: path },
    openGraph: {
      type,
      siteName: settings.name,
      locale: "en_IN",
      title,
      description,
      url: path,
      images: [{ url: image.url, width: image.width, height: image.height, alt: image.alt }],
    },
    twitter: { card: "summary_large_image", title, description, images: [image.url] },
    robots: noindex ? { index: false, follow: false } : undefined,
  };
}

/** Metadata for a page made of sections, from the SEO fields the admin edits. */
export function buildMetadata(page: PageData, settings: SiteSettings, path: string): Metadata {
  return buildPageMetadata(settings, {
    title: page.seo.title,
    description: page.seo.description,
    path,
    image: page.seo.ogImage ?? settings.seo.ogImage,
    noindex: page.seo.noindex,
    absoluteTitle: path === "/",
  });
}

function provider(settings: SiteSettings) {
  return { "@type": "CollegeOrUniversity", name: settings.name, url: SITE_URL };
}

/** schema.org structured data for the college, generated from the site settings. */
export function collegeJsonLd(settings: SiteSettings): Record<string, unknown> {
  const { contact } = settings;
  return {
    "@context": "https://schema.org",
    ...provider(settings),
    alternateName: settings.shortName,
    logo: absoluteUrl(settings.logo.url),
    image: absoluteUrl(settings.seo.ogImage.url),
    foundingDate: String(settings.established),
    description: settings.seo.description,
    address: { "@type": "PostalAddress", streetAddress: contact.address, addressCountry: "IN" },
    ...(contact.phone && { telephone: contact.phone }),
    ...(contact.email && { email: contact.email }),
    ...(settings.social.length > 0 && { sameAs: settings.social.map((s) => s.href) }),
  };
}

export function courseJsonLd(course: Course, settings: SiteSettings): Record<string, unknown> {
  return {
    "@context": "https://schema.org",
    "@type": "Course",
    name: course.name,
    description: course.summary,
    url: absoluteUrl(`/courses/${course.slug}`),
    provider: provider(settings),
  };
}

export function newsJsonLd(item: NewsItem, settings: SiteSettings): Record<string, unknown> {
  return {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    headline: item.title,
    description: item.summary,
    datePublished: item.publishedAt,
    url: absoluteUrl(`/news/${item.slug}`),
    ...(item.cover && { image: absoluteUrl(item.cover.url) }),
    publisher: provider(settings),
  };
}
