// Rich text is stored as restricted editor JSON (a subset of TipTap / ProseMirror). The server
// refuses anything outside that subset, so what the editor produces is cleaned here first:
// only these nodes and marks survive, links are checked, and extra attributes (target, rel,
// class, list "start", ...) are removed. Mirrors backend/app/schemas/common.py.
import { isSafeHref } from "./links.ts";

export type RichMark = { type: string; attrs?: { href: string } };
export type RichNode = {
  type: string;
  text?: string;
  attrs?: { level: number };
  marks?: RichMark[];
  content?: RichNode[];
};
export type RichDoc = { type: "doc"; content: RichNode[] };

const CHILDREN: Record<string, ReadonlySet<string>> = {
  doc: new Set(["paragraph", "heading", "bulletList", "orderedList", "blockquote"]),
  paragraph: new Set(["text", "hardBreak"]),
  heading: new Set(["text", "hardBreak"]),
  bulletList: new Set(["listItem"]),
  orderedList: new Set(["listItem"]),
  listItem: new Set(["paragraph", "bulletList", "orderedList"]),
  blockquote: new Set(["paragraph"]),
  text: new Set(),
  hardBreak: new Set(),
};
const MARKS = new Set(["bold", "italic", "underline", "link"]);
export const MAX_RICH_CHARS = 20000;
const MAX_DEPTH = 6;

type Json = Record<string, unknown>;
const isObject = (value: unknown): value is Json =>
  typeof value === "object" && value !== null && !Array.isArray(value);

function cleanMarks(marks: unknown): RichMark[] | undefined {
  if (!Array.isArray(marks)) return undefined;
  const clean: RichMark[] = [];
  for (const mark of marks) {
    if (!isObject(mark) || typeof mark.type !== "string" || !MARKS.has(mark.type)) continue;
    if (mark.type === "link") {
      const attrs = isObject(mark.attrs) ? mark.attrs : {};
      const href = typeof attrs.href === "string" ? attrs.href.trim() : "";
      if (isSafeHref(href)) clean.push({ type: "link", attrs: { href } });
      continue; // an unsafe link keeps its text but loses the link
    }
    if (!clean.some((c) => c.type === mark.type)) clean.push({ type: mark.type });
  }
  return clean.length > 0 ? clean.slice(0, 4) : undefined;
}

/** Cleans one node for its parent. A node that does not fit is flattened into its parent. */
function cleanNode(node: unknown, parent: string, depth: number): RichNode[] {
  if (!isObject(node) || typeof node.type !== "string" || depth > MAX_DEPTH) return [];
  let type = node.type;
  const level = isObject(node.attrs) ? node.attrs.level : undefined;
  if (type === "heading" && level !== 2 && level !== 3) type = "paragraph"; // only h2 / h3 exist
  if (!(type in CHILDREN)) return [];

  const allowed = CHILDREN[parent];
  if (!allowed.has(type)) {
    // Does not belong here (for example a heading inside a quote): keep its content as paragraphs.
    const content = Array.isArray(node.content) ? node.content : [];
    if (type === "heading" && allowed.has("paragraph")) {
      return cleanNode({ ...node, type: "paragraph", attrs: undefined }, parent, depth);
    }
    return content.flatMap((child) => cleanNode(child, parent, depth));
  }

  if (type === "text") {
    if (typeof node.text !== "string" || node.text.length === 0) return [];
    const marks = cleanMarks(node.marks);
    return [{ type, text: node.text, ...(marks ? { marks } : {}) }];
  }
  if (type === "hardBreak") return [{ type }];

  const children = (Array.isArray(node.content) ? node.content : []).flatMap((child) =>
    cleanNode(child, type, depth + 1),
  );
  const result: RichNode = { type };
  if (type === "heading") result.attrs = { level: level === 3 ? 3 : 2 };
  if (children.length > 0) result.content = children;
  else if (type === "bulletList" || type === "orderedList" || type === "listItem") return [];
  return [result];
}

/** What the editor produced, cleaned to what the server accepts (never empty). */
export function sanitizeDoc(input: unknown): RichDoc {
  const content = isObject(input) && Array.isArray(input.content) ? input.content : [];
  const clean = content.flatMap((node) => cleanNode(node, "doc", 0));
  return { type: "doc", content: clean.length > 0 ? clean : [{ type: "paragraph" }] };
}

export function plainText(doc: unknown): string {
  const parts: string[] = [];
  const walk = (node: unknown) => {
    if (!isObject(node)) return;
    if (node.type === "text" && typeof node.text === "string") parts.push(node.text);
    if (node.type === "hardBreak") parts.push(" ");
    if (Array.isArray(node.content)) node.content.forEach(walk);
    if (["paragraph", "heading", "listItem"].includes(String(node.type))) parts.push(" ");
  };
  walk(doc);
  return parts.join("").replace(/\s+/g, " ").trim();
}

export function isEmptyDoc(doc: unknown): boolean {
  return plainText(doc).length === 0;
}

export function docTooLong(doc: unknown): boolean {
  return plainText(doc).length > MAX_RICH_CHARS;
}

export const EMPTY_DOC: RichDoc = { type: "doc", content: [{ type: "paragraph" }] };
