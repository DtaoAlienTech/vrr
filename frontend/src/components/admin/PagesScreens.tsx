"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { api } from "@/lib/admin/api";
import { useApi } from "@/lib/admin/hooks";
import { initialValue, normalizeServerPath, prune, validate, variantKinds, type JsonSchema, type Problems } from "@/lib/admin/json-schema";
import { SECTION_LABELS } from "@/lib/admin/labels";
import { rememberBriefs } from "@/lib/admin/media-cache";
import { ApiProblem } from "@/lib/admin/problem";
import { seoChecks } from "@/lib/admin/seo";
import type { MediaBrief } from "@/lib/admin/types";
import { cx } from "@/lib/cx";
import { useDirty } from "./dirty";
import { useFeedback } from "./feedback";
import { PreviewButton } from "./PreviewButton";
import { HistoryCard } from "./ResourceScreens";
import { SchemaForm } from "./SchemaForm";
import { Button, Card, EmptyState, ErrorState, Heading, Loading, Notice, StatusPill, Switch } from "./ui";

type Json = Record<string, unknown>;
type Section = { id: number; type: string; position: number; data: Json; isVisible: boolean };
type Page = {
  id: number;
  key: string;
  title: string;
  slug: string;
  seoTitle?: string;
  seoDescription?: string;
  ogMedia?: MediaBrief;
  robotsNoindex: boolean;
  status: string;
  sections: Section[];
  media: Record<string, MediaBrief>;
};
type PageRow = { id: number; key: string; title: string; slug: string; status: string; robotsNoindex: boolean; sections: number };
type Blocks = Record<string, { label: string; schema: JsonSchema }>;
type Forms = Record<string, { label: string; schema: JsonSchema }>;

const SUMMARY_KEYS = ["headline", "title", "heading", "label", "text", "question", "name", "value"];
function summaryOf(value: unknown): string {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const record = value as Json;
    for (const key of SUMMARY_KEYS) {
      const candidate = record[key];
      if (typeof candidate === "string" && candidate.trim()) return candidate.length > 70 ? `${candidate.slice(0, 67)}…` : candidate;
    }
    for (const nested of Object.values(record)) {
      const found = summaryOf(nested);
      if (found) return found;
    }
  }
  if (Array.isArray(value)) for (const item of value) {
    const found = summaryOf(item);
    if (found) return found;
  }
  return "";
}

const typeLabel = (type: string, blocks?: Blocks) => SECTION_LABELS[type] ?? blocks?.[type]?.label ?? type;

// ============================================================ list of pages

export function PagesList() {
  const { data, error, loading, reload } = useApi<PageRow[]>("/admin/pages");
  return (
    <>
      <Heading title="Page content" sub="Every page of the website is made of sections. Open a page to change its text and photos, or to add, hide and move sections." />
      {loading && !data && <Loading />}
      {error && <ErrorState problem={error} retry={reload} />}
      {data && (
        <Card>
          <table className="tbl">
            <thead>
              <tr>
                <th>Page</th>
                <th>Address</th>
                <th>Sections</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.map((page) => (
                <tr key={page.id}>
                  <td>
                    <Link href={`/admin/pages/${page.id}`}>{page.title}</Link>
                  </td>
                  <td>
                    <code>/{page.slug}</code>
                  </td>
                  <td>{page.sections}</td>
                  <td>
                    <StatusPill status={page.status} />
                    {page.robotsNoindex && <span className="st gr"> hidden from Google</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );
}

// ============================================================ one page

export function PageEditor({ id }: { id: string }) {
  const page = useApi<Page>(`/admin/pages/${id}`);
  const forms = useApi<Forms>("/admin/forms/schema");
  const blocks = useApi<Blocks>("/admin/blocks/schema");
  const pages = useApi<PageRow[]>("/admin/pages");
  const [version, setVersion] = useState(0);

  const error = page.error ?? forms.error ?? blocks.error;
  if (error) return <ErrorState problem={error} retry={() => { page.reload(); forms.reload(); blocks.reload(); }} />;
  const formSchema = forms.data?.page?.schema;
  if (!page.data || !formSchema || !blocks.data) return <Loading />;

  return (
    <PageBody
      key={`${id}-${version}`}
      initial={page.data}
      formSchema={formSchema}
      blocks={blocks.data}
      knownPaths={["/", ...(pages.data ?? []).filter((p) => p.slug).map((p) => `/${p.slug}`)]}
      onRestored={() => {
        page.reload();
        setVersion((v) => v + 1);
      }}
    />
  );
}

function pageToForm(page: Page): Json {
  return {
    title: page.title,
    ...(page.slug ? { slug: page.slug } : {}),
    ...(page.seoTitle ? { seoTitle: page.seoTitle } : {}),
    ...(page.seoDescription ? { seoDescription: page.seoDescription } : {}),
    ...(page.ogMedia ? { ogMediaId: page.ogMedia.id } : {}),
    robotsNoindex: page.robotsNoindex,
    status: page.status,
  };
}

function PageBody({ initial, formSchema, blocks, knownPaths, onRestored }: { initial: Page; formSchema: JsonSchema; blocks: Blocks; knownPaths: string[]; onRestored: () => void }) {
  const feedback = useFeedback();
  const [page, setPage] = useState<Page>(initial);
  const [form, setForm] = useState<Json>(() => {
    rememberBriefs([initial.ogMedia, ...Object.values(initial.media)]);
    return pageToForm(initial);
  });
  const [saved, setSaved] = useState(() => JSON.stringify(prune(pageToForm(initial)) ?? {}));
  const [submitted, setSubmitted] = useState(false);
  const [serverProblems, setServerProblems] = useState<Problems>({});
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const [saves, setSaves] = useState(0);

  const dirty = JSON.stringify(prune(form) ?? {}) !== saved;
  useDirty(dirty && editing === null);
  const clientProblems = useMemo(() => validate(formSchema, form), [formSchema, form]);
  const problems = { ...(submitted ? clientProblems : {}), ...serverProblems };

  /** Every change to the sections answers with the whole page: take it over. */
  const take = (next: Page) => {
    rememberBriefs([next.ogMedia, ...Object.values(next.media)]);
    setPage(next);
    setSaves((n) => n + 1);
  };

  async function savePage() {
    setSubmitted(true);
    setServerProblems({});
    if (Object.keys(clientProblems).length > 0) return feedback.error("Please check the fields marked in red.");
    setBusy(true);
    try {
      const next = await api.put<Page>(`/admin/pages/${page.id}`, prune(form) ?? {});
      take(next);
      const fresh = pageToForm(next);
      setForm(fresh);
      setSaved(JSON.stringify(prune(fresh) ?? {}));
      setSubmitted(false);
      feedback.ok("Page details saved.");
    } catch (problem) {
      if (problem instanceof ApiProblem) {
        setServerProblems(problem.fieldMap());
        feedback.error(problem.message);
      }
    } finally {
      setBusy(false);
    }
  }

  async function run<T>(work: () => Promise<T>, done?: string): Promise<T | undefined> {
    try {
      const result = await work();
      if (done) feedback.ok(done);
      return result;
    } catch (problem) {
      feedback.error(problem instanceof ApiProblem ? problem.message : "Something went wrong.");
      return undefined;
    }
  }

  const sections = page.sections;
  const move = async (index: number, delta: number) => {
    const ids = sections.map((s) => s.id);
    const target = index + delta;
    if (target < 0 || target >= ids.length) return;
    [ids[index], ids[target]] = [ids[target], ids[index]];
    const next = await run(() => api.post<Page>(`/admin/pages/${page.id}/sections/reorder`, { ids }));
    if (next) take(next);
  };
  const toggle = async (section: Section) => {
    const next = await run(() => api.put<Page>(`/admin/pages/${page.id}/sections/${section.id}`, { isVisible: !section.isVisible }), section.isVisible ? "Hidden from the page." : "Shown on the page.");
    if (next) take(next);
  };
  const duplicate = async (section: Section) => {
    const next = await run(() => api.post<Page>(`/admin/pages/${page.id}/sections/${section.id}/duplicate`), "Section copied.");
    if (next) take(next);
  };
  const remove = async (section: Section) => {
    const sure = await feedback.confirm({ title: "Delete this section?", message: <>“{typeLabel(section.type, blocks)}” disappears from the page. You can bring it back from the page history.</>, confirmLabel: "Delete", danger: true });
    if (!sure) return;
    const next = await run(() => api.delete<Page>(`/admin/pages/${page.id}/sections/${section.id}`), "Section deleted.");
    if (next) take(next);
  };

  // search engine checks for the whole page
  const visible = sections.filter((s) => s.isVisible);
  const h1Count = visible.filter((s) => s.type === "hero" || s.type === "page_header").length;
  const photosWithoutText = Object.values(page.media).filter((m) => m.kind === "image" && !m.altText.trim()).length;
  const checks = seoChecks({ title: (form.seoTitle as string) || (form.title as string) || "", description: (form.seoDescription as string) ?? "", h1Count, photosWithoutText, pageData: sections.map((s) => s.data), knownPaths });

  return (
    <>
      <Heading
        title={`Page: ${page.title}`}
        sub={
          <>
            <StatusPill status={page.status} /> <code>/{page.slug}</code> {dirty && <span className="st dr">Unsaved page details</span>}
          </>
        }
        actions={
          <>
            <Link className="btn btn-ghost btn-sm" href="/admin/pages">
              ← All pages
            </Link>
            <PreviewButton kind="page" id={page.id} unsaved={dirty} />
            {page.status === "published" && (
              <a className="btn btn-ghost btn-sm" href={`/${page.slug}`} target="_blank" rel="noopener">
                View on website
              </a>
            )}
          </>
        }
      />
      <div className="adm-split">
        <div>
          <Card title="Sections" actions={<Button onClick={() => setEditing("new")} disabled={editing !== null}>+ Add a section</Button>}>
            <p className="fhelp">The page shows its sections from top to bottom. Use the arrows to move them, or “Hide” to take one off the page without deleting it.</p>
            {editing === "new" && (
              <NewSection
                pageId={page.id}
                blocks={blocks}
                knownPaths={knownPaths}
                onCancel={() => setEditing(null)}
                onSaved={(next) => {
                  take(next);
                  setEditing(null);
                  feedback.ok("Section added.");
                }}
              />
            )}
            {sections.length === 0 && editing !== "new" && <EmptyState>This page has no sections yet.</EmptyState>}
            <ol className="seclist">
              {sections.map((section, index) => (
                <li key={section.id} className={cx("secrow", !section.isVisible && "secrow-off")}>
                  <div className="sechead">
                    <div className="sectitle">
                      <b>{typeLabel(section.type, blocks)}</b>
                      <small>{summaryOf(section.data) || "—"}</small>
                      {!section.isVisible && <span className="st gr">Hidden</span>}
                    </div>
                    <span className="rowbtns">
                      <button type="button" className="tbtn" aria-label={`Move ${typeLabel(section.type, blocks)} up`} disabled={index === 0 || editing !== null} onClick={() => move(index, -1)}>
                        ↑
                      </button>
                      <button type="button" className="tbtn" aria-label={`Move ${typeLabel(section.type, blocks)} down`} disabled={index === sections.length - 1 || editing !== null} onClick={() => move(index, 1)}>
                        ↓
                      </button>
                      <button type="button" className="tbtn" aria-label={section.isVisible ? "Hide this section" : "Show this section"} aria-pressed={!section.isVisible} disabled={editing !== null} onClick={() => toggle(section)}>
                        {section.isVisible ? "Hide" : "Show"}
                      </button>
                      <button type="button" className="tbtn" aria-label="Copy this section" disabled={editing !== null} onClick={() => duplicate(section)}>
                        Copy
                      </button>
                      <button type="button" className="tbtn" aria-label={`Edit ${typeLabel(section.type, blocks)}`} disabled={editing !== null} onClick={() => setEditing(section.id)}>
                        Edit
                      </button>
                      <button type="button" className="tbtn tbtn-danger" aria-label="Delete this section" disabled={editing !== null} onClick={() => remove(section)}>
                        ×
                      </button>
                    </span>
                  </div>
                  {editing === section.id && (
                    <SectionForm
                      key={section.id}
                      title={typeLabel(section.type, blocks)}
                      blockSchema={blocks[section.type]?.schema}
                      initial={section.data}
                      knownPaths={knownPaths}
                      save={(data) => api.put<Page>(`/admin/pages/${page.id}/sections/${section.id}`, { data })}
                      onCancel={() => setEditing(null)}
                      onSaved={(next) => {
                        take(next);
                        setEditing(null);
                        feedback.ok("Section saved. The website shows it in a moment.");
                      }}
                    />
                  )}
                </li>
              ))}
            </ol>
          </Card>
        </div>
        <div>
          <Card title="Page details">
            <SchemaForm schema={formSchema} value={form} onChange={setForm} problems={problems} exclude={page.key === "home" ? ["slug", "status"] : undefined} paths={knownPaths} />
            <div className="btnrow">
              <Button onClick={savePage} busy={busy} disabled={!dirty}>
                Save page details
              </Button>
            </div>
          </Card>
          <Card title="Search engine checks">
            <ul className="seochecks" aria-label="Search engine checks">
              {checks.map((check) => (
                <li key={check.id} className={`seo-${check.status}`}>
                  <span aria-hidden="true">{check.status === "ok" ? "✓" : check.status === "warn" ? "!" : "✕"}</span> {check.label}
                  {check.hint && <small> — {check.hint}</small>}
                </li>
              ))}
            </ul>
          </Card>
          <HistoryCard entity="page" entityId={page.id} onRestored={onRestored} dirty={dirty} version={saves} />
        </div>
      </div>
    </>
  );
}

// ============================================================ editing one section

function SectionForm({
  title,
  blockSchema,
  initial,
  knownPaths,
  save,
  onCancel,
  onSaved,
}: {
  title: string;
  blockSchema: JsonSchema | undefined;
  initial: Json;
  knownPaths: string[];
  save: (data: Json) => Promise<Page>;
  onCancel: () => void;
  onSaved: (page: Page) => void;
}) {
  const feedback = useFeedback();
  const [data, setData] = useState<Json>(initial);
  const [submitted, setSubmitted] = useState(false);
  const [serverProblems, setServerProblems] = useState<Problems>({});
  const [busy, setBusy] = useState(false);
  const dirty = JSON.stringify(prune(data) ?? {}) !== JSON.stringify(prune(initial) ?? {});
  useDirty(dirty);
  const kinds = useMemo(() => (blockSchema ? variantKinds(blockSchema) : []), [blockSchema]);
  const clientProblems = useMemo(() => (blockSchema ? validate(blockSchema, data) : {}), [blockSchema, data]);
  const problems = { ...(submitted ? clientProblems : {}), ...serverProblems };

  if (!blockSchema) return <Notice kind="error">This kind of section cannot be edited here.</Notice>;

  async function submit() {
    setSubmitted(true);
    setServerProblems({});
    if (Object.keys(clientProblems).length > 0) {
      feedback.error("Please check the fields marked in red.");
      window.setTimeout(() => document.querySelector(".has-error, .ferr")?.scrollIntoView({ block: "center", behavior: "smooth" }), 0);
      return;
    }
    setBusy(true);
    try {
      onSaved(await save((prune(data) ?? {}) as Json));
    } catch (problem) {
      if (problem instanceof ApiProblem) {
        const mapped: Problems = {};
        for (const [field, message] of Object.entries(problem.fieldMap())) mapped[normalizeServerPath(field, kinds)] = message;
        setServerProblems(mapped);
        feedback.error(Object.keys(mapped).length > 0 ? "Please check the fields marked in red." : problem.message);
      } else feedback.error("Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="secedit" role="group" aria-label={`Edit ${title}`}>
      <SchemaForm schema={blockSchema} value={data} onChange={setData} problems={problems} paths={knownPaths} />
      <div className="btnrow">
        <Button onClick={submit} busy={busy}>
          Save section
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

function NewSection({ pageId, blocks, knownPaths, onCancel, onSaved }: { pageId: number; blocks: Blocks; knownPaths: string[]; onCancel: () => void; onSaved: (page: Page) => void }) {
  const types = Object.keys(blocks);
  const [type, setType] = useState("");
  const [visible, setVisible] = useState(true);
  const chosen = type ? blocks[type] : undefined;

  return (
    <div className="secedit">
      <h3>Add a section</h3>
      <div className="afield">
        <label htmlFor="new-section-type">What do you want to add?</label>
        <select id="new-section-type" value={type} onChange={(event) => setType(event.target.value)}>
          <option value="">Choose a kind of section…</option>
          {types.map((key) => (
            <option key={key} value={key}>
              {typeLabel(key, blocks)}
            </option>
          ))}
        </select>
      </div>
      {chosen ? (
        <>
          <Switch label="Show it on the page" checked={visible} onChange={setVisible} />
          <SectionForm
            key={type}
            title={typeLabel(type, blocks)}
            blockSchema={chosen.schema}
            initial={initialValue(chosen.schema, chosen.schema) as Json}
            knownPaths={knownPaths}
            save={(data) => api.post<Page>(`/admin/pages/${pageId}/sections`, { type, data, isVisible: visible })}
            onCancel={onCancel}
            onSaved={onSaved}
          />
        </>
      ) : (
        <div className="btnrow">
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      )}
    </div>
  );
}
