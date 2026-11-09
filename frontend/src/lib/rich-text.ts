// Draws editor JSON (a restricted subset of the TipTap / ProseMirror format) as React elements.
// There is no HTML anywhere: every text is a React text node (escaped by React), unknown node
// types are dropped, and links go through safeHref. Written with createElement (no JSX) so the
// unit tests can import it directly.
import { createElement, type ReactNode } from "react";
import { safeHref } from "./safe-href.ts";

const MAX_DEPTH = 6;
const MAX_NODES = 2000;

type Json = Record<string, unknown>;
const isObject = (value: unknown): value is Json =>
  typeof value === "object" && value !== null && !Array.isArray(value);

type Budget = { left: number };

function applyMarks(text: string, marks: unknown, key: string): ReactNode {
  let node: ReactNode = text;
  if (!Array.isArray(marks)) return node;
  for (const mark of marks) {
    if (!isObject(mark)) continue;
    if (mark.type === "bold") node = createElement("strong", { key }, node);
    else if (mark.type === "italic") node = createElement("em", { key }, node);
    else if (mark.type === "underline") node = createElement("u", { key }, node);
    else if (mark.type === "link") {
      const attrs = isObject(mark.attrs) ? mark.attrs : {};
      const href = safeHref(typeof attrs.href === "string" ? attrs.href : "");
      const external = /^https?:/i.test(href);
      node = createElement(
        "a",
        { key, href, ...(external ? { target: "_blank", rel: "noopener noreferrer" } : {}) },
        node,
      );
    }
  }
  return node;
}

function renderChildren(content: unknown, depth: number, budget: Budget, key: string): ReactNode[] {
  if (!Array.isArray(content)) return [];
  return content.map((child, index) => renderNode(child, depth + 1, budget, `${key}.${index}`));
}

function renderNode(node: unknown, depth: number, budget: Budget, key: string): ReactNode {
  if (!isObject(node) || depth > MAX_DEPTH || budget.left <= 0) return null;
  budget.left -= 1;
  const children = () => renderChildren(node.content, depth, budget, key);

  switch (node.type) {
    case "text":
      return typeof node.text === "string" ? applyMarks(node.text, node.marks, key) : null;
    case "paragraph":
      return createElement("p", { key }, ...children());
    case "heading": {
      const level = isObject(node.attrs) ? node.attrs.level : undefined;
      // Section titles are h2, so editor headings start at h3.
      if (level === 2) return createElement("h3", { key }, ...children());
      if (level === 3) return createElement("h4", { key }, ...children());
      return createElement("p", { key }, ...children());
    }
    case "bulletList":
      return createElement("ul", { key }, ...children());
    case "orderedList":
      return createElement("ol", { key }, ...children());
    case "listItem":
      return createElement("li", { key }, ...children());
    case "blockquote":
      return createElement("blockquote", { key }, ...children());
    case "hardBreak":
      return createElement("br", { key });
    default:
      return null;
  }
}

/** Returns the elements for a rich-text document, or nothing if the data is not a valid document. */
export function renderRichText(doc: unknown): ReactNode {
  if (!isObject(doc) || doc.type !== "doc" || !Array.isArray(doc.content)) return null;
  const budget: Budget = { left: MAX_NODES };
  return doc.content.map((node, index) => renderNode(node, 0, budget, `n${index}`));
}
