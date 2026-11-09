import Link from "next/link";
import { useState, type ComponentType, type ReactNode } from "react";
import { api } from "@/lib/admin/api";
import { formatDate } from "@/lib/admin/format";
import { enumLabel } from "@/lib/admin/labels";
import { rememberBriefs } from "@/lib/admin/media-cache";
import { ApiProblem } from "@/lib/admin/problem";
import type { MediaBrief, Role } from "@/lib/admin/types";
import { useFeedback } from "./feedback";
import { Thumb, useMediaPicker } from "./media";
import { Button, StatusPill } from "./ui";

export type Json = Record<string, unknown>;
export type Item = { id: number } & Json;

export type Card = { title: string; fields: string[]; seo?: boolean; actions?: boolean };
export type SaveAction = { label: string; patch?: Json; primary?: boolean };
export type Column = { header: string; cell: (item: Item, base: string) => ReactNode };

export type ResourceConfig = {
  /** Key of the form in /admin/forms/schema. */
  formKey: string;
  title: string;
  sub: string;
  singular: string;
  api: string;
  route: string;
  /** Fields shown in the main column (the rest go in the cards on the right). */
  main: string[];
  cards: Card[];
  columns: Column[];
  /** What the API returns -> what the form edits (the same shape the API accepts). */
  toForm: (item: Item) => Json;
  /** A new, empty item (on top of what the schema says). */
  blank?: Json;
  publicPath?: (form: Json, item?: Item) => string | undefined;
  /** Which kind of draft preview link the editor can open (news items and pages have one). */
  previewKind?: "news";
  actions?: (form: Json) => SaveAction[];
  /** Roles allowed to add / delete (default: any staff member). */
  createRole?: Role;
  deleteRole?: Role;
  reorder?: boolean;
  filters?: { status?: boolean; search?: boolean };
  history?: string;
  /** Extra buttons next to "Add" on the list screen. */
  listActions?: ComponentType<{ reload: () => void }>;
};

const text = (value: unknown): string => (typeof value === "string" ? value : value === undefined || value === null ? "" : String(value));
const brief = (value: unknown): MediaBrief | undefined => (value && typeof value === "object" ? (value as MediaBrief) : undefined);

function pick(item: Item, keys: string[]): Json {
  const out: Json = {};
  for (const key of keys) if (item[key] !== undefined && item[key] !== null) out[key] = item[key];
  return out;
}

function titleLink(field: string): Column["cell"] {
  return function TitleCell(item, base) {
    return <Link href={`${base}/${item.id}`}>{text(item[field]) || "(no title)"}</Link>;
  };
}

export const NEWS: ResourceConfig = {
  formKey: "news",
  title: "News & notices",
  sub: "Announcements shown on the website. Publish a notice and it appears within seconds.",
  singular: "news item",
  api: "/admin/news",
  route: "/admin/news",
  main: ["title", "category", "summary", "body", "attachments"],
  cards: [
    { title: "Publish", fields: ["status", "isPinned", "publishedAt"], actions: true },
    { title: "Cover photo", fields: ["coverMediaId"] },
    { title: "How it looks on Google", fields: ["slug", "seoTitle", "seoDescription"], seo: true },
  ],
  filters: { status: true, search: true },
  history: "news",
  columns: [
    { header: "Title", cell: titleLink("title") },
    { header: "Category", cell: (item) => enumLabel(item.category) },
    { header: "Date", cell: (item) => formatDate(text(item.publishedAt)) },
    { header: "Status", cell: (item) => <StatusPill status={text(item.status)} label={item.isPinned ? `${text(item.status) === "published" ? "Published" : "Draft"} · pinned` : undefined} /> },
  ],
  toForm: (item) => {
    const attachments = (Array.isArray(item.attachments) ? item.attachments : []) as { media?: MediaBrief; label: string }[];
    rememberBriefs([brief(item.coverMedia), ...attachments.map((a) => a.media)]);
    return {
      ...pick(item, ["title", "slug", "category", "summary", "body", "publishedAt", "isPinned", "status", "seoTitle", "seoDescription"]),
      ...(brief(item.coverMedia) ? { coverMediaId: brief(item.coverMedia)!.id } : {}),
      attachments: attachments.filter((a) => a.media).map((a) => ({ mediaId: a.media!.id, label: a.label })),
    };
  },
  blank: { status: "draft", isPinned: false },
  publicPath: (form, item) => (text(form.slug) || text(item?.slug) ? `/news/${text(form.slug) || text(item?.slug)}` : "/news/your-title"),
  previewKind: "news",
  actions: (form) => (form.status === "published" ? [{ label: "Save changes", primary: true }, { label: "Unpublish", patch: { status: "draft" } }] : [{ label: "Save draft" }, { label: "Publish", patch: { status: "published" }, primary: true }]),
};

export const ACTIVITIES: ResourceConfig = {
  formKey: "activity",
  title: "Activities",
  sub: "NSS, Leo Club, cultural and sports activities with their photos.",
  singular: "activity",
  api: "/admin/activities",
  route: "/admin/activities",
  main: ["title", "group", "year", "summary", "photos"],
  cards: [
    { title: "Publish", fields: ["status", "showOnHome", "sortOrder"], actions: true },
    { title: "Cover photo", fields: ["coverMediaId"] },
  ],
  filters: { status: true },
  history: "activity",
  reorder: true,
  columns: [
    { header: "Title", cell: titleLink("title") },
    { header: "Group", cell: (item) => enumLabel(item.group) },
    { header: "Year", cell: (item) => text(item.year) || "—" },
    { header: "Photos", cell: (item) => String(Array.isArray(item.photos) ? item.photos.length : 0) },
    { header: "Status", cell: (item) => <StatusPill status={text(item.status)} /> },
  ],
  toForm: (item) => {
    const photos = (Array.isArray(item.photos) ? item.photos : []) as { media?: MediaBrief; caption?: string }[];
    rememberBriefs([brief(item.coverMedia), ...photos.map((p) => p.media)]);
    return {
      ...pick(item, ["title", "slug", "group", "year", "summary", "showOnHome", "status", "sortOrder"]),
      ...(brief(item.coverMedia) ? { coverMediaId: brief(item.coverMedia)!.id } : {}),
      photos: photos.filter((p) => p.media).map((p) => ({ mediaId: p.media!.id, ...(p.caption ? { caption: p.caption } : {}) })),
    };
  },
  blank: { status: "draft", showOnHome: false, sortOrder: 0 },
  actions: NEWS.actions,
};

const GALLERY_CATEGORIES = ["campus", "leo", "nss", "other"];

/** Add many photos to the gallery in one go: choose or upload them, and they are all filed under one category. */
function GalleryBulkAdd({ reload }: { reload: () => void }) {
  const picker = useMediaPicker();
  const feedback = useFeedback();
  const [category, setCategory] = useState("campus");
  const [busy, setBusy] = useState(false);

  async function addPhotos() {
    const photos = await picker.pickMany("image");
    if (photos.length === 0) return;
    setBusy(true);
    let added = 0;
    let failure = "";
    for (const photo of photos) {
      try {
        await api.post("/admin/gallery", { mediaId: photo.id, category, caption: "" });
        added += 1;
      } catch (problem) {
        failure = problem instanceof ApiProblem ? problem.message : "Something went wrong.";
      }
    }
    setBusy(false);
    if (added > 0) feedback.ok(`${added} photo${added === 1 ? "" : "s"} added to the gallery.`);
    if (failure) feedback.error(failure);
    reload();
  }

  return (
    <>
      <select value={category} onChange={(event) => setCategory(event.target.value)} aria-label="Category for the new photos" className="aselect">
        {GALLERY_CATEGORIES.map((value) => (
          <option key={value} value={value}>
            {enumLabel(value)}
          </option>
        ))}
      </select>
      <Button onClick={addPhotos} busy={busy}>
        Add photos
      </Button>
    </>
  );
}

export const GALLERY: ResourceConfig = {
  formKey: "gallery",
  title: "Gallery",
  sub: "Photos and YouTube videos shown on the Gallery page. Drag order with the arrows.",
  singular: "gallery item",
  api: "/admin/gallery",
  route: "/admin/gallery",
  main: ["kind", "mediaId", "youtubeId", "category", "caption"],
  cards: [{ title: "Show on the website", fields: ["isPublished"], actions: true }],
  reorder: true,
  listActions: GalleryBulkAdd,
  columns: [
    { header: "Photo", cell: (item, base) => <Link href={`${base}/${item.id}`}>{brief(item.media) ? <Thumb item={brief(item.media)!} /> : <span className="thumb thumb-pdf">▶</span>}</Link> },
    { header: "Caption", cell: (item, base) => <Link href={`${base}/${item.id}`}>{text(item.caption) || (item.kind === "video" ? `Video ${text(item.youtubeId)}` : "(no caption)")}</Link> },
    { header: "Category", cell: (item) => enumLabel(item.category) },
    { header: "Shown", cell: (item) => <StatusPill status={item.isPublished ? "published" : "hidden"} label={item.isPublished ? "Shown" : "Hidden"} /> },
  ],
  toForm: (item) => {
    rememberBriefs([brief(item.media)]);
    return { ...pick(item, ["kind", "youtubeId", "category", "caption", "sortOrder", "isPublished"]), ...(brief(item.media) ? { mediaId: brief(item.media)!.id } : {}) };
  },
  blank: { kind: "photo", category: "campus", isPublished: true, sortOrder: 0 },
};

export const DEPARTMENTS: ResourceConfig = {
  formKey: "department",
  title: "Departments",
  sub: "The departments that courses and teachers belong to.",
  singular: "department",
  api: "/admin/departments",
  route: "/admin/departments",
  main: ["name", "description"],
  cards: [{ title: "Save", fields: ["sortOrder"], actions: true }],
  createRole: "super_admin",
  deleteRole: "super_admin",
  reorder: true,
  columns: [{ header: "Name", cell: titleLink("name") }, { header: "Address", cell: (item) => <code>{text(item.slug)}</code> }],
  toForm: (item) => pick(item, ["name", "slug", "description", "sortOrder"]),
  blank: { sortOrder: 0 },
};

export const COURSES: ResourceConfig = {
  formKey: "course",
  title: "Courses",
  sub: "The programs the college offers. Editors change the details; only a super admin adds or removes a course.",
  singular: "course",
  api: "/admin/courses",
  route: "/admin/courses",
  main: ["name", "tab", "departmentId", "durationYears", "affiliation", "summary", "description", "subjects", "eligibility", "seats", "fees"],
  cards: [
    { title: "Show on the website", fields: ["isPublished", "sortOrder"], actions: true },
    { title: "Syllabus", fields: ["syllabusMediaId"] },
    { title: "Cover photo", fields: ["coverMediaId"] },
    { title: "How it looks on Google", fields: ["slug", "seoTitle", "seoDescription"], seo: true },
  ],
  createRole: "super_admin",
  deleteRole: "super_admin",
  reorder: true,
  columns: [
    { header: "Course", cell: titleLink("name") },
    { header: "Department", cell: (item) => text(item.departmentName) },
    { header: "Years", cell: (item) => text(item.durationYears) },
    { header: "Shown", cell: (item) => <StatusPill status={item.isPublished ? "published" : "hidden"} label={item.isPublished ? "Shown" : "Hidden"} /> },
  ],
  toForm: (item) => {
    rememberBriefs([brief(item.syllabus), brief(item.coverMedia)]);
    return {
      ...pick(item, ["departmentId", "name", "tab", "slug", "durationYears", "affiliation", "summary", "description", "subjects", "eligibility", "seats", "fees", "sortOrder", "isPublished", "seoTitle", "seoDescription"]),
      ...(brief(item.syllabus) ? { syllabusMediaId: brief(item.syllabus)!.id } : {}),
      ...(brief(item.coverMedia) ? { coverMediaId: brief(item.coverMedia)!.id } : {}),
    };
  },
  blank: { isPublished: true, sortOrder: 0, durationYears: 3, subjects: [] },
  publicPath: (form, item) => `/courses/${text(form.slug) || text(item?.slug) || "course-name"}`,
};

export const FACULTY: ResourceConfig = {
  formKey: "faculty",
  title: "Faculty",
  sub: "The teachers shown on the Faculty page.",
  singular: "faculty member",
  api: "/admin/faculty",
  route: "/admin/faculty",
  main: ["name", "designation", "qualification", "departmentId", "bio"],
  cards: [
    { title: "Show on the website", fields: ["isActive", "sortOrder"], actions: true },
    { title: "Photo", fields: ["photoMediaId"] },
  ],
  reorder: true,
  columns: [
    { header: "Name", cell: titleLink("name") },
    { header: "Designation", cell: (item) => text(item.designation) },
    { header: "Department", cell: (item) => text(item.departmentName) },
    { header: "Shown", cell: (item) => <StatusPill status={item.isActive ? "published" : "hidden"} label={item.isActive ? "Shown" : "Hidden"} /> },
  ],
  toForm: (item) => {
    rememberBriefs([brief(item.photo)]);
    return { ...pick(item, ["departmentId", "name", "designation", "qualification", "bio", "sortOrder", "isActive"]), ...(brief(item.photo) ? { photoMediaId: brief(item.photo)!.id } : {}) };
  },
  blank: { isActive: true, sortOrder: 0 },
};
