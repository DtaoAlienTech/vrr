import assert from "node:assert/strict";
import { test } from "node:test";
import ReactDOMServer from "react-dom/server";
import { renderRichText } from "./rich-text.ts";

const html = (doc: unknown) => ReactDOMServer.renderToStaticMarkup(renderRichText(doc) as never);
const text = (value: string, marks?: unknown[]) => ({ type: "text", text: value, ...(marks ? { marks } : {}) });
const para = (...content: unknown[]) => ({ type: "paragraph", content });
const doc = (...content: unknown[]) => ({ type: "doc", content });

test("renders paragraphs, lists and marks", () => {
  const out = html(
    doc(
      para(text("Hello "), text("world", [{ type: "bold" }])),
      { type: "bulletList", content: [{ type: "listItem", content: [para(text("one"))] }] },
    ),
  );
  assert.equal(out, "<p>Hello <strong>world</strong></p><ul><li><p>one</p></li></ul>");
});

test("html written as text is escaped, never executed", () => {
  const out = html(doc(para(text("<script>alert(1)</script><img src=x onerror=alert(1)>"))));
  assert.ok(!out.includes("<script"));
  assert.ok(!out.includes("<img"));
  assert.ok(out.includes("&lt;script&gt;"));
});

test("dangerous link addresses are replaced", () => {
  const out = html(doc(para(text("x", [{ type: "link", attrs: { href: "javascript:alert(1)" } }]))));
  assert.ok(!out.includes("javascript:"));
  assert.ok(out.includes('href="#"'));
});

test("safe external links open safely", () => {
  const out = html(doc(para(text("x", [{ type: "link", attrs: { href: "https://example.com" } }]))));
  assert.ok(out.includes('rel="noopener noreferrer"'));
  assert.ok(out.includes('target="_blank"'));
});

test("unknown nodes and raw html fields are dropped", () => {
  const out = html(
    doc(
      { type: "script", content: [text("alert(1)")] },
      { type: "html", html: "<b onclick=x>hi</b>" },
      { type: "paragraph", html: "<i>nope</i>", content: [text("kept")] },
    ),
  );
  assert.equal(out, "<p>kept</p>");
});

test("headings start at h3 because section titles use h2", () => {
  assert.equal(html(doc({ type: "heading", attrs: { level: 2 }, content: [text("A")] })), "<h3>A</h3>");
  assert.equal(html(doc({ type: "heading", attrs: { level: 1 }, content: [text("B")] })), "<p>B</p>");
});

test("invalid documents render nothing", () => {
  for (const bad of [null, undefined, "text", 42, { type: "doc" }, { type: "paragraph" }, []]) {
    assert.equal(renderRichText(bad), null);
  }
});

test("very deep or huge documents are cut off", () => {
  let deep: unknown = para(text("deep"));
  for (let i = 0; i < 20; i++) deep = { type: "blockquote", content: [deep] };
  assert.ok(!html(doc(deep)).includes("deep"));
  const many = Array.from({ length: 5000 }, () => para(text("x")));
  assert.ok(html(doc(...many)).split("<p>").length - 1 <= 2000);
});
