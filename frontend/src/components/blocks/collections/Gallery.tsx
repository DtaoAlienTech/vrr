import { FilterGroup } from "@/components/ui/FilterGroup";
import { Media } from "@/components/ui/Media";
import type { GalleryItem } from "@/lib/content/types";
import { cx } from "@/lib/cx";

export function GalleryMosaic({ items }: { items: GalleryItem[] }) {
  if (items.length === 0) return <p className="lead">Photos will be added soon.</p>;
  const categories = [...new Map(items.map((i) => [i.category, i.categoryLabel])).entries()].map(
    ([value, label]) => ({ value, label }),
  );
  return (
    <FilterGroup options={categories} label="Filter photos">
      <div className="mosaic">
        {items.map((item, index) => (
          <div key={item.id} className={cx("ph", "img", index === 0 && "big")} data-cat={item.category}>
            <Media
              media={item.media}
              sizes={index === 0 ? "(min-width: 820px) 50vw, 100vw" : "(min-width: 820px) 25vw, 50vw"}
            />
            <span>{item.caption}</span>
          </div>
        ))}
      </div>
    </FilterGroup>
  );
}
