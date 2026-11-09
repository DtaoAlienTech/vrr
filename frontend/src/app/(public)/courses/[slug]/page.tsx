import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PageHeaderBlock } from "@/components/blocks/PageHeaderBlock";
import { courseFacts } from "@/components/blocks/collections/Courses";
import { DocList } from "@/components/ui/DocList";
import { JsonLd } from "@/components/ui/JsonLd";
import { KeyValueTable } from "@/components/ui/KeyValueTable";
import { LinkButton } from "@/components/ui/LinkButton";
import { RichText } from "@/components/ui/RichText";
import { Section } from "@/components/ui/Section";
import { getCourse, getCourses, getSiteSettings } from "@/lib/content/api";
import { buildPageMetadata, courseJsonLd } from "@/lib/seo";

export async function generateStaticParams() {
  const courses = await getCourses();
  return courses.map((course) => ({ slug: course.slug }));
}

export async function generateMetadata(props: PageProps<"/courses/[slug]">): Promise<Metadata> {
  const { slug } = await props.params;
  const [course, settings] = await Promise.all([getCourse(slug), getSiteSettings()]);
  if (!course) return {};
  return buildPageMetadata(settings, {
    title: course.name,
    description: course.summary,
    path: `/courses/${slug}`,
    image: settings.seo.ogImage,
  });
}

export default async function CoursePage(props: PageProps<"/courses/[slug]">) {
  const { slug } = await props.params;
  const [course, settings] = await Promise.all([getCourse(slug), getSiteSettings()]);
  if (!course) notFound();

  return (
    <>
      <JsonLd data={courseJsonLd(course, settings)} />
      <PageHeaderBlock
        data={{
          title: course.name,
          subtitle: `${course.department} · ${course.duration} · ${settings.affiliationText}`,
          crumbs: [{ label: "Courses", href: "/courses" }],
        }}
      />
      <Section>
        <div className="split">
          <div className="stack">
            <div>
              <h2>About the course</h2>
              {course.description ? <RichText doc={course.description} /> : <p>{course.summary}</p>}
            </div>
            {course.subjects && course.subjects.length > 0 && (
              <div>
                <h3>What you will study</h3>
                <ul className="ticks">
                  {course.subjects.map((subject) => (
                    <li key={subject}>{subject}</li>
                  ))}
                </ul>
              </div>
            )}
            {course.syllabus?.href && (
              <div>
                <h3>Syllabus</h3>
                <DocList docs={[course.syllabus]} />
              </div>
            )}
          </div>
          <aside>
            <div className="sidebox">
              <h3>Course at a glance</h3>
              <KeyValueTable rows={courseFacts(course)} />
              <LinkButton href="/admissions#enquire" className="btn-block">
                Enquire about this course
              </LinkButton>
            </div>
          </aside>
        </div>
      </Section>
    </>
  );
}
