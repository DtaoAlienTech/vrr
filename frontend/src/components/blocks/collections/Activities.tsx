import { FilterGroup } from "@/components/ui/FilterGroup";
import { Media } from "@/components/ui/Media";
import { SmartLink } from "@/components/ui/SmartLink";
import type { Activity } from "@/lib/content/types";
import { cx } from "@/lib/cx";

const photoCount = (activity: Activity) =>
  `${activity.photos.length} ${activity.photos.length === 1 ? "photo" : "photos"}`;

/** Cards for the home page. Each links to the album on the Activities page. */
export function ActivityCards({ activities }: { activities: Activity[] }) {
  return (
    <div className="grid2">
      {activities.map((activity) => {
        const href = `/activities#${activity.slug}`;
        return (
          <article key={activity.slug} className="act">
            <SmartLink className="actimg" href={href}>
              <Media media={activity.cover} sizes="(min-width: 760px) 50vw, 100vw" />
            </SmartLink>
            <div className="body">
              <span className="cat">{activity.group}</span>
              {activity.year && <time>{activity.year}</time>}
              <h3>{activity.title}</h3>
              <p>{activity.summary}</p>
              <SmartLink className="more" href={href}>
                View {photoCount(activity)} →
              </SmartLink>
            </div>
          </article>
        );
      })}
    </div>
  );
}

/** The Activities page: one album per activity, with a filter by group. */
export function ActivityAlbums({ activities }: { activities: Activity[] }) {
  const groups = [...new Map(activities.map((a) => [a.groupKey, a.group])).entries()].map(
    ([value, label]) => ({ value, label }),
  );
  return (
    <FilterGroup options={groups} label="Filter by group">
      {activities.map((activity) => (
        <article key={activity.slug} className="asec" id={activity.slug} data-cat={activity.groupKey}>
          <div className="ahead">
            <span className="cat">{activity.group}</span>
            {activity.year && <time>{activity.year}</time>}
            <h2>{activity.title}</h2>
            <p>{activity.summary}</p>
          </div>
          <div className={cx("agrid", activity.photos.length === 1 && "one")}>
            {activity.photos.map((photo, index) => (
              <div key={photo.media.url} className={cx("ph", "img", index === 0 && "lead")}>
                <Media media={photo.media} sizes="(min-width: 820px) 33vw, 50vw" />
              </div>
            ))}
          </div>
        </article>
      ))}
    </FilterGroup>
  );
}
