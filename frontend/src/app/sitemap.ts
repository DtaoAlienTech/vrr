import type { MetadataRoute } from "next";
import { getCourses, getNews, getPageSlugs, getPageBySlug } from "@/lib/content/api";
import { SITE_URL } from "@/lib/env";

/** Every public address, generated from the content. Pages marked noindex are left out. */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [slugs, courses, news] = await Promise.all([getPageSlugs(), getCourses(), getNews()]);
  const pages = await Promise.all(slugs.map((slug) => getPageBySlug(slug)));
  const indexable = slugs.filter((_, index) => !pages[index]?.seo.noindex);

  return [
    { url: `${SITE_URL}/`, changeFrequency: "weekly", priority: 1 },
    ...indexable.map((slug) => ({ url: `${SITE_URL}/${slug}`, changeFrequency: "weekly" as const, priority: 0.8 })),
    ...courses.map((course) => ({
      url: `${SITE_URL}/courses/${course.slug}`,
      changeFrequency: "monthly" as const,
      priority: 0.8,
    })),
    ...news.map((item) => ({
      url: `${SITE_URL}/news/${item.slug}`,
      lastModified: item.publishedAt,
      changeFrequency: "monthly" as const,
      priority: 0.6,
    })),
  ];
}
