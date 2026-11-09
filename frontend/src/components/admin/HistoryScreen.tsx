"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { api, withQuery } from "@/lib/admin/api";
import { formatDateTime } from "@/lib/admin/format";
import { useApi } from "@/lib/admin/hooks";
import { ApiProblem } from "@/lib/admin/problem";
import type { RedirectItem, Revision } from "@/lib/admin/types";
import { useFeedback } from "./feedback";
import { useUser } from "./session";
import { Button, Card, EmptyState, ErrorState, Field, Heading, Loading, Notice } from "./ui";

type Entry = Revision & { label?: string };
const ENTITY: Record<string, string> = { news: "News", activity: "Activity", page: "Page", settings: "Settings" };
const ACTION: Record<string, string> = { create: "created", update: "edited", delete: "deleted", restore: "restored an older version of" };

function hrefFor(entry: Entry): string | null {
  if (entry.action === "delete" || !entry.label) return null;
  if (entry.entity === "news") return `/admin/news/${entry.entityId}`;
  if (entry.entity === "activity") return `/admin/activities/${entry.entityId}`;
  if (entry.entity === "page") return `/admin/pages/${entry.entityId}`;
  if (entry.entity === "settings") return "/admin/settings";
  return null;
}

function Changes() {
  const user = useUser();
  const feedback = useFeedback();
  const first = useApi<Entry[]>(withQuery("/admin/revisions", { limit: 30 }));
  const [more, setMore] = useState<Entry[]>([]);
  const [done, setDone] = useState(false);
  const entries = [...(first.data ?? []), ...more];

  async function older() {
    const last = entries.at(-1);
    if (!last) return;
    const page = await api.get<Entry[]>(withQuery("/admin/revisions", { limit: 30, before_id: last.id }));
    setMore((current) => [...current, ...page]);
    if (page.length < 30) setDone(true);
  }

  async function restore(entry: Entry) {
    const sure = await feedback.confirm({
      title: "Go back to this version?",
      message: `${ENTITY[entry.entity] ?? entry.entity} “${entry.label ?? "(deleted)"}” returns to how it was then. The current version stays in the history, so you can undo this.`,
      confirmLabel: "Restore",
    });
    if (!sure) return;
    try {
      await api.post(`/admin/revisions/${entry.id}/restore`);
      feedback.ok("Restored. The website shows it in a moment.");
      first.reload();
      setMore([]);
    } catch (problem) {
      feedback.error(problem instanceof ApiProblem ? problem.message : "Could not restore that version.");
    }
  }

  return (
    <Card title="Recent changes">
      <p className="fhelp">Every change to news, activities, pages and settings is kept. Choose “Restore” to go back to how something was.</p>
      {first.loading && !first.data && <Loading />}
      {first.error && <ErrorState problem={first.error} retry={first.reload} />}
      {first.data && entries.length === 0 && <EmptyState>No changes yet.</EmptyState>}
      {entries.length > 0 && (
        <table className="tbl">
          <thead>
            <tr>
              <th>What</th>
              <th>Who</th>
              <th>When</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => {
              const href = hrefFor(entry);
              const canRestore = !(entry.entity === "settings" && user.role !== "super_admin");
              return (
                <tr key={entry.id}>
                  <td>
                    {ENTITY[entry.entity] ?? entry.entity} {href ? <Link href={href}>{entry.label}</Link> : <span>{entry.label ?? "(deleted)"}</span>} <small>{ACTION[entry.action] ?? entry.action}</small>
                  </td>
                  <td>{entry.userName ?? "—"}</td>
                  <td>
                    <time dateTime={entry.createdAt}>{formatDateTime(entry.createdAt)}</time>
                  </td>
                  <td>
                    {canRestore && (
                      <button type="button" className="alink" onClick={() => restore(entry)} aria-label={`Restore ${entry.label ?? "item"} to the version of ${formatDateTime(entry.createdAt)}`}>
                        Restore
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      {!done && entries.length >= 30 && (
        <div className="btnrow">
          <Button variant="ghost" onClick={older}>
            Show older changes
          </Button>
        </div>
      )}
    </Card>
  );
}

function Redirects() {
  const feedback = useFeedback();
  const { data, error, loading, reload } = useApi<RedirectItem[]>("/admin/redirects");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [permanent, setPermanent] = useState(true);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function add(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    setBusy(true);
    try {
      await api.post("/admin/redirects", { fromPath: from.trim(), toPath: to.trim(), statusCode: permanent ? 301 : 302 });
      setFrom("");
      setTo("");
      feedback.ok("Redirect added.");
      reload();
    } catch (failure) {
      setProblem(failure instanceof ApiProblem ? (failure.errors[0]?.message ?? failure.message) : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(item: RedirectItem) {
    const sure = await feedback.confirm({ title: "Remove this redirect?", message: <>People who open <code>{item.fromPath}</code> will see “page not found”.</>, confirmLabel: "Remove", danger: true });
    if (!sure) return;
    try {
      await api.delete(`/admin/redirects/${item.id}`);
      reload();
    } catch (failure) {
      feedback.error(failure instanceof ApiProblem ? failure.message : "Something went wrong.");
    }
  }

  return (
    <Card title="Redirects">
      <p className="fhelp">When a page, course or news item gets a new web address, a redirect from the old one is made automatically, so old links and Google results keep working. You can also add one yourself.</p>
      <form className="redirect-form" onSubmit={add} noValidate>
        {problem && <Notice kind="error">{problem}</Notice>}
        <Field label="Old address" htmlFor="redirect-from" help="For example /old-page">
          <input id="redirect-from" type="text" value={from} onChange={(event) => setFrom(event.target.value)} />
        </Field>
        <Field label="New address" htmlFor="redirect-to" help="For example /about">
          <input id="redirect-to" type="text" value={to} onChange={(event) => setTo(event.target.value)} />
        </Field>
        <label className="ucheck">
          <input type="checkbox" checked={permanent} onChange={(event) => setPermanent(event.target.checked)} /> The move is permanent (recommended for Google)
        </label>
        <Button type="submit" busy={busy} disabled={!from.trim() || !to.trim()}>
          Add redirect
        </Button>
      </form>
      {loading && !data && <Loading />}
      {error && <ErrorState problem={error} retry={reload} />}
      {data && data.length === 0 && <EmptyState>No redirects yet.</EmptyState>}
      {data && data.length > 0 && (
        <table className="tbl">
          <thead>
            <tr>
              <th>From</th>
              <th>To</th>
              <th>Kind</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {data.map((item) => (
              <tr key={item.id}>
                <td>
                  <code>{item.fromPath}</code>
                </td>
                <td>
                  <code>{item.toPath}</code>
                </td>
                <td>{item.statusCode === 301 || item.statusCode === 308 ? "Permanent" : "Temporary"}</td>
                <td>
                  <button type="button" className="alink" onClick={() => remove(item)} aria-label={`Remove the redirect from ${item.fromPath}`}>
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

export function HistoryScreen() {
  return (
    <>
      <Heading title="History & redirects" sub="See who changed what and go back to an earlier version, and manage the redirects from old web addresses." />
      <Changes />
      <Redirects />
    </>
  );
}
