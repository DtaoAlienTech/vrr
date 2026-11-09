"use client";

import Link from "next/link";
import { useApi } from "@/lib/admin/hooks";
import { formatDateTime, timeAgo } from "@/lib/admin/format";
import type { Dashboard } from "@/lib/admin/types";
import { useUser } from "./session";
import { Card, EmptyState, ErrorState, Heading, Loading, StatusPill } from "./ui";

const ENTITY: Record<string, string> = { news: "News", activity: "Activity", page: "Page", settings: "Settings" };
const ACTION: Record<string, string> = { create: "created", update: "edited", delete: "deleted", restore: "restored" };

function entityHref(entity: string, id: number): string | null {
  if (entity === "news") return `/admin/news/${id}`;
  if (entity === "activity") return `/admin/activities/${id}`;
  if (entity === "page") return `/admin/pages/${id}`;
  if (entity === "settings") return "/admin/settings";
  return null;
}

export function DashboardScreen() {
  const user = useUser();
  const { data, error, loading, reload } = useApi<Dashboard>("/admin/dashboard");

  return (
    <>
      <Heading title={`Welcome, ${user.name.split(" ")[0]}`} sub="Everything you change here appears on the website within seconds." />
      <div className="qa">
        <Link href="/admin/news/new">
          <i>+</i>
          <b>Add news or notice</b>
          <small>Publish an announcement</small>
        </Link>
        <Link href="/admin/activities/new">
          <i>+</i>
          <b>Add an activity</b>
          <small>NSS, Leo Club, events</small>
        </Link>
        <Link href="/admin/media">
          <i>↑</i>
          <b>Upload photos</b>
          <small>Photos and PDF files</small>
        </Link>
        <Link href="/admin/enquiries">
          <i>{data?.counts.newEnquiries ?? "•"}</i>
          <b>Enquiries</b>
          <small>{data ? `${data.counts.newEnquiries} new` : "People who asked about admission"}</small>
        </Link>
        <Link href="/admin/pages">
          <i>✎</i>
          <b>Edit page content</b>
          <small>Home, About, Contact …</small>
        </Link>
        <Link href="/admin/gallery">
          <i>▣</i>
          <b>Gallery</b>
          <small>Add and arrange photos</small>
        </Link>
      </div>

      {loading && <Loading />}
      {error && <ErrorState problem={error} retry={reload} />}
      {data && (
        <div className="adm-split">
          <Card title="Latest enquiries" actions={<Link href="/admin/enquiries">See all</Link>}>
            {data.recentEnquiries.length === 0 ? (
              <EmptyState>No enquiries yet. They appear here when someone fills the form on the website.</EmptyState>
            ) : (
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Phone</th>
                    <th>Course</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recentEnquiries.map((enquiry) => (
                    <tr key={enquiry.id}>
                      <td>{enquiry.name}</td>
                      <td>{enquiry.phone}</td>
                      <td>{enquiry.course ?? "—"}</td>
                      <td>
                        <StatusPill status={enquiry.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
          <div>
            <Card title="On the website">
              <dl className="astats">
                <div>
                  <dt>News published</dt>
                  <dd>{data.counts.publishedNews}</dd>
                </div>
                <div>
                  <dt>News drafts</dt>
                  <dd>{data.counts.draftNews}</dd>
                </div>
                <div>
                  <dt>Activities published</dt>
                  <dd>{data.counts.publishedActivities}</dd>
                </div>
                <div>
                  <dt>Photos and files</dt>
                  <dd>{data.counts.media}</dd>
                </div>
              </dl>
            </Card>
            <Card title="Recent changes">
              {data.recentChanges.length === 0 ? (
                <EmptyState>Changes made in this panel are listed here.</EmptyState>
              ) : (
                <ul className="alist">
                  {data.recentChanges.map((change) => {
                    const href = entityHref(change.entity, change.entityId);
                    const name = change.label ?? "(deleted)";
                    return (
                      <li key={change.id}>
                        {href && change.label ? <Link href={href}>{name}</Link> : <span>{name}</span>}
                        <small>
                          {ENTITY[change.entity] ?? change.entity} {ACTION[change.action] ?? change.action}
                          {change.userName ? ` by ${change.userName}` : ""} · <time dateTime={change.createdAt} title={formatDateTime(change.createdAt)}>{timeAgo(change.createdAt)}</time>
                        </small>
                      </li>
                    );
                  })}
                </ul>
              )}
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
