import type { StatsData } from "@/lib/content/types";

export function StatsBlock({ data }: { data: StatsData }) {
  return (
    <div className="wrap">
      <div className="facts">
        {data.items.map((item) => (
          <div key={item.label}>
            <b>{item.value}</b>
            <span>{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
