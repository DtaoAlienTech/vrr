import type { DocItem } from "@/lib/content/types";
import { SmartLink } from "./SmartLink";

function DocCard({ doc }: { doc: DocItem }) {
  const body = (
    <>
      {doc.href && <span className="pdfi">PDF</span>}
      <div>
        <b>{doc.title}</b>
        {doc.note && <small>{doc.note}</small>}
      </div>
    </>
  );
  // Only documents that have a file are links and get the PDF badge.
  return doc.href ? (
    <SmartLink className="doc" href={doc.href}>
      {body}
    </SmartLink>
  ) : (
    <div className="doc">{body}</div>
  );
}

export function DocList({ docs }: { docs: DocItem[] }) {
  if (docs.length === 0) return null;
  return (
    <div className="grid2">
      {docs.map((doc) => (
        <DocCard key={doc.title} doc={doc} />
      ))}
    </div>
  );
}
