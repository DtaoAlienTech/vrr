"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Fragment, useEffect, useMemo, useState } from "react";
import { api, withQuery } from "@/lib/admin/api";
import { formatDateTime } from "@/lib/admin/format";
import { useApi } from "@/lib/admin/hooks";
import { initialValue, normalizeServerPath, prune, validate, variantKinds, type JsonSchema, type Problems } from "@/lib/admin/json-schema";
import { labelFor } from "@/lib/admin/labels";
import { ApiProblem } from "@/lib/admin/problem";
import { seoChecks, serpPreview } from "@/lib/admin/seo";
import type { Revision } from "@/lib/admin/types";
import { cx } from "@/lib/cx";
import { useDirty } from "./dirty";
import { PreviewButton } from "./PreviewButton";
import { useFeedback } from "./feedback";
import { SchemaForm } from "./SchemaForm";
import { useUser } from "./session";
import type { Card as CardConfig, Item, Json, ResourceConfig } from "./resources";
import { Button, Card, EmptyState, ErrorState, Heading, Loading, Notice, StatusPill } from "./ui";

type Forms = Record<string, { label: string; schema: JsonSchema }>;
const text = (value: unknown): string => (typeof value === "string" ? value : "");

/** Addresses of the site's pages, offered as suggestions in link fields. */
export function useSitePaths(): string[] {
  const { data } = useApi<{ slug: string }[]>("/admin/pages");
  return useMemo(() => ["/", ...(data ?? []).filter((p) => p.slug).map((p) => `/${p.slug}`)], [data]);
}

// ============================================================ list

export function ResourceList({ config }: { config: ResourceConfig }) {
  const user = useUser();
  const feedback = useFeedback();
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const { data, error, loading, reload } = useApi<Item[]>(withQuery(config.api, { status: status || undefined, q: q || undefined, limit: 200 }));
  const canCreate = !config.createRole || user.role === config.createRole;
  const filtered = Boolean(status || q);

  useEffect(() => {
    const timer = window.setTimeout(() => setQ(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  async function moveItem(index: number, delta: number) {
    if (!data) return;
    const ids = data.map((item) => item.id);
    const target = index + delta;
    if (target < 0 || target >= ids.length) return;
    [ids[index], ids[target]] = [ids[target], ids[index]];
    try {
      await api.post(`${config.api}/reorder`, { ids });
      reload();
    } catch (problem) {
      feedback.error(problem instanceof ApiProblem ? problem.message : "Could not change the order.");
    }
  }

  return (
    <>
      <Heading
        title={config.title}
        sub={config.sub}
        actions={
          <>
            {config.listActions && <config.listActions reload={reload} />}
            {canCreate && (
              <Link className="btn btn-primary btn-sm" href={`${config.route}/new`}>
                + Add {config.singular}
              </Link>
            )}
          </>
        }
      />
      {(config.filters?.search || config.filters?.status) && (
        <div className="mtools">
          {config.filters.search && <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search by title" aria-label="Search" />}
          {config.filters.status && (
            <select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Status">
              <option value="">All</option>
              <option value="published">Published</option>
              <option value="draft">Drafts</option>
            </select>
          )}
        </div>
      )}
      {loading && !data && <Loading />}
      {error && <ErrorState problem={error} retry={reload} />}
      {data && (
        <Card>
          {data.length === 0 ? (
            <EmptyState>{filtered ? "Nothing matches." : `No ${config.title.toLowerCase()} yet.`}</EmptyState>
          ) : (
            <table className="tbl">
              <thead>
                <tr>
                  {config.columns.map((column) => (
                    <th key={column.header}>{column.header}</th>
                  ))}
                  {config.reorder && !filtered && <th>Order</th>}
                </tr>
              </thead>
              <tbody>
                {data.map((item, index) => (
                  <tr key={item.id}>
                    {config.columns.map((column) => (
                      <td key={column.header}>{column.cell(item, config.route)}</td>
                    ))}
                    {config.reorder && !filtered && (
                      <td className="rowbtns">
                        <button type="button" className="tbtn" aria-label={`Move ${index + 1} up`} disabled={index === 0} onClick={() => moveItem(index, -1)}>
                          ↑
                        </button>
                        <button type="button" className="tbtn" aria-label={`Move ${index + 1} down`} disabled={index === data.length - 1} onClick={() => moveItem(index, 1)}>
                          ↓
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}
    </>
  );
}

// ============================================================ editor

export function ResourceEditor({ config, id }: { config: ResourceConfig; id: string }) {
  const creating = id === "new";
  const [version, setVersion] = useState(0);
  const forms = useApi<Forms>("/admin/forms/schema");
  const item = useApi<Item>(creating ? null : `${config.api}/${id}`);

  if (forms.error) return <ErrorState problem={forms.error} retry={forms.reload} />;
  if (item.error) {
    return (
      <>
        <Heading title={`Edit ${config.singular}`} />
        <ErrorState problem={item.error} retry={item.reload} />
        <p>
          <Link href={config.route}>← Back to {config.title.toLowerCase()}</Link>
        </p>
      </>
    );
  }
  const schema = forms.data?.[config.formKey]?.schema;
  if (!schema || (!creating && !item.data)) return <Loading />;

  return (
    <EditorBody
      key={`${id}-${version}`}
      config={config}
      schema={schema}
      item={creating ? undefined : item.data}
      onRestored={() => {
        item.reload();
        setVersion((v) => v + 1);
      }}
    />
  );
}

function EditorBody({ config, schema, item: loaded, onRestored }: { config: ResourceConfig; schema: JsonSchema; item?: Item; onRestored: () => void }) {
  const user = useUser();
  const router = useRouter();
  const feedback = useFeedback();
  const paths = useSitePaths();
  const [item, setItem] = useState<Item | undefined>(loaded);
  const [form, setForm] = useState<Json>(() => (loaded ? config.toForm(loaded) : { ...(initialValue(schema, schema) as Json), ...config.blank }));
  const [saved, setSaved] = useState(() => JSON.stringify(prune(form) ?? {}));
  const [submitted, setSubmitted] = useState(false);
  const [serverProblems, setServerProblems] = useState<Problems>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [saves, setSaves] = useState(0); // counts saves, so the history panel reloads

  const clean = useMemo(() => (prune(form) ?? {}) as Json, [form]);
  const dirty = JSON.stringify(clean) !== saved;
  useDirty(dirty);

  const clientProblems = useMemo(() => validate(schema, form), [schema, form]);
  const problems = useMemo(() => ({ ...(submitted ? clientProblems : {}), ...serverProblems }), [submitted, clientProblems, serverProblems]);
  const kinds = useMemo(() => variantKinds(schema), [schema]);
  const canDelete = item && (!config.deleteRole || user.role === config.deleteRole);
  const actions = config.actions?.(form) ?? [{ label: "Save", primary: true }];
  const status = text(form.status);

  async function save(label: string, patch?: Json) {
    // The button's own change (for example status: published) is applied only if the save works;
    // a refused save must leave the form exactly as it was.
    const next = { ...form, ...patch };
    setSubmitted(true);
    setServerProblems({});
    const found = validate(schema, next);
    if (Object.keys(found).length > 0) {
      feedback.error("Please check the fields marked in red.");
      window.setTimeout(() => document.querySelector(".has-error, .ferr")?.scrollIntoView({ block: "center", behavior: "smooth" }), 0);
      return;
    }
    setBusy(label);
    try {
      const body = prune(next) ?? {};
      const out = item ? await api.put<Item>(`${config.api}/${item.id}`, body) : await api.post<Item>(config.api, body);
      const fresh = config.toForm(out);
      setItem(out);
      setForm(fresh);
      setSaved(JSON.stringify(prune(fresh) ?? {}));
      setSubmitted(false);
      setSaves((count) => count + 1);
      feedback.ok(item ? "Saved. The website shows it in a moment." : "Created.");
      if (!item) router.replace(`${config.route}/${out.id}`);
    } catch (problem) {
      if (problem instanceof ApiProblem) {
        const mapped: Problems = {};
        for (const [field, message] of Object.entries(problem.fieldMap())) mapped[normalizeServerPath(field, kinds)] = message;
        if (problem.code === "slug_taken") mapped.slug = problem.message;
        setServerProblems(mapped);
        feedback.error(Object.keys(mapped).length > 0 ? "Please check the fields marked in red." : problem.message);
        window.setTimeout(() => document.querySelector(".has-error, .ferr")?.scrollIntoView({ block: "center", behavior: "smooth" }), 0);
      } else feedback.error("Something went wrong. Please try again.");
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    if (!item) return;
    const sure = await feedback.confirm({ title: `Delete this ${config.singular}?`, message: "It disappears from the website. You can bring it back from the history if it has one.", confirmLabel: "Delete", danger: true });
    if (!sure) return;
    try {
      await api.delete(`${config.api}/${item.id}`);
      setSaved(JSON.stringify(clean)); // nothing left to lose
      feedback.ok("Deleted.");
      router.push(config.route);
    } catch (problem) {
      feedback.error(problem instanceof ApiProblem ? problem.message : "Could not delete.");
    }
  }

  const publicPath = config.publicPath?.(form, item);
  const renderCard = (card: CardConfig) => (
    <Card key={card.title} title={card.title}>
      <SchemaForm schema={schema} value={form} onChange={setForm} problems={problems} only={card.fields} paths={paths} />
      {card.seo && <SeoPanel form={form} path={publicPath ?? "/"} />}
      {card.actions && (
        <div className="btnrow">
          {actions.map((action) => (
            <Button key={action.label} variant={action.primary ? "primary" : "ghost"} busy={busy === action.label} disabled={busy !== null} onClick={() => save(action.label, action.patch)}>
              {action.label}
            </Button>
          ))}
        </div>
      )}
    </Card>
  );

  return (
    <>
      <Heading
        title={item ? `Edit ${config.singular}` : `Add ${config.singular}`}
        sub={
          <>
            {status && <StatusPill status={status} />} {dirty ? <span className="st dr">Unsaved changes</span> : item && <span className="fhelp">All changes saved</span>}
          </>
        }
        actions={
          <>
            <Link className="btn btn-ghost btn-sm" href={config.route}>
              ← Back to list
            </Link>
            {item && config.previewKind && <PreviewButton kind={config.previewKind} id={item.id} unsaved={dirty} />}
            {item && publicPath && status !== "draft" && (
              <a className="btn btn-ghost btn-sm" href={publicPath} target="_blank" rel="noopener">
                View on website
              </a>
            )}
          </>
        }
      />
      {Object.keys(problems).length > 0 && (
        <Notice kind="error">
          <b>Please fix {Object.keys(problems).length === 1 ? "this" : "these"} before saving:</b>{" "}
          {Object.entries(problems)
            .slice(0, 4)
            .map(([path, message]) => `${labelFor(path.split(".").filter((part) => !/^\d+$/.test(part)).at(-1) ?? path)}: ${message}`)
            .join(" · ")}
          {Object.keys(problems).length > 4 ? ` · and ${Object.keys(problems).length - 4} more` : ""}
        </Notice>
      )}
      <div className="adm-split">
        <div>
          <Card>
            <SchemaForm schema={schema} value={form} onChange={setForm} problems={problems} only={config.main} paths={paths} />
          </Card>
        </div>
        <div>
          {config.cards.map(renderCard)}
          {config.history && item && <HistoryCard entity={config.history} entityId={item.id} onRestored={onRestored} dirty={dirty} version={saves} />}
          {canDelete && (
            <Card title="Delete">
              <p className="fhelp">Removes it from the website.</p>
              <Button variant="danger" onClick={remove}>
                Delete this {config.singular}
              </Button>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}

// ============================================================ side panels

type PublicSettings = { name: string; seo: { titleTemplate: string } };

function SeoPanel({ form, path }: { form: Json; path: string }) {
  const settings = useApi<PublicSettings>("/public/settings");
  const title = text(form.seoTitle) || text(form.title) || text(form.name);
  const description = text(form.seoDescription) || text(form.summary);
  const checks = seoChecks({ title, description });
  const preview = serpPreview({ title: title || "Title", template: settings.data?.seo.titleTemplate ?? "%s", description: description || "The description appears here.", origin: typeof window === "undefined" ? "http://localhost" : window.location.origin, path });
  return (
    <>
      <div className="serp" aria-label="How it looks on Google">
        <b>{preview.title}</b>
        <small>{preview.url}</small>
        <span>{preview.description}</span>
      </div>
      <ul className="seochecks" aria-label="Search engine checks">
        {checks.map((check) => (
          <li key={check.id} className={`seo-${check.status}`}>
            <span aria-hidden="true">{check.status === "ok" ? "✓" : check.status === "warn" ? "!" : "✕"}</span> {check.label}
            {check.hint && <small> — {check.hint}</small>}
          </li>
        ))}
      </ul>
    </>
  );
}

const ACTION_WORDS: Record<string, string> = { create: "Created", update: "Edited", delete: "Deleted", restore: "Restored an older version" };

export function HistoryCard({ entity, entityId, onRestored, dirty, version = 0 }: { entity: string; entityId: number; onRestored: () => void; dirty?: boolean; version?: number }) {
  const feedback = useFeedback();
  const { data, error, reload } = useApi<Revision[]>(withQuery("/admin/revisions", { entity, entity_id: entityId, limit: 15, v: version }));
  const [open, setOpen] = useState(false);

  async function restore(revision: Revision) {
    const sure = await feedback.confirm({
      title: "Go back to this version?",
      message: dirty ? "Your unsaved changes will be lost. The current saved version stays in the history, so you can undo this." : "The current version stays in the history, so you can undo this.",
      confirmLabel: "Restore",
    });
    if (!sure) return;
    try {
      await api.post(`/admin/revisions/${revision.id}/restore`);
      feedback.ok("Restored.");
      reload();
      onRestored();
    } catch (problem) {
      feedback.error(problem instanceof ApiProblem ? problem.message : "Could not restore that version.");
    }
  }

  return (
    <Card title="History" actions={<button type="button" className="alink" onClick={() => setOpen(!open)} aria-expanded={open}>{open ? "Hide" : "Show"}</button>}>
      {error && <ErrorState problem={error} retry={reload} />}
      {data && data.length === 0 && <p className="fhelp">No saved versions yet.</p>}
      {open && data && (
        <ul className="alist history">
          {data.map((revision, index) => (
            <Fragment key={revision.id}>
              <li>
                <span>
                  {ACTION_WORDS[revision.action] ?? revision.action}
                  {revision.userName ? ` by ${revision.userName}` : ""}
                </span>
                <small>
                  <time dateTime={revision.createdAt}>{formatDateTime(revision.createdAt)}</time>
                  {index === 0 ? " · current" : ""}
                </small>
                {index > 0 && (
                  <button type="button" className={cx("alink")} onClick={() => restore(revision)}>
                    Restore this version
                  </button>
                )}
              </li>
            </Fragment>
          ))}
        </ul>
      )}
      {!open && data && data.length > 0 && <p className="fhelp">{data.length} saved version{data.length === 1 ? "" : "s"}. Any earlier version can be restored.</p>}
    </Card>
  );
}
