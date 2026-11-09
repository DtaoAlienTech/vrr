"use client";

import { useMemo, useState } from "react";
import { api } from "@/lib/admin/api";
import { useApi } from "@/lib/admin/hooks";
import { prune, validate, type JsonSchema, type Problems } from "@/lib/admin/json-schema";
import { rememberBriefs } from "@/lib/admin/media-cache";
import { ApiProblem } from "@/lib/admin/problem";
import type { MediaBrief } from "@/lib/admin/types";
import { cx } from "@/lib/cx";
import { useDirty } from "./dirty";
import { useFeedback } from "./feedback";
import { useSitePaths } from "./ResourceScreens";
import { SchemaForm } from "./SchemaForm";
import { useUser } from "./session";
import { Button, Card, ErrorState, Heading, Loading, Notice } from "./ui";

type Json = Record<string, unknown>;
type Schemas = Record<string, { label: string; schema: JsonSchema }>;
type Settings = { groups: Record<string, Json | null>; media: Record<string, MediaBrief> };

const HELP: Record<string, string> = {
  brand: "The college name, logo and the lines in the top bar and footer.",
  contact: "Shown on the Contact page, the footer and the call button on phones. Leave out what you do not have yet.",
  social: "Links to the college on Facebook, Instagram, YouTube …",
  menu: "The links across the top of every page. The order here is the order on the website.",
  footer_courses: "The course links in the footer.",
  seo: "How the site appears on Google and when shared. “%s” is replaced by each page's own title.",
};

export function SettingsScreen() {
  const user = useUser();
  const settings = useApi<Settings>(user.role === "super_admin" ? "/admin/settings" : null);
  const schemas = useApi<Schemas>(user.role === "super_admin" ? "/admin/settings/schema" : null);
  const [group, setGroup] = useState("brand");

  if (user.role !== "super_admin") {
    return (
      <>
        <Heading title="Site settings" />
        <Notice kind="warn">Only a super admin can change the site settings.</Notice>
      </>
    );
  }
  const error = settings.error ?? schemas.error;
  if (error) return <ErrorState problem={error} retry={() => { settings.reload(); schemas.reload(); }} />;
  if (!settings.data || !schemas.data) return <Loading />;
  rememberBriefs(Object.values(settings.data.media));

  const names = Object.keys(schemas.data);
  return (
    <>
      <Heading title="Site settings" sub="The details that appear on every page of the website. Changes show within seconds." />
      <div className="tabs" role="tablist" aria-label="Settings groups">
        {names.map((name) => (
          <button
            key={name}
            type="button"
            role="tab"
            aria-selected={group === name}
            className={cx("tab", group === name && "on")}
            onClick={() => setGroup(name)}
          >
            {schemas.data![name].label}
          </button>
        ))}
      </div>
      <GroupForm key={group} name={group} schema={schemas.data[group].schema} initial={settings.data.groups[group] ?? {}} onSaved={settings.reload} />
    </>
  );
}

function GroupForm({ name, schema, initial, onSaved }: { name: string; schema: JsonSchema; initial: Json; onSaved: () => void }) {
  const feedback = useFeedback();
  const paths = useSitePaths();
  const [form, setForm] = useState<Json>(initial);
  const [saved, setSaved] = useState(() => JSON.stringify(prune(initial) ?? {}));
  const [submitted, setSubmitted] = useState(false);
  const [serverProblems, setServerProblems] = useState<Problems>({});
  const [busy, setBusy] = useState(false);
  const dirty = JSON.stringify(prune(form) ?? {}) !== saved;
  useDirty(dirty);
  const clientProblems = useMemo(() => validate(schema, form), [schema, form]);
  const problems = { ...(submitted ? clientProblems : {}), ...serverProblems };

  async function save() {
    setSubmitted(true);
    setServerProblems({});
    if (Object.keys(clientProblems).length > 0) return feedback.error("Please check the fields marked in red.");
    setBusy(true);
    try {
      const body = (prune(form) ?? {}) as Json;
      const clean = await api.put<Json>(`/admin/settings/${name}`, body);
      setForm(clean);
      setSaved(JSON.stringify(prune(clean) ?? {}));
      setSubmitted(false);
      feedback.ok("Saved. The website shows the change in a moment.");
      onSaved();
    } catch (problem) {
      if (problem instanceof ApiProblem) {
        setServerProblems(problem.fieldMap());
        feedback.error(problem.message);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <p className="fhelp">{HELP[name]}</p>
      <SchemaForm schema={schema} value={form} onChange={setForm} problems={problems} paths={paths} />
      <div className="btnrow">
        <Button onClick={save} busy={busy} disabled={!dirty}>
          Save
        </Button>
        {dirty && <span className="st dr">Unsaved changes</span>}
      </div>
    </Card>
  );
}
