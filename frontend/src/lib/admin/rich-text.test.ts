import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { isEmptyDoc, plainText, sanitizeDoc } from "./rich-text.ts";

const para = (...content: unknown[]) => ({ type: "paragraph", content });
const text = (value: string, marks?: unknown[]) => ({ type: "text", text: value, ...(marks ? { marks } : {}) });

describe("cleaning editor output for the server", () => {
  it("keeps allowed structure and formatting", () => {
    const input = {
      type: "doc",
      content: [
        { type: "heading", attrs: { level: 2 }, content: [text("Title")] },
        para(text("A "), text("bold", [{ type: "bold" }]), text(" and ", [{ type: "italic" }, { type: "underline" }])),
        { type: "bulletList", content: [{ type: "listItem", content: [para(text("one"))] }] },
        { type: "blockquote", content: [para(text("quote"), { type: "hardBreak" }, text("more"))] },
      ],
    };
    assert.deepEqual(sanitizeDoc(input), input);
  });

  it("removes attributes the server does not accept (target, rel, class, list start)", () => {
    const input = {
      type: "doc",
      content: [
        para(text("see", [{ type: "link", attrs: { href: "https://example.com/a", target: "_blank", rel: "noopener", class: "x" } }])),
        { type: "orderedList", attrs: { start: 1, type: null }, content: [{ type: "listItem", content: [para(text("a"))] }] },
      ],
    };
    const clean = sanitizeDoc(input);
    assert.deepEqual(clean.content[0], para(text("see", [{ type: "link", attrs: { href: "https://example.com/a" } }])));
    assert.deepEqual(clean.content[1], { type: "orderedList", content: [{ type: "listItem", content: [para(text("a"))] }] });
  });

  it("keeps the words of an unsafe link but drops the link", () => {
    for (const href of ["javascript:alert(1)", "//evil.example", "data:text/html,x", "", "/\\evil.example"]) {
      const clean = sanitizeDoc({ type: "doc", content: [para(text("click", [{ type: "link", attrs: { href } }]))] });
      assert.deepEqual(clean.content[0], para(text("click")), href);
    }
  });

  it("turns other heading levels and unknown nodes into safe ones", () => {
    const clean = sanitizeDoc({
      type: "doc",
      content: [
        { type: "heading", attrs: { level: 1 }, content: [text("Big")] },
        { type: "heading", attrs: { level: 4 }, content: [text("Small")] },
        { type: "codeBlock", content: [text("code")] },
        { type: "image", attrs: { src: "x" } },
        { type: "script" },
      ],
    });
    // headings other than h2/h3 become paragraphs; node types we do not support are dropped
    assert.deepEqual(clean.content, [para(text("Big")), para(text("Small"))]);
  });

  it("flattens what does not fit inside a quote or list", () => {
    const clean = sanitizeDoc({
      type: "doc",
      content: [
        { type: "blockquote", content: [{ type: "heading", attrs: { level: 2 }, content: [text("H")] }, para(text("p"))] },
      ],
    });
    assert.deepEqual(clean.content, [{ type: "blockquote", content: [para(text("H")), para(text("p"))] }]);
  });

  it("drops unknown marks, empty text and empty lists", () => {
    const clean = sanitizeDoc({
      type: "doc",
      content: [
        para(text("x", [{ type: "color", attrs: { color: "red" } }, { type: "bold" }, { type: "bold" }]), text("")),
        { type: "bulletList", content: [] },
      ],
    });
    assert.deepEqual(clean.content, [para(text("x", [{ type: "bold" }]))]);
  });

  it("never returns an empty document and is safe on junk", () => {
    const empty = { type: "doc", content: [{ type: "paragraph" }] };
    assert.deepEqual(sanitizeDoc(null), empty);
    assert.deepEqual(sanitizeDoc({ type: "doc", content: [] }), empty);
    assert.deepEqual(sanitizeDoc("<script>"), empty);
    assert.deepEqual(sanitizeDoc({ type: "doc", content: [{ type: "script" }] }), empty);
  });

  it("is idempotent", () => {
    const once = sanitizeDoc({ type: "doc", content: [para(text("a", [{ type: "link", attrs: { href: "/x", target: "_blank" } }]))] });
    assert.deepEqual(sanitizeDoc(once), once);
  });

  it("stops at the depth the website renders", () => {
    let node: unknown = para(text("deep"));
    for (let i = 0; i < 6; i += 1) node = { type: "bulletList", content: [{ type: "listItem", content: [node] }] };
    const clean = sanitizeDoc({ type: "doc", content: [node] });
    assert.equal(JSON.stringify(clean).includes("deep"), false);
  });
});

describe("reading the text of a document", () => {
  it("finds the plain text and tells empty from filled", () => {
    const doc = { type: "doc", content: [para(text("Hello "), text("world")), { type: "bulletList", content: [{ type: "listItem", content: [para(text("item"))] }] }] };
    assert.equal(plainText(doc), "Hello world item");
    assert.equal(isEmptyDoc(doc), false);
    assert.equal(isEmptyDoc({ type: "doc", content: [{ type: "paragraph" }] }), true);
    assert.equal(isEmptyDoc({ type: "doc", content: [para(text("   "))] }), true);
    assert.equal(isEmptyDoc(null), true);
  });
});
