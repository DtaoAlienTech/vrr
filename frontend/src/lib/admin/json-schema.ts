// The admin forms are built from the JSON Schemas that the backend publishes (the same models
// that validate every save), so a new field is one line in the backend and appears here by itself.
// This file is the pure logic: resolving schemas, default values, validation and cleaning.
import { isSafeHref, LINK_HELP } from "./links.ts";
import { isEmptyDoc } from "./rich-text.ts";

export type JsonSchema = {
  type?: string;
  properties?: Record<string, JsonSchema>;
  required?: string[];
  items?: JsonSchema;
  enum?: unknown[];
  const?: unknown;
  anyOf?: JsonSchema[];
  oneOf?: JsonSchema[];
  allOf?: JsonSchema[];
  $ref?: string;
  $defs?: Record<string, JsonSchema>;
  title?: string;
  description?: string;
  default?: unknown;
  minLength?: number;
  maxLength?: number;
  pattern?: string;
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  minItems?: number;
  maxItems?: number;
  format?: string;
  discriminator?: { propertyName: string; mapping?: Record<string, string> };
  "x-widget"?: string;
};

// ---------- reading schemas ----------

function lookup(root: JsonSchema, ref: string): JsonSchema {
  const match = /^#\/\$defs\/(.+)$/.exec(ref);
  const target = match ? root.$defs?.[match[1]] : undefined;
  if (!target) throw new Error(`Unknown schema reference ${ref}`);
  return target;
}

/** Follows $ref (and single-item allOf), keeping the description/default written next to it. */
export function deref(schema: JsonSchema, root: JsonSchema): JsonSchema {
  let current = schema;
  for (let guard = 0; guard < 20; guard += 1) {
    if (current.$ref) {
      const { $ref, ...rest } = current;
      current = { ...lookup(root, $ref), ...rest };
    } else if (current.allOf?.length === 1) {
      const { allOf, ...rest } = current;
      current = { ...deref(allOf[0], root), ...rest };
    } else {
      return current;
    }
  }
  throw new Error("Schema references loop");
}

const isNull = (schema: JsonSchema) => schema.type === "null";

/** "Optional X" is written as anyOf [X, null]. Returns X (with the outer description/default). */
export function unwrap(schema: JsonSchema, root: JsonSchema): { schema: JsonSchema; optional: boolean } {
  const outer = deref(schema, root);
  const options = outer.anyOf ?? outer.oneOf;
  if (!options || !options.some(isNull)) return { schema: outer, optional: false };
  const rest = options.filter((option) => !isNull(option));
  if (rest.length === 1) {
    const inner = deref(rest[0], root);
    return {
      optional: true,
      schema: {
        ...inner,
        title: outer.title ?? inner.title,
        description: outer.description ?? inner.description,
        default: outer.default ?? inner.default,
      },
    };
  }
  const { anyOf, oneOf, ...others } = outer;
  void anyOf;
  void oneOf;
  return { optional: true, schema: { ...others, anyOf: rest } };
}

export type Variant = { key: string; schema: JsonSchema };

/** The choices of a union of objects told apart by a "type" field (for example the blocks that can
 * sit inside a two-column section). Null when the schema is not such a union. */
export function variantsOf(schema: JsonSchema, root: JsonSchema): Variant[] | null {
  const options = schema.oneOf ?? schema.anyOf;
  if (!options || options.length < 2) return null;
  const variants: Variant[] = [];
  for (const option of options) {
    const resolved = deref(option, root);
    const key = resolved.properties?.type?.const;
    if (typeof key !== "string") return null;
    variants.push({ key, schema: resolved });
  }
  return variants;
}

export type FieldKind =
  | "text"
  | "textarea"
  | "link"
  | "select"
  | "number"
  | "boolean"
  | "datetime"
  | "richtext"
  | "media-pick"
  | "media-image"
  | "media-pdf"
  | "department"
  | "object"
  | "list-text"
  | "list-object"
  | "union"
  | "unknown";

export const TEXTAREA_FROM = 200; // longer text boxes are drawn as a paragraph box

export function kindOf(schema: JsonSchema, root: JsonSchema): FieldKind {
  const widget = schema["x-widget"];
  if (widget === "richtext") return "richtext";
  if (widget === "media") return "media-pick";
  if (widget === "media-image" || widget === "media-pdf" || widget === "department") return widget;
  if (variantsOf(schema, root)) return "union";
  if (schema.enum) return "select";
  switch (schema.type) {
    case "object":
      return "object";
    case "boolean":
      return "boolean";
    case "integer":
    case "number":
      return "number";
    case "array": {
      const item = unwrap(schema.items ?? {}, root).schema;
      if (item.type === "string") return "list-text";
      return item.type === "object" || variantsOf(item, root) ? "list-object" : "unknown";
    }
    case "string":
      if (widget === "link") return "link";
      if (schema.format === "date-time") return "datetime";
      return (schema.maxLength ?? 0) > TEXTAREA_FROM ? "textarea" : "text";
    default:
      return "unknown";
  }
}

// ---------- values ----------

export type FormValue = unknown;
type Json = Record<string, unknown>;
const isObject = (value: unknown): value is Json =>
  typeof value === "object" && value !== null && !Array.isArray(value);

/** A new, empty value for a schema. Required lists start empty, required text starts unset. */
export function initialValue(schema: JsonSchema, root: JsonSchema): FormValue {
  const { schema: s } = unwrap(schema, root);
  if (s.default !== undefined && s.default !== null) return structuredClone(s.default);
  if (s.type === "boolean") return false;
  if (s.type === "array") return [];
  if (s.type === "object" && s["x-widget"] !== "richtext" && s.properties) {
    const value: Json = {};
    for (const [name, property] of Object.entries(s.properties)) {
      const inner = unwrap(property, root);
      const required = s.required?.includes(name) ?? false;
      const hasDefault = inner.schema.default !== undefined && inner.schema.default !== null;
      if (required || hasDefault) {
        const initial = initialValue(property, root);
        if (initial !== undefined) value[name] = initial;
      }
    }
    return value;
  }
  return undefined;
}

/** The value of a new item of a union of blocks: its type, plus empty data. */
export function newVariantValue(variant: Variant, root: JsonSchema): Json {
  return {
    ...(initialValue(variant.schema, root) as Json),
    type: variant.key,
  };
}

function isBlank(value: unknown): boolean {
  return value === undefined || value === null || (typeof value === "string" && value.trim() === "");
}

/** What is sent to the server: no empty text, no unset fields, no empty optional objects. */
export function prune(value: FormValue): FormValue {
  if (typeof value === "string") return value.trim() === "" ? undefined : value;
  if (Array.isArray(value)) return value.map(prune).filter((item) => item !== undefined);
  if (isObject(value)) {
    if (value.type === "doc") return value; // rich text is cleaned by its own function
    const result: Json = {};
    for (const [key, item] of Object.entries(value)) {
      const cleaned = prune(item);
      if (cleaned !== undefined) result[key] = cleaned;
      // a block's "data" may legitimately be empty (for example the contact details block)
      else if (key === "data" && isObject(item)) result[key] = {};
    }
    return Object.keys(result).length > 0 ? result : undefined;
  }
  return value;
}

// ---------- validation ----------

export type Problems = Record<string, string>;

const KNOWN_PATTERNS: Record<string, string> = {
  "^[a-z0-9]+(-[a-z0-9]+)*$": "Use lower-case letters, numbers and single hyphens (like open-day-2026).",
  "^[A-Za-z0-9_-]{6,20}$": "That does not look like a YouTube video id.",
  ".*%s.*": "It must contain %s (where the page title goes).",
};

function textProblem(schema: JsonSchema, value: string): string | undefined {
  if (schema.minLength !== undefined && value.length < schema.minLength) {
    return `Use at least ${schema.minLength} characters.`;
  }
  if (schema.maxLength !== undefined && value.length > schema.maxLength) {
    return `Too long: ${value.length} of at most ${schema.maxLength} characters.`;
  }
  if (schema["x-widget"] === "link" && !isSafeHref(value)) return LINK_HELP;
  if (schema.pattern) {
    try {
      if (!new RegExp(schema.pattern).test(value)) {
        return KNOWN_PATTERNS[schema.pattern] ?? "That is not in the expected format.";
      }
    } catch {
      // a pattern this browser cannot read: the server will check it
    }
  }
  if (schema.format === "date-time" && Number.isNaN(Date.parse(value))) return "Enter a valid date and time.";
  return undefined;
}

function numberProblem(schema: JsonSchema, value: number): string | undefined {
  if (!Number.isFinite(value)) return "Enter a number.";
  if (schema.type === "integer" && !Number.isInteger(value)) return "Enter a whole number.";
  if (schema.minimum !== undefined && value < schema.minimum) return `At least ${schema.minimum}.`;
  if (schema.exclusiveMinimum !== undefined && value <= schema.exclusiveMinimum) {
    return `More than ${schema.exclusiveMinimum}.`;
  }
  if (schema.maximum !== undefined && value > schema.maximum) return `At most ${schema.maximum}.`;
  return undefined;
}

/** Problems keyed like the server's: "title", "primaryCta.href", "items.0.label". */
export function validate(schema: JsonSchema, value: FormValue, root: JsonSchema = schema, path = ""): Problems {
  const problems: Problems = {};
  const add = (key: string, message: string) => {
    if (!(key in problems)) problems[key] = message;
  };
  const { schema: s } = unwrap(schema, root);
  const kind = kindOf(s, root);
  const key = path;

  if (kind === "richtext") return problems; // required-ness is decided by the caller

  if (kind === "union") {
    const variants = variantsOf(s, root) ?? [];
    if (!isObject(value)) return problems;
    const chosen = variants.find((v) => v.key === value.type);
    if (!chosen) {
      add(key, "Choose a kind.");
      return problems;
    }
    return validate(chosen.schema, value, root, path);
  }

  if (kind === "object" || kind === "media-pick") {
    if (!isObject(value)) return problems;
    for (const [name, property] of Object.entries(s.properties ?? {})) {
      const child = path ? `${path}.${name}` : name;
      const inner = unwrap(property, root);
      const item = value[name];
      const required = (s.required ?? []).includes(name);
      const innerKind = kindOf(inner.schema, root);
      const missing = innerKind === "richtext" ? item === undefined || isEmptyDoc(item) : isBlank(item);
      if (required && !inner.optional && missing && innerKind !== "boolean") {
        add(child, "This is required.");
        continue;
      }
      if (isBlank(item)) continue;
      Object.assign(problems, validate(property, item, root, child));
    }
    return problems;
  }

  if (kind === "list-text" || kind === "list-object") {
    if (!Array.isArray(value)) return problems;
    if (s.minItems !== undefined && value.length < s.minItems) add(key, `Add at least ${s.minItems}.`);
    if (s.maxItems !== undefined && value.length > s.maxItems) add(key, `At most ${s.maxItems} items.`);
    value.forEach((item, index) => {
      Object.assign(problems, validate(s.items ?? {}, item, root, path ? `${path}.${index}` : String(index)));
    });
    return problems;
  }

  if (typeof value === "string") {
    if (s.enum && !s.enum.includes(value)) add(key, "Choose one of the options.");
    else {
      const message = textProblem(s, value);
      if (message) add(key, message);
    }
  } else if (typeof value === "number") {
    const message = numberProblem(s, value);
    if (message) add(key, message);
  }
  return problems;
}

/** Does a field of this schema have to be filled in? */
export function isRequired(parent: JsonSchema, name: string, root: JsonSchema): boolean {
  const property = parent.properties?.[name];
  if (!property) return false;
  return (parent.required ?? []).includes(name) && !unwrap(property, root).optional;
}

// ---------- labels ----------

/** "primaryCta" -> "Primary cta". A dictionary of friendlier names lives in labels.ts. */
export function humanize(name: string): string {
  const spaced = name.replace(/([a-z0-9])([A-Z])/g, "$1 $2").replace(/[_-]+/g, " ").trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1).toLowerCase();
}

export function describeEnum(value: unknown): string {
  return humanize(String(value));
}

export function joinPath(parent: string, key: string | number): string {
  return parent === "" ? String(key) : `${parent}.${key}`;
}

// ---------- server problems ----------

/** The server names a field inside a union of blocks with the block's kind in the path
 * ("main.0.panel.data.title"); the form has no such step ("main.0.data.title"). */
export function normalizeServerPath(path: string, kinds: Iterable<string>): string {
  let result = path;
  for (const kind of kinds) {
    result = result.replace(new RegExp(`(^|\\.)(\\d+)\\.${kind.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\.data(\\.|$)`), "$1$2.data$3");
  }
  return result;
}

/** Every "type" value of the unions of blocks in a schema. */
export function variantKinds(root: JsonSchema): string[] {
  const kinds = new Set<string>();
  for (const def of Object.values(root.$defs ?? {})) {
    const key = def.properties?.type?.const;
    if (typeof key === "string") kinds.add(key);
  }
  return [...kinds];
}
