"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, useSyncExternalStore, type DragEvent, type ReactNode } from "react";
import { api, uploadMedia, withQuery, type Upload } from "@/lib/admin/api";
import { formatBytes, formatDate } from "@/lib/admin/format";
import { useApi } from "@/lib/admin/hooks";
import { loadBrief, peekBrief, rememberBrief, subscribeBriefs } from "@/lib/admin/media-cache";
import { ApiProblem } from "@/lib/admin/problem";
import type { MediaItem, Usage } from "@/lib/admin/types";
import { cx } from "@/lib/cx";
import { useFeedback } from "./feedback";
import { Modal } from "./Modal";
import { Button, EmptyState, ErrorState, Field, Loading, Notice } from "./ui";

export type PickKind = "image" | "pdf";

// ---------------------------------------------------------------- the picker used by every form

type Picker = {
  pick: (kind: PickKind) => Promise<MediaItem | null>;
  /** Choose and/or upload several files at once. */
  pickMany: (kind: PickKind) => Promise<MediaItem[]>;
};
const PickerContext = createContext<Picker | null>(null);

type Request = { kind: PickKind; many: boolean; resolve: (items: MediaItem[]) => void };

export function MediaPickerProvider({ children }: { children: ReactNode }) {
  const [request, setRequest] = useState<Request | null>(null);
  const picker = useMemo<Picker>(
    () => ({
      pick: (kind) => new Promise((resolve) => setRequest({ kind, many: false, resolve: (items) => resolve(items[0] ?? null) })),
      pickMany: (kind) => new Promise((resolve) => setRequest({ kind, many: true, resolve })),
    }),
    [],
  );
  const finish = (items: MediaItem[]) => {
    request?.resolve(items);
    setRequest(null);
  };
  return (
    <PickerContext.Provider value={picker}>
      {children}
      <Modal open={request !== null} onClose={() => finish([])} title={request?.many ? "Choose photos" : request?.kind === "pdf" ? "Choose a PDF file" : "Choose a photo"} wide>
        {request && <MediaBrowser kind={request.kind} onPick={request.many ? undefined : (item) => finish([item])} onPickMany={request.many ? finish : undefined} />}
      </Modal>
    </PickerContext.Provider>
  );
}

export function useMediaPicker(): Picker {
  const picker = useContext(PickerContext);
  if (!picker) throw new Error("useMediaPicker needs a MediaPickerProvider");
  return picker;
}

/** A photo's thumbnail details, from the shared memory (fetched once if not known yet). */
export function useBrief(id: number | null | undefined) {
  const brief = useSyncExternalStore(subscribeBriefs, () => peekBrief(id), () => undefined);
  useEffect(() => {
    if (id) loadBrief(id);
  }, [id]);
  return brief;
}

export function Thumb({ item, className }: { item: Pick<MediaItem, "kind" | "thumbUrl" | "altText" | "originalFilename">; className?: string }) {
  if (item.kind === "pdf") {
    return (
      <span className={cx("thumb thumb-pdf", className)} aria-hidden="true">
        PDF
      </span>
    );
  }
  return <img className={cx("thumb", className)} src={item.thumbUrl} alt="" loading="lazy" />;
}

// ---------------------------------------------------------------- uploading

type Row = {
  id: number;
  file: File;
  alt: string;
  crop: boolean;
  preview: string | null;
  status: "ready" | "uploading" | "done" | "error";
  progress: number;
  error?: string;
};

const ACCEPT_ALL = "image/jpeg,image/png,image/webp,application/pdf,.jpg,.jpeg,.png,.webp,.pdf";
const MAX_BYTES = 10 * 1024 * 1024;

function problemWith(file: File, kind?: PickKind): string | undefined {
  const type = file.type;
  const isImage = ["image/jpeg", "image/png", "image/webp"].includes(type);
  const isPdf = type === "application/pdf";
  if (!isImage && !isPdf) return "Only JPEG, PNG or WebP photos and PDF files can be uploaded.";
  if (kind === "image" && !isImage) return "Choose a photo here (JPEG, PNG or WebP).";
  if (kind === "pdf" && !isPdf) return "Choose a PDF file here.";
  if (file.size > MAX_BYTES) return `This file is ${formatBytes(file.size)}. The limit is 10 MB.`;
  return undefined;
}

export function UploadPanel({ kind, onUploaded }: { kind?: PickKind; onUploaded: (item: MediaItem) => void }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [sameAlt, setSameAlt] = useState("");
  const [busy, setBusy] = useState(false);
  const [rejected, setRejected] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);
  const nextId = useRef(1);
  const input = useRef<HTMLInputElement>(null);
  const running = useRef<Upload | null>(null);

  useEffect(
    () => () => {
      running.current?.abort();
    },
    [],
  );

  const add = (files: FileList | File[]) => {
    const accepted: Row[] = [];
    const bad: string[] = [];
    for (const file of Array.from(files)) {
      const problem = problemWith(file, kind);
      if (problem) bad.push(`${file.name}: ${problem}`);
      else {
        accepted.push({
          id: nextId.current++,
          file,
          alt: "",
          crop: false,
          preview: file.type.startsWith("image/") ? URL.createObjectURL(file) : null,
          status: "ready",
          progress: 0,
        });
      }
    }
    setRejected(bad);
    setRows((current) => [...current, ...accepted]);
  };

  const update = (id: number, patch: Partial<Row>) => setRows((current) => current.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  const remove = (id: number) =>
    setRows((current) => {
      const gone = current.find((row) => row.id === id);
      if (gone?.preview) URL.revokeObjectURL(gone.preview);
      return current.filter((row) => row.id !== id);
    });

  const waiting = rows.filter((row) => row.status === "ready" || row.status === "error");
  const missingText = waiting.filter((row) => row.file.type.startsWith("image/") && !row.alt.trim());

  async function startAll() {
    setBusy(true);
    for (const row of waiting) {
      update(row.id, { status: "uploading", progress: 0, error: undefined });
      const upload = uploadMedia(row.file, row.alt, row.crop, (fraction) => update(row.id, { progress: fraction }));
      running.current = upload;
      try {
        const item = await upload.promise;
        rememberBrief(item);
        update(row.id, { status: "done", progress: 1 });
        onUploaded(item);
      } catch (error) {
        update(row.id, { status: "error", error: error instanceof ApiProblem ? error.message : "The upload did not finish." });
      }
    }
    running.current = null;
    setBusy(false);
  }

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    add(event.dataTransfer.files);
  };

  return (
    <div className="upanel">
      <div
        className={cx("drop", dragging && "drop-on")}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <b>Drop {kind === "pdf" ? "a PDF" : kind === "image" ? "photos" : "photos or PDFs"} here</b>
        <span>or</span>
        <Button variant="ghost" onClick={() => input.current?.click()}>
          Choose files
        </Button>
        <input
          ref={input}
          type="file"
          hidden
          multiple={kind !== "pdf"}
          accept={kind === "pdf" ? "application/pdf,.pdf" : kind === "image" ? "image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp" : ACCEPT_ALL}
          onChange={(event) => {
            if (event.target.files) add(event.target.files);
            event.target.value = "";
          }}
          data-testid="file-input"
        />
        <small>JPEG, PNG, WebP or PDF, up to 10 MB each. Photos are resized automatically and location data is removed.</small>
      </div>

      {rejected.length > 0 && (
        <Notice kind="error">
          {rejected.map((message) => (
            <div key={message}>{message}</div>
          ))}
        </Notice>
      )}

      {rows.length > 0 && (
        <>
          {rows.filter((r) => r.file.type.startsWith("image/") && r.status === "ready").length > 1 && (
            <div className="usame">
              <input
                type="text"
                value={sameAlt}
                onChange={(event) => setSameAlt(event.target.value)}
                placeholder="Same description for all photos, e.g. NSS volunteers at the camp"
                aria-label="Same description for all photos"
              />
              <Button
                variant="ghost"
                disabled={!sameAlt.trim()}
                onClick={() => setRows((current) => current.map((row) => (row.file.type.startsWith("image/") && row.status === "ready" && !row.alt ? { ...row, alt: sameAlt.trim() } : row)))}
              >
                Fill empty
              </Button>
            </div>
          )}
          <ul className="uplist">
            {rows.map((row) => (
              <li key={row.id} className={cx("uprow", `up-${row.status}`)}>
                {row.preview ? <img className="thumb" src={row.preview} alt="" /> : <span className="thumb thumb-pdf">PDF</span>}
                <div className="upinfo">
                  <b>{row.file.name}</b> <small>{formatBytes(row.file.size)}</small>
                  {row.status !== "done" && (
                    <Field label={row.file.type.startsWith("image/") ? "Describe the photo (required)" : "Title (optional)"}>
                      <input
                        type="text"
                        value={row.alt}
                        maxLength={300}
                        disabled={row.status === "uploading"}
                        onChange={(event) => update(row.id, { alt: event.target.value })}
                        placeholder={row.file.type.startsWith("image/") ? "What does the photo show?" : "e.g. Syllabus 2026"}
                      />
                    </Field>
                  )}
                  {row.status === "ready" && row.file.type.startsWith("image/") && (
                    <label className="ucheck">
                      <input type="checkbox" checked={row.crop} onChange={(event) => update(row.id, { crop: event.target.checked })} /> A camera date stamp is printed on the bottom edge: hide it
                    </label>
                  )}
                  {row.status === "uploading" && <progress value={row.progress} max={1} aria-label={`Uploading ${row.file.name}`} />}
                  {row.status === "done" && <span className="st ok">Uploaded</span>}
                  {row.status === "error" && <p className="ferr">{row.error}</p>}
                </div>
                {row.status !== "uploading" && (
                  <button type="button" className="aclose" onClick={() => remove(row.id)} aria-label={`Remove ${row.file.name}`}>
                    ×
                  </button>
                )}
              </li>
            ))}
          </ul>
          {waiting.length > 0 && (
            <div className="btnrow">
              <Button onClick={startAll} busy={busy} disabled={missingText.length > 0}>
                Upload {waiting.length} file{waiting.length === 1 ? "" : "s"}
              </Button>
              {missingText.length > 0 && <small className="fhelp">Describe each photo first ({missingText.length} left). The description helps people who cannot see it, and Google.</small>}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- browsing

const PAGE = 24;

function MediaGrid({
  query,
  onPick,
  onOpen,
  version,
  selected,
  onToggle,
}: {
  query: { kind?: string; q?: string };
  onPick?: (item: MediaItem) => void;
  onOpen?: (item: MediaItem) => void;
  version: number;
  selected?: ReadonlyMap<number, MediaItem>;
  onToggle?: (item: MediaItem) => void;
}) {
  const first = useApi<MediaItem[]>(withQuery("/admin/media", { ...query, limit: PAGE, v: version }));
  const [more, setMore] = useState<MediaItem[]>([]);
  const [done, setDone] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const items = [...(first.data ?? []), ...more];

  async function loadMore() {
    const last = items[items.length - 1];
    if (!last) return;
    setLoadingMore(true);
    try {
      const page = await api.get<MediaItem[]>(withQuery("/admin/media", { ...query, limit: PAGE, before_id: last.id }));
      setMore((current) => [...current, ...page]);
      if (page.length < PAGE) setDone(true);
    } finally {
      setLoadingMore(false);
    }
  }

  if (first.loading && !first.data) return <Loading />;
  if (first.error) return <ErrorState problem={first.error} retry={first.reload} />;
  if (items.length === 0) return <EmptyState>{query.q ? "Nothing found. Try another word." : "No files yet. Use “Upload” to add the first photo."}</EmptyState>;

  return (
    <>
      <ul className="mgrid">
        {items.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              className={cx("mcard", selected?.has(item.id) && "mcard-on")}
              onClick={() => (onToggle ? onToggle(item) : onPick ? onPick(item) : onOpen?.(item))}
              aria-label={`${onPick || onToggle ? "Choose" : "Open"} ${item.originalFilename}`}
              aria-pressed={onToggle ? selected?.has(item.id) === true : undefined}
            >
              <Thumb item={item} />
              <span className="mname">{item.kind === "image" ? item.altText || item.originalFilename : item.altText || item.originalFilename}</span>
              <small>
                {item.kind === "pdf" ? "PDF" : `${item.width}×${item.height}`} · {formatBytes(item.sizeBytes)}
              </small>
            </button>
          </li>
        ))}
      </ul>
      {!done && (first.data?.length ?? 0) >= PAGE && (
        <div className="btnrow">
          <Button variant="ghost" onClick={loadMore} busy={loadingMore}>
            Show more
          </Button>
        </div>
      )}
    </>
  );
}

/** The library: search, filter, upload, and (in the library screen) open a file to edit or delete it. */
export function MediaBrowser({ kind, onPick, onPickMany, manage }: { kind?: PickKind; onPick?: (item: MediaItem) => void; onPickMany?: (items: MediaItem[]) => void; manage?: boolean }) {
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<PickKind | "">("");
  const [showUpload, setShowUpload] = useState(false);
  const [version, setVersion] = useState(0);
  const [open, setOpen] = useState<MediaItem | null>(null);
  const [selected, setSelected] = useState<ReadonlyMap<number, MediaItem>>(new Map());
  const lock = kind ?? (filter || undefined);
  const toggle = (item: MediaItem) =>
    setSelected((current) => {
      const next = new Map(current);
      if (next.has(item.id)) next.delete(item.id);
      else next.set(item.id, item);
      return next;
    });

  useEffect(() => {
    const timer = window.setTimeout(() => setQ(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  return (
    <div className="mbrowser">
      <div className="mtools">
        <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search by description or file name" aria-label="Search files" />
        {!kind && (
          <select value={filter} onChange={(event) => setFilter(event.target.value as PickKind | "")} aria-label="Kind of file">
            <option value="">Photos and PDFs</option>
            <option value="image">Photos only</option>
            <option value="pdf">PDFs only</option>
          </select>
        )}
        <Button variant={showUpload ? "ghost" : "primary"} onClick={() => setShowUpload(!showUpload)}>
          {showUpload ? "Close upload" : "Upload"}
        </Button>
      </div>
      {showUpload && (
        <UploadPanel
          kind={kind}
          onUploaded={(item) => {
            setVersion((v) => v + 1);
            if (onPickMany) setSelected((current) => new Map(current).set(item.id, item)); // uploaded photos are chosen at once
          }}
        />
      )}
      <MediaGrid key={`${lock}-${q}`} query={{ kind: lock, q }} version={version} onPick={onPick} onOpen={manage ? setOpen : undefined} selected={onPickMany ? selected : undefined} onToggle={onPickMany ? toggle : undefined} />
      {onPickMany && (
        <div className="mpickbar">
          <span>{selected.size === 0 ? "Click photos to choose them, or upload new ones." : `${selected.size} photo${selected.size === 1 ? "" : "s"} chosen`}</span>
          <Button disabled={selected.size === 0} onClick={() => onPickMany([...selected.values()])}>
            Add {selected.size || ""} photo{selected.size === 1 ? "" : "s"}
          </Button>
        </div>
      )}
      {manage && <MediaDetails item={open} onClose={() => setOpen(null)} onChanged={() => setVersion((v) => v + 1)} />}
    </div>
  );
}

// ---------------------------------------------------------------- one file: edit, usage, delete

function MediaDetails({ item, onClose, onChanged }: { item: MediaItem | null; onClose: () => void; onChanged: () => void }) {
  return (
    <Modal open={item !== null} onClose={onClose} title={item?.originalFilename ?? "File"} wide>
      {item && <DetailsBody key={item.id} item={item} onClose={onClose} onChanged={onChanged} />}
    </Modal>
  );
}

function DetailsBody({ item, onClose, onChanged }: { item: MediaItem; onClose: () => void; onChanged: () => void }) {
  const feedback = useFeedback();
  const [alt, setAlt] = useState(item.altText);
  const [crop, setCrop] = useState(item.cropBottom);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const usage = useApi<{ usages: Usage[] }>(`/admin/media/${item.id}/usage`);
  const dirty = alt !== item.altText || crop !== item.cropBottom;
  const inUse = (usage.data?.usages.length ?? 0) > 0;

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const updated = await api.patch<MediaItem>(`/admin/media/${item.id}`, { altText: alt.trim() || undefined, cropBottom: crop });
      rememberBrief(updated);
      feedback.ok("Saved. The website shows the change in a moment.");
      onChanged();
      onClose();
    } catch (problem) {
      setError(problem instanceof ApiProblem ? (problem.errors[0]?.message ?? problem.message) : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    const sure = await feedback.confirm({ title: "Delete this file?", message: <>This removes <b>{item.originalFilename}</b> and all its sizes for good.</>, confirmLabel: "Delete", danger: true });
    if (!sure) return;
    try {
      await api.delete(`/admin/media/${item.id}`);
      feedback.ok("Deleted.");
      onChanged();
      onClose();
    } catch (problem) {
      setError(problem instanceof ApiProblem ? problem.message : "Something went wrong.");
      usage.reload();
    }
  }

  return (
    <div className="mdetail">
      <div className="mpreview">
        {item.kind === "image" ? (
          <img src={item.variants.at(-1)?.url ?? item.url} alt={item.altText} />
        ) : (
          <a className="btn btn-ghost" href={item.url} target="_blank" rel="noopener">
            Open the PDF
          </a>
        )}
      </div>
      <div>
        {error && <Notice kind="error">{error}</Notice>}
        <Field label={item.kind === "image" ? "Description of the photo" : "Title"} help="Shown to people who cannot see the picture, and to search engines." htmlFor="media-alt">
          <input id="media-alt" type="text" value={alt} maxLength={300} onChange={(event) => setAlt(event.target.value)} />
        </Field>
        {item.kind === "image" && (
          <label className="ucheck">
            <input type="checkbox" checked={crop} onChange={(event) => setCrop(event.target.checked)} /> Hide a camera date stamp on the bottom edge
          </label>
        )}
        <dl className="minfo">
          <dt>Type</dt>
          <dd>{item.kind === "pdf" ? "PDF document" : `Photo, ${item.width}×${item.height}`}</dd>
          <dt>Size</dt>
          <dd>{formatBytes(item.sizeBytes)}</dd>
          <dt>Uploaded</dt>
          <dd>{formatDate(item.createdAt)}</dd>
          <dt>Address</dt>
          <dd>
            <code>{item.url}</code>
          </dd>
        </dl>
        <h3>Where it is used</h3>
        {usage.loading && <Loading />}
        {usage.data && (inUse ? <ul className="alist">{usage.data.usages.map((u, index) => <li key={`${u.entity}-${u.id}-${index}`}>{u.label}</li>)}</ul> : <p className="fhelp">Not used anywhere yet.</p>)}
        <div className="btnrow">
          <Button onClick={save} busy={busy} disabled={!dirty}>
            Save changes
          </Button>
          <Button variant="danger" onClick={remove} disabled={inUse} title={inUse ? "Remove it from the places above first" : undefined}>
            Delete
          </Button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- the field used inside forms

export function MediaChooser({ id, kind, onChange, optional, label }: { id: number | undefined; kind: PickKind; onChange: (id: number | undefined) => void; optional: boolean; label?: string }) {
  const picker = useMediaPicker();
  const brief = useBrief(id);
  const choose = useCallback(async () => {
    const item = await picker.pick(kind);
    if (item) {
      rememberBrief(item);
      onChange(item.id);
    }
  }, [picker, kind, onChange]);

  return (
    <div className="mchoose">
      {id ? (
        <div className="mchosen">
          {brief ? <Thumb item={brief} /> : <span className="thumb thumb-pdf">…</span>}
          <span className="mchosen-name">{brief ? brief.altText || brief.originalFilename : "Loading…"}</span>
        </div>
      ) : (
        <span className="fhelp">{kind === "pdf" ? "No PDF chosen" : "No photo chosen"}</span>
      )}
      <div className="mchoose-actions">
        <Button variant="ghost" onClick={choose} aria-label={`${id ? "Change" : "Choose"}${label ? ` ${label}` : ""}`}>
          {id ? "Change" : kind === "pdf" ? "Choose a PDF" : "Choose a photo"}
        </Button>
        {id && optional && (
          <Button variant="ghost" onClick={() => onChange(undefined)} aria-label={`Remove${label ? ` ${label}` : ""}`}>
            Remove
          </Button>
        )}
      </div>
    </div>
  );
}
