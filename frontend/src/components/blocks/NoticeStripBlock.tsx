import type { NoticeStripData } from "@/lib/content/types";

export function NoticeStripBlock({ data }: { data: NoticeStripData }) {
  return (
    <div className="notices mt-40">
      <div className="wrap">
        <span className="tag">{data.label}</span>
        <ul>
          {data.items.map((text) => (
            <li key={text}>{text}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
