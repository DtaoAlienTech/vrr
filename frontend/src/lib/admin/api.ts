// The browser's connection to the staff API. It adds the CSRF token to every change, renews an
// expired login once (and retries), copes with a token that went stale in another tab, and keeps
// upload progress. All the rules the server enforces (roles, validation) stay on the server.
import { ApiProblem, NETWORK_PROBLEM, parseProblem } from "./problem.ts";
import type { MediaItem, SessionInfo } from "./types.ts";

const BASE = "/api/v1";

let csrfToken: string | null = null;
let onLost: (() => void) | null = null;

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

/** Called when the login can no longer be renewed (the screens then go to the sign-in page). */
export function onSessionLost(handler: (() => void) | null): void {
  onLost = handler;
}

export type Query = Record<string, string | number | boolean | undefined | null>;

export function withQuery(path: string, query?: Query): string {
  const parts = Object.entries(query ?? {})
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
  return parts.length > 0 ? `${path}?${parts.join("&")}` : path;
}

async function readBody(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined;
  const type = response.headers.get("content-type") ?? "";
  if (type.includes("json")) return response.json().catch(() => undefined);
  return response.text().catch(() => undefined);
}

let renewing: Promise<boolean> | null = null;

/** Gets a new login from the refresh cookie. One request at a time, however many screens ask. */
export function renewSession(): Promise<boolean> {
  renewing ??= (async () => {
    try {
      const response = await fetch(`${BASE}/auth/refresh`, { method: "POST", credentials: "same-origin" });
      if (response.ok) {
        const body = (await response.json()) as SessionInfo;
        setCsrfToken(body.csrfToken);
        return true;
      }
      if (response.status === 401) {
        const body = (await readBody(response)) as { code?: string } | undefined;
        if (body?.code === "session_replaced") {
          // another tab renewed the login a moment ago: its new cookies are already in place
          return (await fetchSession()) !== null;
        }
      }
      return false;
    } catch {
      return false;
    }
  })().finally(() => {
    renewing = null;
  });
  return renewing;
}

export async function fetchSession(): Promise<SessionInfo | null> {
  try {
    const response = await fetch(`${BASE}/auth/me`, { credentials: "same-origin" });
    if (!response.ok) return null;
    const info = (await response.json()) as SessionInfo;
    setCsrfToken(info.csrfToken);
    return info;
  } catch {
    return null;
  }
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
type Options = { body?: unknown; signal?: AbortSignal; auth?: boolean };

async function once(method: Method, url: string, options: Options): Promise<Response> {
  const headers: Record<string, string> = {};
  let body: string | undefined;
  if (options.body !== undefined) {
    headers["content-type"] = "application/json";
    body = JSON.stringify(options.body);
  }
  if (method !== "GET" && csrfToken) headers["x-csrf-token"] = csrfToken;
  return fetch(`${BASE}${url}`, { method, headers, body, credentials: "same-origin", signal: options.signal });
}

async function request(method: Method, url: string, options: Options = {}): Promise<unknown> {
  let response: Response;
  try {
    response = await once(method, url, options);
    if (options.auth !== false) {
      if (response.status === 401 && (await renewSession())) {
        response = await once(method, url, options);
      } else if (response.status === 403) {
        const body = (await readBody(response.clone())) as { code?: string } | undefined;
        if (body?.code === "csrf_failed" && (await fetchSession())) response = await once(method, url, options);
      }
    }
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw NETWORK_PROBLEM;
  }
  const body = await readBody(response);
  if (!response.ok) {
    const problem = parseProblem(response.status, body);
    if (response.status === 401 && options.auth !== false) onLost?.();
    throw problem;
  }
  return body;
}

export const api = {
  get: <T>(url: string, signal?: AbortSignal) => request("GET", url, { signal }) as Promise<T>,
  post: <T = void>(url: string, body?: unknown, options: Options = {}) => request("POST", url, { ...options, body }) as Promise<T>,
  put: <T = void>(url: string, body?: unknown) => request("PUT", url, { body }) as Promise<T>,
  patch: <T = void>(url: string, body?: unknown) => request("PATCH", url, { body }) as Promise<T>,
  delete: <T = void>(url: string) => request("DELETE", url) as Promise<T>,
};

// ---------- uploads (with progress) ----------

export type Upload = { promise: Promise<MediaItem>; abort: () => void };

function sendFile(form: FormData, onProgress: (fraction: number) => void, xhrRef: { current?: XMLHttpRequest }): Promise<{ status: number; body: unknown }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhrRef.current = xhr;
    xhr.open("POST", `${BASE}/admin/media`);
    xhr.withCredentials = true;
    if (csrfToken) xhr.setRequestHeader("x-csrf-token", csrfToken);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    };
    xhr.onload = () => {
      let body: unknown;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        body = undefined;
      }
      resolve({ status: xhr.status, body });
    };
    xhr.onerror = () => reject(NETWORK_PROBLEM);
    xhr.onabort = () => reject(new DOMException("Upload cancelled", "AbortError"));
    xhr.send(form);
  });
}

export function uploadMedia(file: File, altText: string, cropBottom: boolean, onProgress: (fraction: number) => void): Upload {
  const xhrRef: { current?: XMLHttpRequest } = {};
  const run = async (): Promise<MediaItem> => {
    const build = () => {
      const form = new FormData();
      form.append("file", file);
      if (altText.trim()) form.append("altText", altText.trim());
      if (cropBottom) form.append("cropBottom", "true");
      return form;
    };
    let result = await sendFile(build(), onProgress, xhrRef);
    const code = (result.body as { code?: string } | undefined)?.code;
    if (result.status === 401 && (await renewSession())) result = await sendFile(build(), onProgress, xhrRef);
    else if (result.status === 403 && code === "csrf_failed" && (await fetchSession())) {
      result = await sendFile(build(), onProgress, xhrRef);
    }
    if (result.status === 201) return result.body as MediaItem;
    throw parseProblem(result.status, result.body);
  };
  return { promise: run(), abort: () => xhrRef.current?.abort() };
}

export { ApiProblem };
