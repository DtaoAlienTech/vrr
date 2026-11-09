import { FilterGroup } from "@/components/ui/FilterGroup";
import { Media } from "@/components/ui/Media";
import type { FacultyMember } from "@/lib/content/types";
import { initials } from "@/lib/format";

export function FacultyGrid({ members }: { members: FacultyMember[] }) {
  if (members.length === 0) return <p className="lead">The faculty list will be published soon.</p>;
  const departments = [...new Map(members.map((m) => [m.departmentKey, m.department])).entries()].map(
    ([value, label]) => ({ value, label }),
  );
  return (
    <FilterGroup options={departments} label="Filter by department">
      <div className="fgrid">
        {members.map((member) => (
          <div key={member.id} className="fc" data-cat={member.departmentKey}>
            <div className="arch">
              {member.photo ? <Media media={member.photo} sizes="150px" /> : initials(member.name)}
            </div>
            <h3>{member.name}</h3>
            <small>{member.designation}</small>
            <small>{member.qualification}</small>
            <small>{member.department}</small>
          </div>
        ))}
      </div>
    </FilterGroup>
  );
}
