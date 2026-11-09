// The same link rule as the backend (and the website's safeHref): site paths, #anchors, https,
// mailto and tel only. Control characters and backslashes are refused everywhere, because
// browsers turn "/\t/evil.com" and "/\evil.com" into "//evil.com".
const SAFE_START = /^(\/(?![/\\])|#|https:\/\/|mailto:|tel:)/i;

export function isSafeHref(value: string): boolean {
  const href = value.trim();
  if (href.length === 0 || href.length > 500) return false;
  for (const char of href) {
    const code = char.charCodeAt(0);
    if (code < 32 || code === 127 || char === "\\") return false;
  }
  if (!SAFE_START.test(href)) return false;
  if (/^https:\/\//i.test(href)) {
    try {
      return new URL(href).hostname.length > 0;
    } catch {
      return false;
    }
  }
  return true;
}

export const LINK_HELP = "Use a site address like /about, a #link, https://…, mailto: or tel:";

/** Every link (any "href" string) inside a block of page data, to check them before saving. */
export function collectLinks(value: unknown, found: string[] = []): string[] {
  if (Array.isArray(value)) {
    for (const item of value) collectLinks(item, found);
  } else if (value !== null && typeof value === "object") {
    for (const [key, item] of Object.entries(value)) {
      if (key === "href" && typeof item === "string") found.push(item);
      else collectLinks(item, found);
    }
  }
  return found;
}

/** Site paths (starting with "/") that do not match any known page address. */
export function brokenSitePaths(links: string[], knownPaths: Iterable<string>): string[] {
  const known = new Set(knownPaths);
  return links.filter((link) => {
    if (!link.startsWith("/") || link.startsWith("//")) return false;
    const path = link.split(/[?#]/)[0].replace(/\/+$/, "") || "/";
    if (known.has(path)) return false;
    // detail pages live under a known list address: /courses/anything, /news/anything
    const parent = "/" + path.split("/")[1];
    return !(path.split("/").length > 2 && known.has(parent));
  });
}
