import { Section } from "@/components/ui/Section";
import { getCourses } from "@/lib/content/api";
import type { EnquiryCtaData } from "@/lib/content/types";
import { EnquiryForm } from "./EnquiryForm";

export async function EnquiryCtaBlock({ data }: { data: EnquiryCtaData }) {
  const courses = await getCourses();
  return (
    <Section tone="band" id="enquire">
      <div className="box">
        <div>
          <h2>{data.heading}</h2>
          <p>{data.text}</p>
        </div>
        <EnquiryForm courses={courses.map((course) => course.name)} tone="dark" />
      </div>
    </Section>
  );
}
