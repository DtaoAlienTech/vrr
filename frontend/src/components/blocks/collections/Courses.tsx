import { KeyValueTable } from "@/components/ui/KeyValueTable";
import { LinkButton } from "@/components/ui/LinkButton";
import { SmartLink } from "@/components/ui/SmartLink";
import type { Course } from "@/lib/content/types";

export function CourseCards({ courses }: { courses: Course[] }) {
  return (
    <div className="grid3">
      {courses.map((course) => (
        <article key={course.slug} className="idx">
          <span className="tab">{course.tab}</span>
          <h3>{course.name}</h3>
          <div className="meta">
            <span>{course.duration}</span>
            <span>{course.department}</span>
          </div>
          <p>{course.summary}</p>
          <SmartLink className="more" href={`/courses/${course.slug}`}>
            View course →
          </SmartLink>
        </article>
      ))}
    </div>
  );
}

/** Facts about a course. Only the facts the college has filled in are shown. */
export function courseFacts(course: Course): { label: string; value: string }[] {
  const facts: [string, string | undefined][] = [
    ["Duration", course.duration],
    ["Department", course.department],
    ["Affiliation", course.affiliation],
    ["Eligibility", course.eligibility],
    ["Seats", course.seats],
    ["Fees", course.fees],
  ];
  return facts.flatMap(([label, value]) => (value ? [{ label, value }] : []));
}

export function CourseDetailedList({ courses }: { courses: Course[] }) {
  return (
    <>
      {courses.map((course) => (
        <article key={course.slug} className="crow">
          <div>
            <span className="tab">{course.tab}</span>
            <h2>{course.name}</h2>
            <p className="muted">{course.summary}</p>
            <LinkButton href={`/courses/${course.slug}`} variant="ghost" size="sm">
              Course details
            </LinkButton>
          </div>
          <KeyValueTable rows={courseFacts(course)} />
        </article>
      ))}
    </>
  );
}
