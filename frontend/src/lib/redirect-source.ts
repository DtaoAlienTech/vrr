// Loads the redirect rules from the backend, shared by src/proxy.ts and the refresh hook.
import { createRedirectCache, parseRedirects, type RedirectTable } from "./redirects";

const BACKEND_URL = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

/** 30 s is the longest a new redirect can take to start working if the refresh hook is missed. */
const TTL_MS = 30_000;

async function load(): Promise<RedirectTable> {
  const response = await fetch(`${BACKEND_URL}/api/v1/public/redirects`, {
    headers: { accept: "application/json" },
    signal: AbortSignal.timeout(2_000), // never hold up a visitor for long
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Redirects API answered ${response.status}`);
  return parseRedirects(await response.json());
}

// One cache per server process. It is kept on globalThis so the proxy and the refresh route
// (which Next.js may bundle separately) use the same one.
const KEY = Symbol.for("vrr.redirectCache");
type Cache = ReturnType<typeof createRedirectCache>;
const holder = globalThis as unknown as Record<symbol, Cache | undefined>;
const cache: Cache = (holder[KEY] ??= createRedirectCache(load, TTL_MS));

export function getRedirectTable(): Promise<RedirectTable> {
  return cache.get();
}

/** Called when an editor changes a redirect: the next request loads the new rules. */
export function clearRedirectCache(): void {
  cache.clear();
}
