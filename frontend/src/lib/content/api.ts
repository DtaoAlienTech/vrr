// The single data-access layer for the public site. Every function is cached and tagged, so the
// admin can refresh exactly what changed through /internal/revalidate (see that route).
// Content comes from the FastAPI backend (public, read-only endpoints; the response shapes are the
// types in ./types.ts).
import { cacheLife, cacheTag } from "next/cache";
import type {
  Activity,
  Course,
  FacultyMember,
  GalleryItem,
  NewsItem,
  PageData,
  PageKey,
  PreviewData,
  SiteSettings,
} from "./types";

const BACKEND_URL = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

/** `null` when the content does not exist (404). Any other failure throws, so a hiccup of the API
 * is never cached as "not found" (errors are not cached; the next visit tries again). */
async function fetchContent<T>(path: string): Promise<T | null> {
  const response = await fetch(`${BACKEND_URL}/api/v1/public${path}`, {
    headers: { accept: "application/json" },
    signal: AbortSignal.timeout(10_000),
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`Content API ${path} answered ${response.status}`);
  return (await response.json()) as T;
}

async function required<T>(path: string): Promise<T> {
  const data = await fetchContent<T>(path);
  if (data === null) throw new Error(`Content API ${path} has no content`);
  return data;
}

const segment = encodeURIComponent;

export async function getSiteSettings(): Promise<SiteSettings> {
  "use cache";
  cacheTag("settings");
  cacheLife("hours");
  return required<SiteSettings>("/settings");
}

export async function getPage(key: PageKey): Promise<PageData | null> {
  "use cache";
  cacheTag("pages", `page:${key}`);
  cacheLife("hours");
  return fetchContent<PageData>(`/pages/${segment(key)}`);
}

/** Finds a page by its URL path (without the leading slash). The home page is not included. */
export async function getPageBySlug(slug: string): Promise<PageData | null> {
  "use cache";
  cacheTag("pages", `page-slug:${slug}`);
  cacheLife("hours");
  return slug === "" ? null : fetchContent<PageData>(`/pages/by-slug/${segment(slug)}`);
}

export async function getPageSlugs(): Promise<string[]> {
  "use cache";
  cacheTag("pages");
  cacheLife("hours");
  const pages = await required<{ slug: string }[]>("/pages");
  return pages.map((page) => page.slug).filter((slug) => slug !== "");
}

export async function getCourses(limit?: number): Promise<Course[]> {
  "use cache";
  cacheTag("courses");
  cacheLife("hours");
  return (await required<Course[]>("/courses")).slice(0, limit);
}

export async function getCourse(slug: string): Promise<Course | null> {
  "use cache";
  cacheTag("courses", `course:${slug}`);
  cacheLife("hours");
  return fetchContent<Course>(`/courses/${segment(slug)}`);
}

export async function getActivities(limit?: number): Promise<Activity[]> {
  "use cache";
  cacheTag("activities");
  cacheLife("hours");
  return (await required<Activity[]>("/activities")).slice(0, limit);
}

/** The API sends pinned items first, then newest first. */
export async function getNews(limit?: number): Promise<NewsItem[]> {
  "use cache";
  cacheTag("news");
  cacheLife("hours");
  return (await required<NewsItem[]>("/news")).slice(0, limit);
}

export async function getNewsItem(slug: string): Promise<NewsItem | null> {
  "use cache";
  cacheTag("news", `news:${slug}`);
  cacheLife("hours");
  return fetchContent<NewsItem>(`/news/${segment(slug)}`);
}

export async function getFaculty(): Promise<FacultyMember[]> {
  "use cache";
  cacheTag("faculty");
  cacheLife("hours");
  return required<FacultyMember[]>("/faculty");
}

export async function getGallery(): Promise<GalleryItem[]> {
  "use cache";
  cacheTag("gallery");
  cacheLife("hours");
  return required<GalleryItem[]>("/gallery");
}

/** A draft, opened with a signed preview token. Never cached (it is private and changes while the
 * editor works), so it is a plain fetch, not a tagged cache function. `null` = the token is wrong,
 * expired, or the item was deleted. */
export async function getPreview(token: string): Promise<PreviewData | null> {
  if (!/^[A-Za-z0-9._-]{1,200}$/.test(token)) return null;
  const response = await fetch(`${BACKEND_URL}/api/v1/preview/${segment(token)}`, {
    headers: { accept: "application/json" },
    cache: "no-store",
    signal: AbortSignal.timeout(10_000),
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`Preview API answered ${response.status}`);
  return (await response.json()) as PreviewData;
}
