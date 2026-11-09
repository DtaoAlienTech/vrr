import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  deref,
  humanize,
  initialValue,
  isRequired,
  kindOf,
  newVariantValue,
  prune,
  unwrap,
  validate,
  variantsOf,
  type JsonSchema,
} from "./json-schema.ts";

// Shapes copied from what the backend really produces (Pydantic JSON Schema).
const ROOT: JsonSchema = {
  type: "object",
  required: ["title", "category", "body", "main"],
  properties: {
    title: { type: "string", minLength: 1, maxLength: 20, title: "Title" },
    slug: {
      anyOf: [{ type: "string", maxLength: 120, minLength: 1, pattern: "^[a-z0-9]+(-[a-z0-9]+)*$" }, { type: "null" }],
      default: null,
      description: "The web address.",
    },
    category: { $ref: "#/$defs/Category" },
    summary: { type: "string", maxLength: 400 },
    body: { type: "object", "x-widget": "richtext" },
    coverMediaId: {
      anyOf: [{ type: "integer", minimum: 1, "x-widget": "media-image" }, { type: "null" }],
      default: null,
    },
    isPinned: { type: "boolean", default: false },
    year: { anyOf: [{ type: "integer", minimum: 1990, maximum: 2100 }, { type: "null" }], default: null },
    tone: { type: "string", enum: ["default", "alt"], default: "default" },
    link: { type: "string", "x-widget": "link", maxLength: 500 },
    subjects: { type: "array", items: { type: "string", maxLength: 10 }, maxItems: 3 },
    cta: { anyOf: [{ $ref: "#/$defs/Link" }, { type: "null" }], default: null },
    image: { $ref: "#/$defs/MediaPick" },
    cards: { type: "array", items: { $ref: "#/$defs/Link" }, minItems: 1, maxItems: 2 },
    main: {
      type: "array",
      minItems: 1,
      items: {
        discriminator: { propertyName: "type", mapping: { panel: "#/$defs/EmbeddedPanel", faq: "#/$defs/EmbeddedFaq" } },
        oneOf: [{ $ref: "#/$defs/EmbeddedPanel" }, { $ref: "#/$defs/EmbeddedFaq" }],
      },
    },
  },
  $defs: {
    Category: { type: "string", enum: ["admission", "notice"] },
    Link: {
      type: "object",
      required: ["label", "href"],
      properties: {
        label: { type: "string", minLength: 1, maxLength: 80 },
        href: { type: "string", "x-widget": "link", maxLength: 500 },
      },
    },
    MediaPick: {
      type: "object",
      "x-widget": "media",
      required: ["mediaId"],
      properties: { mediaId: { type: "integer", exclusiveMinimum: 0 } },
    },
    PanelData: { type: "object", properties: { title: { type: "string", maxLength: 50 } } },
    FaqData: {
      type: "object",
      required: ["items"],
      properties: { items: { type: "array", minItems: 1, items: { type: "string" } } },
    },
    EmbeddedPanel: {
      type: "object",
      required: ["type", "data"],
      properties: {
        type: { const: "panel", type: "string" },
        data: { $ref: "#/$defs/PanelData" },
        isVisible: { type: "boolean", default: true },
      },
    },
    EmbeddedFaq: {
      type: "object",
      required: ["type", "data"],
      properties: { type: { const: "faq", type: "string" }, data: { $ref: "#/$defs/FaqData" } },
    },
  },
};

const prop = (name: string) => ROOT.properties![name];
const doc = (text: string) => ({ type: "doc", content: [{ type: "paragraph", content: [{ type: "text", text }] }] });

describe("reading schemas", () => {
  it("follows references and keeps the description written beside them", () => {
    const resolved = deref({ $ref: "#/$defs/Category", description: "Pick one" }, ROOT);
    assert.deepEqual(resolved.enum, ["admission", "notice"]);
    assert.equal(resolved.description, "Pick one");
    assert.throws(() => deref({ $ref: "#/$defs/Nope" }, ROOT), /Unknown schema reference/);
    assert.deepEqual(deref({ allOf: [{ $ref: "#/$defs/Category" }], description: "d" }, ROOT).enum, ["admission", "notice"]);
  });

  it("recognises optional fields and keeps their description and default", () => {
    const slug = unwrap(prop("slug"), ROOT);
    assert.equal(slug.optional, true);
    assert.equal(slug.schema.type, "string");
    assert.equal(slug.schema.description, "The web address.");
    assert.equal(unwrap(prop("title"), ROOT).optional, false);
    assert.equal(unwrap(prop("cta"), ROOT).schema.required?.includes("href"), true);
  });

  it("decides what kind of input each field needs", () => {
    const kind = (name: string) => kindOf(unwrap(prop(name), ROOT).schema, ROOT);
    assert.equal(kind("title"), "text");
    assert.equal(kind("summary"), "textarea");
    assert.equal(kind("category"), "select");
    assert.equal(kind("body"), "richtext");
    assert.equal(kind("coverMediaId"), "media-image");
    assert.equal(kind("image"), "media-pick");
    assert.equal(kind("isPinned"), "boolean");
    assert.equal(kind("year"), "number");
    assert.equal(kind("link"), "link");
    assert.equal(kind("subjects"), "list-text");
    assert.equal(kind("cards"), "list-object");
    assert.equal(kind("cta"), "object");
    assert.equal(kind("main"), "list-object");
    assert.equal(kindOf(unwrap(prop("main"), ROOT).schema.items!, ROOT), "union");
  });

  it("finds the choices of a union of blocks", () => {
    const variants = variantsOf(prop("main").items!, ROOT);
    assert.deepEqual(variants?.map((v) => v.key), ["panel", "faq"]);
    assert.equal(variantsOf(prop("title"), ROOT), null);
    assert.equal(variantsOf({ anyOf: [{ type: "string" }, { type: "integer" }] }, ROOT), null);
  });

  it("makes readable names", () => {
    assert.equal(humanize("primaryCta"), "Primary cta");
    assert.equal(humanize("show_on_home"), "Show on home");
    assert.equal(humanize("seoTitle"), "Seo title");
  });

  it("knows which fields are required", () => {
    assert.equal(isRequired(ROOT, "title", ROOT), true);
    assert.equal(isRequired(ROOT, "slug", ROOT), false);
    assert.equal(isRequired(ROOT, "nothing", ROOT), false);
  });
});

describe("starting values", () => {
  it("starts with required lists empty, defaults filled and optional fields unset", () => {
    const start = initialValue(ROOT, ROOT) as Record<string, unknown>;
    assert.deepEqual(start.main, []);
    assert.equal(start.tone, "default");
    assert.equal(start.isPinned, false);
    assert.equal("slug" in start, false);
    assert.equal("title" in start, false);
    assert.equal("coverMediaId" in start, false);
  });

  it("builds the value of a new block of a chosen kind", () => {
    const panel = variantsOf(prop("main").items!, ROOT)![0];
    const value = newVariantValue(panel, ROOT);
    assert.equal(value.type, "panel");
    assert.deepEqual(value.data, {});
    assert.equal(value.isVisible, true);
    const faq = newVariantValue(variantsOf(prop("main").items!, ROOT)![1], ROOT);
    assert.deepEqual(faq.data, { items: [] });
  });
});

describe("what is sent to the server", () => {
  it("drops empty text, unset fields and empty objects but keeps zero, false and lists", () => {
    const cleaned = prune({
      title: "  ",
      summary: "Hello",
      year: 0,
      isPinned: false,
      subjects: ["a", "", "b"],
      cta: { label: "", href: " " },
      nested: { deep: { value: undefined } },
      empty: [],
    });
    assert.deepEqual(cleaned, { summary: "Hello", year: 0, isPinned: false, subjects: ["a", "b"], empty: [] });
  });

  it("keeps the empty data of a block that has no fields", () => {
    assert.deepEqual(prune({ type: "contact_info", data: {}, isVisible: true }), { type: "contact_info", data: {}, isVisible: true });
    assert.deepEqual(prune({ type: "map", data: { title: " " } }), { type: "map", data: {} });
    assert.deepEqual(prune({ other: {} }), undefined);
  });

  it("leaves rich text documents alone", () => {
    const body = doc("Hi");
    assert.deepEqual(prune({ body }), { body });
  });
});

describe("checking a form like the server does", () => {
  const good = () => ({ title: "Open day", category: "notice", body: doc("Hello"), main: [{ type: "panel", data: {} }] });

  it("accepts a valid form", () => {
    assert.deepEqual(validate(ROOT, good()), {});
  });

  it("asks for what is required, with the server's field names", () => {
    const problems = validate(ROOT, { main: [] });
    assert.deepEqual(Object.keys(problems).sort(), ["body", "category", "main", "title"]);
    assert.equal(problems.title, "This is required.");
    assert.equal(problems.main, "Add at least 1.");
  });

  it("treats an empty rich text document as missing", () => {
    const problems = validate(ROOT, { ...good(), body: { type: "doc", content: [{ type: "paragraph" }] } });
    assert.equal(problems.body, "This is required.");
  });

  it("checks lengths, patterns, options, numbers and links", () => {
    const problems = validate(ROOT, {
      ...good(),
      title: "x".repeat(21),
      slug: "Bad Slug",
      category: "gossip",
      year: 1800,
      link: "javascript:alert(1)",
      subjects: ["a", "b", "c", "d"],
    });
    assert.match(problems.title, /Too long: 21 of at most 20/);
    assert.match(problems.slug, /lower-case letters/);
    assert.equal(problems.category, "Choose one of the options.");
    assert.equal(problems.year, "At least 1990.");
    assert.match(problems.link, /Use a site address/);
    assert.equal(problems.subjects, "At most 3 items.");
  });

  it("names nested fields like the server (cta.href, cards.1.label, main.0.data.title)", () => {
    const problems = validate(ROOT, {
      ...good(),
      cta: { label: "Go", href: "//evil.example" },
      cards: [{ label: "ok", href: "/a" }, { label: "", href: "/b" }],
      main: [{ type: "panel", data: { title: "x".repeat(51) } }, { type: "faq", data: { items: [] } }],
    });
    assert.match(problems["cta.href"], /Use a site address/);
    assert.equal(problems["cards.1.label"], "This is required.");
    assert.match(problems["main.0.data.title"], /Too long/);
    assert.equal(problems["main.1.data.items"], "Add at least 1.");
  });

  it("asks to choose the kind of a block that has none", () => {
    assert.equal(validate(ROOT, { ...good(), main: [{ type: "bogus", data: {} }] }).main, undefined);
    assert.equal(validate(ROOT, { ...good(), main: [{ type: "bogus", data: {} }] })["main.0"], "Choose a kind.");
  });

  it("checks the id of a picked photo", () => {
    assert.equal(validate(ROOT, { ...good(), image: { mediaId: 0 } })["image.mediaId"], "More than 0.");
    assert.deepEqual(validate(ROOT, { ...good(), image: { mediaId: 5 }, coverMediaId: 7 }), {});
  });

  it("does not complain about optional fields left empty", () => {
    assert.deepEqual(validate(ROOT, { ...good(), slug: "", cta: undefined, year: undefined }), {});
  });
});

describe("server problems inside unions of blocks", () => {
  it("drops the kind the server writes between the item and its data", async () => {
    const { normalizeServerPath, variantKinds } = await import("./json-schema.ts");
    const kinds = variantKinds(ROOT);
    assert.deepEqual(kinds.sort(), ["faq", "panel"]);
    assert.equal(normalizeServerPath("main.0.panel.data.title", kinds), "main.0.data.title");
    assert.equal(normalizeServerPath("main.12.faq.data.items.0", kinds), "main.12.data.items.0");
    assert.equal(normalizeServerPath("main.0.panel.data", kinds), "main.0.data");
    // a field that happens to be called like a kind is left alone
    assert.equal(normalizeServerPath("image.mediaId", ["image"]), "image.mediaId");
    assert.equal(normalizeServerPath("title", kinds), "title");
  });
});
