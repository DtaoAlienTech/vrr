import { SmartLink } from "@/components/ui/SmartLink";
import type { NewsItem } from "@/lib/content/types";
import { cx } from "@/lib/cx";
import { dateParts } from "@/lib/format";

export function NewsList({ items }: { items: NewsItem[] }) {
  if (items.length === 0) return <p className="lead">No notices have been published yet.</p>;
  return (
    <div className="news">
      {items.map((item) => {
        const date = dateParts(item.publishedAt);
        return (
          <article key={item.slug} className={cx("ni", item.pinned && "pin")}>
            <div className="date">
              <b>{date.day}</b>
              <small>{date.monthYear}</small>
            </div>
            <div>
              {item.pinned && <span className="cat pinned">Pinned</span>}
              <span className="cat">{item.category}</span>
              <h3>
                <SmartLink href={`/news/${item.slug}`}>{item.title}</SmartLink>
              </h3>
              <p>{item.summary}</p>
              {item.attachments.some((file) => file.href) && <span className="pdfb">PDF attached</span>}
            </div>
          </article>
        );
      })}
    </div>
  );
}
