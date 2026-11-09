// Only these link types are ever rendered: site paths, #anchors, http(s), mailto and tel.
const ALLOWED = /^(\/(?![/\\])|#|https?:\/\/|mailto:|tel:)/i;

/**
 * Returns the link if it is safe to render, otherwise "#".
 * Control characters and backslashes are rejected everywhere, because browsers silently remove
 * tabs and newlines and treat "\" like "/": "/\t/evil.com" and "/\evil.com" would both turn
 * into the protocol-relative address "//evil.com".
 */
export function safeHref(href: string): string {
  const value = href.trim();
  for (const char of value) {
    const code = char.charCodeAt(0);
    if (code < 32 || code === 127 || char === "\\") return "#";
  }
  return ALLOWED.test(value) ? value : "#";
}
