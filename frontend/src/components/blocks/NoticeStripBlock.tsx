import { NoticeTicker } from "@/components/ui/NoticeTicker";
import type { NoticeStripData } from "@/lib/content/types";

export function NoticeStripBlock({ data }: { data: NoticeStripData }) {
  return (
    <div className="notices mt-40">
      <div className="wrap">
        <span className="tag">{data.label}</span>
        <NoticeTicker items={data.items} />
      </div>
    </div>
  );
}
