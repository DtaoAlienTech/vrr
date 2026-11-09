"use client";

import { useEffect, useState } from "react";
import { api, withQuery } from "@/lib/admin/api";
import { formatDateTime } from "@/lib/admin/format";
import { useApi } from "@/lib/admin/hooks";
import { ApiProblem } from "@/lib/admin/problem";
import type { Enquiry } from "@/lib/admin/types";
import { useFeedback } from "./feedback";
import { Button, Card, EmptyState, ErrorState, Heading, Loading, StatusPill } from "./ui";

const PAGE = 30;

function Row({ item, onChange }: { item: Enquiry; onChange: (next: Enquiry) => void }) {
  const feedback = useFeedback();
  const [busy, setBusy] = useState(false);

  async function setStatus(status: Enquiry["status"]) {
    setBusy(true);
    try {
      onChange(await api.patch<Enquiry>(`/admin/enquiries/${item.id}`, { status }));
    } catch (problem) {
      feedback.error(problem instanceof ApiProblem ? problem.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <tr>
      <td>
        <time dateTime={item.createdAt}>{formatDateTime(item.createdAt)}</time>
      </td>
      <td>
        <b>{item.name}</b>
        <br />
        <a href={`tel:${item.phone}`}>{item.phone}</a>
      </td>
      <td>{item.course ?? "—"}</td>
      <td className="enq-message">{item.message ?? "—"}</td>
      <td>
        <StatusPill status={item.status} />
      </td>
      <td className="enq-actions">
        {item.status === "new" && (
          <Button variant="ghost" busy={busy} onClick={() => setStatus("contacted")}>
            Mark contacted
          </Button>
        )}
        {item.status === "contacted" && (
          <Button variant="ghost" busy={busy} onClick={() => setStatus("closed")}>
            Close
          </Button>
        )}
        {item.status !== "new" && (
          <button type="button" className="alink" disabled={busy} onClick={() => setStatus("new")}>
            Reopen
          </button>
        )}
      </td>
    </tr>
  );
}

export function EnquiriesScreen() {
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const first = useApi<Enquiry[]>(withQuery("/admin/enquiries", { status: status || undefined, q: q || undefined, limit: PAGE }));
  const [more, setMore] = useState<Enquiry[]>([]);
  const [done, setDone] = useState(false);
  const [changed, setChanged] = useState<Record<number, Enquiry>>({});

  useEffect(() => {
    const timer = window.setTimeout(() => setQ(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  const items = [...(first.data ?? []), ...more].map((item) => changed[item.id] ?? item);

  async function older() {
    const last = items.at(-1);
    if (!last) return;
    const page = await api.get<Enquiry[]>(withQuery("/admin/enquiries", { status: status || undefined, q: q || undefined, limit: PAGE, before_id: last.id }));
    setMore((current) => [...current, ...page]);
    if (page.length < PAGE) setDone(true);
  }

  const exportUrl = withQuery("/api/v1/admin/enquiries/export.csv", { status: status || undefined, q: q || undefined });
  return (
    <>
      <Heading
        title="Enquiries"
        sub="People who asked about admission through the website. Call them back, then mark them as contacted."
        actions={
          <a className="btn btn-ghost btn-sm" href={exportUrl} download>
            Download as spreadsheet (CSV)
          </a>
        }
      />
      <div className="mtools">
        <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search by name, phone, course or message" aria-label="Search enquiries" />
        <select
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setMore([]);
            setDone(false);
          }}
          aria-label="Status"
        >
          <option value="">All</option>
          <option value="new">New</option>
          <option value="contacted">Contacted</option>
          <option value="closed">Closed</option>
        </select>
      </div>
      {first.loading && !first.data && <Loading />}
      {first.error && <ErrorState problem={first.error} retry={first.reload} />}
      {first.data && (
        <Card>
          {items.length === 0 ? (
            <EmptyState>No enquiries{status || q ? " match" : " yet"}.</EmptyState>
          ) : (
            <table className="tbl">
              <thead>
                <tr>
                  <th>Received</th>
                  <th>Who</th>
                  <th>Course</th>
                  <th>Message</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <Row key={item.id} item={item} onChange={(next) => setChanged((current) => ({ ...current, [next.id]: next }))} />
                ))}
              </tbody>
            </table>
          )}
          {!done && (first.data?.length ?? 0) >= PAGE && (
            <div className="btnrow">
              <Button variant="ghost" onClick={older}>
                Show older enquiries
              </Button>
            </div>
          )}
        </Card>
      )}
    </>
  );
}
