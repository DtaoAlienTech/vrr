// A small shared memory of the photos and files the screens have seen, so a form can show a
// thumbnail for "photo number 12" without asking the server again each time.
import { api } from "./api.ts";
import type { MediaBrief } from "./types.ts";

const briefs = new Map<number, MediaBrief>();
const loading = new Set<number>();
const listeners = new Set<() => void>();

// Tell the screens a moment later: this can be called while a screen is being drawn, and a screen
// must not be updated in the middle of drawing another.
const notify = () => queueMicrotask(() => listeners.forEach((listener) => listener()));

export function rememberBrief(brief: MediaBrief | null | undefined): void {
  if (!brief) return;
  briefs.set(brief.id, brief);
  notify();
}

export function rememberBriefs(items: Iterable<MediaBrief | null | undefined>): void {
  for (const item of items) if (item) briefs.set(item.id, item);
  notify();
}

export const peekBrief = (id: number | null | undefined): MediaBrief | undefined => (id ? briefs.get(id) : undefined);

export function subscribeBriefs(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Fetches a file's details if they are not known yet (the screens update by themselves). */
export function loadBrief(id: number): void {
  if (briefs.has(id) || loading.has(id)) return;
  loading.add(id);
  api
    .get<MediaBrief>(`/admin/media/${id}`)
    .then(rememberBrief)
    .catch(() => undefined)
    .finally(() => loading.delete(id));
}

/** Every photo/file id mentioned in a block of data ({"mediaId": 12} pointers and *MediaId fields). */
export function mediaIdsIn(value: unknown, found = new Set<number>()): Set<number> {
  if (Array.isArray(value)) value.forEach((item) => mediaIdsIn(item, found));
  else if (value !== null && typeof value === "object") {
    for (const [key, item] of Object.entries(value)) {
      if ((key === "mediaId" || key.endsWith("MediaId")) && typeof item === "number") found.add(item);
      else mediaIdsIn(item, found);
    }
  }
  return found;
}
