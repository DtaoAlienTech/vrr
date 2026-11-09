// The single data-access layer for the public site. Every function is cached and tagged, so the
// admin can refresh exactly what changed through /internal/revalidate (see that route).
// Today it reads fixtures; in Phase 1/2 only the bodies change (fetch from the FastAPI backend).
import { cacheLife, cacheTag } from "next/cache";
import { activities, courses, faculty, gallery, news, pages, settings } from "./fixtures";
import type {
  Activity,
  Course,
  FacultyMember,
  GalleryItem,
  NewsItem,
  PageData,
  PageKey,
  SiteSettings,
} from "./types";

export async function getSiteSettings(): Promise<SiteSettings> {
  "use cache";
  cacheTag("settings");
  cacheLife("hours");
  return settings;
}

export async function getPage(key: PageKey): Promise<PageData | null> {
  "use cache";
  cacheTag("pages", `page:${key}`);
  cacheLife("hours");
  return pages[key] ?? null;
}

/** Finds a page by its URL path (without the leading slash). The home page is not included. */
export async function getPageBySlug(slug: string): Promise<PageData | null> {
  "use cache";
  cacheTag("pages", `page-slug:${slug}`);
  cacheLife("hours");
  return Object.values(pages).find((page) => page.slug !== "" && page.slug === slug) ?? null;
}

export async function getPageSlugs(): Promise<string[]> {
  "use cache";
  cacheTag("pages");
  cacheLife("hours");
  return Object.values(pages)
    .map((page) => page.slug)
    .filter((slug) => slug !== "");
}

export async function getCourses(limit?: number): Promise<Course[]> {
  "use cache";
  cacheTag("courses");
  cacheLife("hours");
  return courses.slice(0, limit);
}

export async function getCourse(slug: string): Promise<Course | null> {
  "use cache";
  cacheTag("courses", `course:${slug}`);
  cacheLife("hours");
  return courses.find((course) => course.slug === slug) ?? null;
}

export async function getActivities(limit?: number): Promise<Activity[]> {
  "use cache";
  cacheTag("activities");
  cacheLife("hours");
  return activities.slice(0, limit);
}

/** Pinned items first, then newest first. */
export async function getNews(limit?: number): Promise<NewsItem[]> {
  "use cache";
  cacheTag("news");
  cacheLife("hours");
  const sorted = [...news].sort(
    (a, b) => Number(b.pinned ?? false) - Number(a.pinned ?? false) || b.publishedAt.localeCompare(a.publishedAt),
  );
  return sorted.slice(0, limit);
}

export async function getNewsItem(slug: string): Promise<NewsItem | null> {
  "use cache";
  cacheTag("news", `news:${slug}`);
  cacheLife("hours");
  return news.find((item) => item.slug === slug) ?? null;
}

export async function getFaculty(): Promise<FacultyMember[]> {
  "use cache";
  cacheTag("faculty");
  cacheLife("hours");
  return faculty;
}

export async function getGallery(): Promise<GalleryItem[]> {
  "use cache";
  cacheTag("gallery");
  cacheLife("hours");
  return gallery;
}
