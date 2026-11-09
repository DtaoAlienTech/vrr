// Old address -> new address. The backend creates these when an editor changes a page, course or
// news address (GET /api/v1/public/redirects). This file is the pure logic (no Next.js imports),
// so it is unit-tested; src/proxy.ts uses it to answer visitors with a real 301/302.

export type RedirectStatus = 301 | 302 | 307 | 308;

export type RedirectRule = { toPath: string; statusCode: RedirectStatus };

/** Old path -> where it now lives. */
export type RedirectTable = ReadonlyMap<string, RedirectRule>;

const STATUS_CODES: readonly number[] = [301, 302, 307, 308];

/** Site paths only: one leading "/", never "//" or a backslash (open-redirect tricks). */
function isLocalPath(value: unknown): value is string {
  if (typeof value !== "string" || value.length > 300) return false;
  if (!value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return false;
  for (const char of value) {
    const code = char.charCodeAt(0);
    if (code < 32 || code === 127) return false;
  }
  return true;
}

/** "/news/" and "/news" are the same page. The home page stays "/". */
export function normalizePath(path: string): string {
  return path.length > 1 && path.endsWith("/") ? path.replace(/\/+$/, "") || "/" : path;
}

/** Turns the API answer into a lookup table. Anything that is not a safe rule is dropped, so a
 * wrong row can never send visitors to another website. */
export function parseRedirects(data: unknown): RedirectTable {
  const table = new Map<string, RedirectRule>();
  if (!Array.isArray(data)) return table;
  for (const row of data as unknown[]) {
    if (typeof row !== "object" || row === null) continue;
    const { fromPath, toPath, statusCode } = row as Record<string, unknown>;
    if (!isLocalPath(fromPath) || !isLocalPath(toPath)) continue;
    if (typeof statusCode !== "number" || !STATUS_CODES.includes(statusCode)) continue;
    const from = normalizePath(fromPath);
    if (from === normalizePath(toPath)) continue;
    table.set(from, { toPath, statusCode: statusCode as RedirectStatus });
  }
  return table;
}

const MAX_HOPS = 5;

/** Where a visitor of `pathname` should go, or null when the address is not redirected.
 * A chain (A -> B -> C) is followed to the end in one step; a loop gives up (returns null) so the
 * visitor sees the normal page instead of an endless redirect. The query string is kept. */
export function resolveRedirect(
  table: RedirectTable,
  pathname: string,
  search = "",
): { location: string; status: RedirectStatus } | null {
  let current = normalizePath(pathname);
  const seen = new Set<string>([current]);
  let rule: RedirectRule | undefined;
  for (let hop = 0; hop < MAX_HOPS; hop++) {
    const next = table.get(current);
    if (!next) break;
    rule = next;
    current = normalizePath(next.toPath);
    if (seen.has(current)) return null;
    seen.add(current);
  }
  if (!rule || current === normalizePath(pathname)) return null;
  // The new address may carry its own "?" or "#" (it is stored as typed by the editor): keep it
  // and only add the visitor's query string when there is none.
  const target = rule.toPath;
  const location = search && !target.includes("?") ? `${target}${search}` : target;
  return { location, status: rule.statusCode };
}

/** Keeps the table for a short time, so the check costs nothing on most requests. If the API
 * does not answer, the last good table keeps working (or an empty one, never an error page). */
export function createRedirectCache(
  load: () => Promise<RedirectTable>,
  ttlMs: number,
  now: () => number = Date.now,
) {
  let table: RedirectTable = new Map();
  let loadedAt = Number.NEGATIVE_INFINITY;
  let inFlight: Promise<void> | null = null;

  function refresh(): Promise<void> {
    inFlight ??= load()
      .then((fresh) => {
        table = fresh;
        loadedAt = now();
      })
      .catch(() => {
        // Try again in a few seconds instead of on every request.
        loadedAt = now() - ttlMs + Math.min(ttlMs, 5_000);
      })
      .finally(() => {
        inFlight = null;
      });
    return inFlight;
  }

  return {
    async get(): Promise<RedirectTable> {
      if (now() - loadedAt >= ttlMs) await refresh();
      return table;
    },
    /** The next request loads a fresh table (called when an editor changes a redirect). */
    clear(): void {
      loadedAt = Number.NEGATIVE_INFINITY;
    },
  };
}
