import type { ReactNode } from "react";
import { LinkButton } from "@/components/ui/LinkButton";
import { Section, SectionHead } from "@/components/ui/Section";
import {
  getActivities,
  getCourses,
  getFaculty,
  getGallery,
  getNews,
} from "@/lib/content/api";
import type { CollectionListData } from "@/lib/content/types";
import { ActivityAlbums, ActivityCards } from "./collections/Activities";
import { CourseCards, CourseDetailedList } from "./collections/Courses";
import { FacultyGrid } from "./collections/Faculty";
import { GalleryMosaic } from "./collections/Gallery";
import { NewsList } from "./collections/News";

async function renderCollection(data: CollectionListData): Promise<ReactNode> {
  switch (data.collection) {
    case "courses": {
      const courses = await getCourses(data.limit);
      return data.layout === "detailed" ? (
        <CourseDetailedList courses={courses} />
      ) : (
        <CourseCards courses={courses} />
      );
    }
    case "activities": {
      const activities = await getActivities(data.limit);
      return data.layout === "albums" ? (
        <ActivityAlbums activities={activities} />
      ) : (
        <ActivityCards activities={activities} />
      );
    }
    case "news":
      return <NewsList items={await getNews(data.limit)} />;
    case "faculty":
      return <FacultyGrid members={await getFaculty()} />;
    case "gallery":
      return <GalleryMosaic items={await getGallery()} />;
  }
}

/**
 * Shows a list from the database (courses, activities, news, faculty or gallery) in the chosen
 * layout, anywhere on any page. `embedded` skips the section wrapper (inside the two-column layout).
 */
export async function CollectionListBlock({
  data,
  embedded = false,
}: {
  data: CollectionListData;
  embedded?: boolean;
}) {
  const body = await renderCollection(data);
  if (embedded) return <>{body}</>;
  return (
    <Section tone={data.tone} id={data.collection}>
      {data.heading && <SectionHead title={data.heading} intro={data.intro} />}
      {body}
      {data.cta && (
        <p className="mt-24">
          <LinkButton href={data.cta.href} variant="ghost">
            {data.cta.label}
          </LinkButton>
        </p>
      )}
    </Section>
  );
}
