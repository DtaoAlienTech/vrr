"use client";

import dynamic from "next/dynamic";
import { createContext, useContext, useId, useState, type ReactNode } from "react";
import { useApi } from "@/lib/admin/hooks";
import { fromLocalInput, toLocalInput } from "@/lib/admin/format";
import {
  initialValue,
  isRequired,
  kindOf,
  newVariantValue,
  unwrap,
  variantsOf,
  type FormValue,
  type JsonSchema,
  type Problems,
  type Variant,
} from "@/lib/admin/json-schema";
import { enumLabel, labelFor, SECTION_LABELS } from "@/lib/admin/labels";
import { cx } from "@/lib/cx";
import { MediaChooser, useMediaPicker } from "./media";
import { Button, Field, Loading, Switch } from "./ui";

// The editor is loaded only when a form needs it (it is a large library).
const RichTextEditor = dynamic(() => import("./RichTextEditor").then((m) => m.RichTextEditor), {
  ssr: false,
  loading: () => <Loading label="Loading the editor…" />,
});

type Json = Record<string, unknown>;
const isObject = (value: unknown): value is Json => typeof value === "object" && value !== null && !Array.isArray(value);

type Context = { root: JsonSchema; problems: Problems; disabled: boolean; paths: string[] };
const FormContext = createContext<Context | null>(null);
const useForm = () => {
  const context = useContext(FormContext);
  if (!context) throw new Error("Used outside SchemaForm");
  return context;
};

const joinPath = (parent: string, key: string | number) => (parent === "" ? String(key) : `${parent}.${key}`);

// ---------------------------------------------------------------- public component

type Props = {
  /** The JSON Schema of the form (an object); the one published by the backend. */
  schema: JsonSchema;
  value: Json;
  onChange: (value: Json) => void;
  /** Problems to show, keyed by field path ("title", "primaryCta.href"). */
  problems?: Problems;
  /** Show only these fields (in the order of the schema), or hide some. */
  only?: string[];
  exclude?: string[];
  disabled?: boolean;
  /** Site addresses offered as suggestions in link fields. */
  paths?: string[];
  /** The schema to resolve references against (when `schema` is a part of a bigger one). */
  root?: JsonSchema;
};

export function SchemaForm({ schema, value, onChange, problems = {}, only, exclude, disabled = false, paths = [], root }: Props) {
  const context: Context = { root: root ?? schema, problems, disabled, paths };
  const object = unwrap(schema, context.root).schema;
  return (
    <FormContext.Provider value={context}>
      <ObjectFields schema={object} value={value} onChange={onChange} path="" only={only} exclude={exclude} />
    </FormContext.Provider>
  );
}

// ---------------------------------------------------------------- objects

function ObjectFields({ schema, value, onChange, path, only, exclude }: { schema: JsonSchema; value: Json; onChange: (value: Json) => void; path: string; only?: string[]; exclude?: string[] }) {
  const names = Object.keys(schema.properties ?? {}).filter((name) => (!only || only.includes(name)) && !exclude?.includes(name));
  return (
    <>
      {names.map((name) => (
        <Property
          key={name}
          name={name}
          parent={schema}
          schema={schema.properties![name]}
          value={value[name]}
          path={joinPath(path, name)}
          onChange={(next) => {
            const copy = { ...value };
            if (next === undefined) delete copy[name];
            else copy[name] = next;
            onChange(copy);
          }}
        />
      ))}
    </>
  );
}

function Property({ name, parent, schema, value, path, onChange }: { name: string; parent: JsonSchema; schema: JsonSchema; value: FormValue; path: string; onChange: (value: FormValue) => void }) {
  const { root, problems, disabled, paths } = useForm();
  const inner = unwrap(schema, root);
  const s = inner.schema;
  const kind = kindOf(s, root);
  const required = isRequired(parent, name, root);
  const label = labelFor(name, s.title);
  const error = problems[path];
  const id = useId();
  const help = s.description?.split("\n")[0];

  switch (kind) {
    case "object":
      return <Group label={label} help={help} schema={s} optional={inner.optional} value={value} path={path} onChange={onChange} />;
    case "media-pick":
      return (
        <Field label={label} required={required} error={error} help={help}>
          <MediaChooser id={isObject(value) && typeof value.mediaId === "number" ? value.mediaId : undefined} kind="image" label={label} optional={!required} onChange={(mediaId) => onChange(mediaId === undefined ? undefined : { mediaId })} />
        </Field>
      );
    case "media-image":
    case "media-pdf":
      return (
        <Field label={label} required={required} error={error} help={help}>
          <MediaChooser id={typeof value === "number" ? value : undefined} kind={kind === "media-pdf" ? "pdf" : "image"} label={label} optional={!required} onChange={onChange} />
        </Field>
      );
    case "richtext":
      return (
        <Field label={label} htmlFor={id} required={required} error={error} help={help}>
          <RichTextEditor id={id} label={label} invalid={Boolean(error)} value={isObject(value) ? (value as never) : undefined} onChange={(doc) => onChange(doc)} />
        </Field>
      );
    case "list-text":
      return <TextList label={label} help={help} schema={s} value={Array.isArray(value) ? (value as string[]) : []} path={path} onChange={onChange} />;
    case "list-object":
      return <ObjectList label={label} help={help} schema={s} value={Array.isArray(value) ? value : []} path={path} onChange={onChange} />;
    case "boolean":
      return (
        <div className="afield">
          <Switch id={id} label={label} checked={value === true} disabled={disabled} onChange={onChange} />
          {error ? <p className="ferr">{error}</p> : help && <p className="fhelp">{help}</p>}
        </div>
      );
    case "select": {
      const options = s.enum ?? [];
      if (options.length === 2 && options.includes("draft") && options.includes("published")) {
        return <Switch id={id} label={label} checked={value === "published"} disabled={disabled} onChange={(on) => onChange(on ? "published" : "draft")} />;
      }
      return (
        <Field label={label} htmlFor={id} required={required} error={error} help={help}>
          <select id={id} value={typeof value === "string" ? value : ""} disabled={disabled} onChange={(event) => onChange(event.target.value === "" ? undefined : event.target.value)}>
            {(!required || value === undefined) && <option value="">{required ? "Choose…" : "—"}</option>}
            {options.map((option) => (
              <option key={String(option)} value={String(option)}>
                {enumLabel(option)}
              </option>
            ))}
          </select>
        </Field>
      );
    }
    case "department":
      return (
        <Field label={label} htmlFor={id} required={required} error={error} help={help}>
          <DepartmentSelect id={id} value={typeof value === "number" ? value : undefined} disabled={disabled} onChange={onChange} />
        </Field>
      );
    case "number":
      return (
        <Field label={label} htmlFor={id} required={required} error={error} help={help}>
          <input
            id={id}
            type="number"
            inputMode="numeric"
            value={typeof value === "number" ? value : ""}
            min={s.minimum}
            max={s.maximum}
            disabled={disabled}
            onChange={(event) => onChange(event.target.value === "" ? undefined : Number(event.target.value))}
          />
        </Field>
      );
    case "datetime":
      return (
        <Field label={label} htmlFor={id} required={required} error={error} help={help ?? "India time"}>
          <input id={id} type="datetime-local" value={toLocalInput(typeof value === "string" ? value : undefined)} disabled={disabled} onChange={(event) => onChange(event.target.value ? fromLocalInput(event.target.value) : undefined)} />
        </Field>
      );
    case "textarea":
      return (
        <Field label={label} htmlFor={id} required={required} error={error} help={help} count={{ length: typeof value === "string" ? value.length : 0, max: s.maxLength ?? 0 }}>
          <textarea id={id} value={typeof value === "string" ? value : ""} rows={4} disabled={disabled} onChange={(event) => onChange(event.target.value)} />
        </Field>
      );
    case "link":
      return (
        <Field label={label} htmlFor={id} required={required} error={error} help={help ?? "A page of the site (/about), https://…, mailto: or tel:"}>
          <input id={id} type="text" list={`${id}-paths`} value={typeof value === "string" ? value : ""} disabled={disabled} onChange={(event) => onChange(event.target.value)} autoComplete="off" />
          <datalist id={`${id}-paths`}>
            {paths.map((p) => (
              <option key={p} value={p} />
            ))}
          </datalist>
        </Field>
      );
    case "text":
      return (
        <Field label={label} htmlFor={id} required={required} error={error} help={help} count={s.maxLength ? { length: typeof value === "string" ? value.length : 0, max: s.maxLength } : undefined}>
          <input id={id} type="text" value={typeof value === "string" ? value : ""} disabled={disabled} onChange={(event) => onChange(event.target.value)} />
        </Field>
      );
    default:
      return null; // a kind of field this form does not know: the server still checks the data
  }
}

function DepartmentSelect({ id, value, disabled, onChange }: { id: string; value: number | undefined; disabled: boolean; onChange: (value: number | undefined) => void }) {
  const { data } = useApi<{ id: number; name: string }[]>("/admin/departments");
  return (
    <select id={id} value={value ?? ""} disabled={disabled || !data} onChange={(event) => onChange(event.target.value ? Number(event.target.value) : undefined)}>
      <option value="">Choose…</option>
      {data?.map((department) => (
        <option key={department.id} value={department.id}>
          {department.name}
        </option>
      ))}
    </select>
  );
}

// ---------------------------------------------------------------- nested group (optional object)

function Group({ label, help, schema, optional, value, path, onChange }: { label: string; help?: string; schema: JsonSchema; optional: boolean; value: FormValue; path: string; onChange: (value: FormValue) => void }) {
  const { disabled } = useForm();
  if (optional && value === undefined) {
    return (
      <div className="afield">
        <Button variant="ghost" disabled={disabled} onClick={() => onChange({})}>
          + Add {label.toLowerCase()}
        </Button>
        {help && <p className="fhelp">{help}</p>}
      </div>
    );
  }
  return (
    <fieldset className="afieldset">
      <legend>{label}</legend>
      {help && <p className="fhelp">{help}</p>}
      <ObjectFields schema={schema} value={isObject(value) ? value : {}} onChange={onChange} path={path} />
      {optional && (
        <Button variant="ghost" disabled={disabled} onClick={() => onChange(undefined)}>
          Remove {label.toLowerCase()}
        </Button>
      )}
    </fieldset>
  );
}

// ---------------------------------------------------------------- lists

function move<T>(list: T[], from: number, to: number): T[] {
  if (to < 0 || to >= list.length) return list;
  const copy = [...list];
  const [item] = copy.splice(from, 1);
  copy.splice(to, 0, item);
  return copy;
}

function ListFrame({ label, help, error, children, footer }: { label: string; help?: string; error?: string; children: ReactNode; footer: ReactNode }) {
  return (
    <fieldset className={cx("afieldset", error && "has-error")}>
      <legend>{label}</legend>
      {help && <p className="fhelp">{help}</p>}
      {children}
      {error && <p className="ferr">{error}</p>}
      <div className="alist-add">{footer}</div>
    </fieldset>
  );
}

function TextList({ label, help, schema, value, path, onChange }: { label: string; help?: string; schema: JsonSchema; value: string[]; path: string; onChange: (value: FormValue) => void }) {
  const { problems, disabled } = useForm();
  const full = schema.maxItems !== undefined && value.length >= schema.maxItems;
  return (
    <ListFrame
      label={label}
      help={help}
      error={problems[path]}
      footer={
        <Button variant="ghost" disabled={disabled || full} onClick={() => onChange([...value, ""])}>
          + Add
        </Button>
      }
    >
      {value.map((item, index) => (
        <div className="alistrow" key={index}>
          <input type="text" value={item} aria-label={`${label} ${index + 1}`} disabled={disabled} onChange={(event) => onChange(value.map((v, i) => (i === index ? event.target.value : v)))} />
          <RowButtons index={index} count={value.length} onMove={(to) => onChange(move(value, index, to))} onRemove={() => onChange(value.filter((_, i) => i !== index))} />
          {problems[joinPath(path, index)] && <p className="ferr">{problems[joinPath(path, index)]}</p>}
        </div>
      ))}
    </ListFrame>
  );
}

function RowButtons({ index, count, onMove, onRemove }: { index: number; count: number; onMove: (to: number) => void; onRemove: () => void }) {
  const { disabled } = useForm();
  return (
    <span className="rowbtns">
      <button type="button" className="tbtn" aria-label="Move up" disabled={disabled || index === 0} onClick={() => onMove(index - 1)}>
        ↑
      </button>
      <button type="button" className="tbtn" aria-label="Move down" disabled={disabled || index === count - 1} onClick={() => onMove(index + 1)}>
        ↓
      </button>
      <button type="button" className="tbtn tbtn-danger" aria-label="Remove" disabled={disabled} onClick={onRemove}>
        ×
      </button>
    </span>
  );
}

const SUMMARY_KEYS = ["title", "label", "question", "heading", "headline", "name", "caption", "value", "text"];

function summaryOf(item: unknown, fallback: string): string {
  if (isObject(item)) {
    for (const key of SUMMARY_KEYS) {
      const candidate = item[key];
      if (typeof candidate === "string" && candidate.trim()) return candidate.length > 60 ? `${candidate.slice(0, 57)}…` : candidate;
    }
    if (isObject(item.data)) return summaryOf(item.data, fallback);
  }
  return fallback;
}

/** A list whose items are photos ({mediaId, caption} or {media: {mediaId}, caption}) can be filled in bulk. */
function photoShape(itemSchema: JsonSchema, root: JsonSchema): "mediaId" | "media" | null {
  const properties = itemSchema.properties ?? {};
  if (properties.mediaId && kindOf(unwrap(properties.mediaId, root).schema, root) === "media-image") return "mediaId";
  if (properties.media && kindOf(unwrap(properties.media, root).schema, root) === "media-pick") return "media";
  return null;
}

function ObjectList({ label, help, schema, value, path, onChange }: { label: string; help?: string; schema: JsonSchema; value: unknown[]; path: string; onChange: (value: FormValue) => void }) {
  const { root, problems, disabled } = useForm();
  const picker = useMediaPicker();
  const itemSchema = unwrap(schema.items ?? {}, root).schema;
  const variants = variantsOf(itemSchema, root);
  const shape = variants ? null : photoShape(itemSchema, root);

  async function addPhotos() {
    const chosen = await picker.pickMany("image");
    if (chosen.length === 0) return;
    const room = schema.maxItems !== undefined ? Math.max(0, schema.maxItems - value.length) : chosen.length;
    const fresh = chosen.slice(0, room).map((photo) => ({
      ...(initialValue(itemSchema, root) as Json),
      ...(shape === "media" ? { media: { mediaId: photo.id } } : { mediaId: photo.id }),
    }));
    onChange([...value, ...fresh]);
  }
  const [kind, setKind] = useState(variants?.[0]?.key ?? "");
  const full = schema.maxItems !== undefined && value.length >= schema.maxItems;

  const add = () => {
    if (variants) {
      const variant = variants.find((v) => v.key === kind) ?? variants[0];
      onChange([...value, newVariantValue(variant, root)]);
    } else {
      onChange([...value, initialValue(itemSchema, root) ?? {}]);
    }
  };

  return (
    <ListFrame
      label={label}
      help={help}
      error={problems[path]}
      footer={
        <>
          {variants && (
            <select value={kind} onChange={(event) => setKind(event.target.value)} aria-label={`Kind of ${label.toLowerCase()} to add`} disabled={disabled}>
              {variants.map((variant) => (
                <option key={variant.key} value={variant.key}>
                  {SECTION_LABELS[variant.key] ?? enumLabel(variant.key)}
                </option>
              ))}
            </select>
          )}
          {shape && (
            <Button variant="primary" disabled={disabled || full} onClick={addPhotos}>
              Choose or upload photos
            </Button>
          )}
          <Button variant="ghost" disabled={disabled || full} onClick={add}>
            + Add {variants ? "" : "item"}
          </Button>
        </>
      }
    >
      {value.length === 0 && <p className="fhelp">Nothing here yet.</p>}
      {value.map((item, index) => {
        const itemPath = joinPath(path, index);
        const change = (next: unknown) => onChange(value.map((v, i) => (i === index ? next : v)));
        return (
          <div className="alistitem" key={index}>
            <div className="alistitem-head">
              <b>{variants && isObject(item) ? `${SECTION_LABELS[String(item.type)] ?? enumLabel(item.type)}: ` : `${index + 1}. `}{summaryOf(item, "New item")}</b>
              <RowButtons index={index} count={value.length} onMove={(to) => onChange(move(value, index, to))} onRemove={() => onChange(value.filter((_, i) => i !== index))} />
            </div>
            {problems[itemPath] && <p className="ferr">{problems[itemPath]}</p>}
            {variants ? <UnionItem variants={variants} value={isObject(item) ? item : {}} path={itemPath} onChange={change} /> : <ObjectFields schema={itemSchema} value={isObject(item) ? item : {}} onChange={change} path={itemPath} />}
          </div>
        );
      })}
    </ListFrame>
  );
}

function UnionItem({ variants, value, path, onChange }: { variants: Variant[]; value: Json; path: string; onChange: (value: Json) => void }) {
  const { root, disabled } = useForm();
  const variant = variants.find((v) => v.key === value.type);
  if (!variant) return <p className="ferr">Unknown kind “{String(value.type)}”.</p>;
  const dataSchema = unwrap(variant.schema.properties?.data ?? {}, root).schema;
  const data = isObject(value.data) ? value.data : {};
  return (
    <>
      {"isVisible" in (variant.schema.properties ?? {}) && <Switch label="Shown on the page" checked={value.isVisible !== false} disabled={disabled} onChange={(visible) => onChange({ ...value, isVisible: visible })} />}
      <ObjectFields schema={dataSchema} value={data} onChange={(next) => onChange({ ...value, data: next })} path={joinPath(path, "data")} />
    </>
  );
}
