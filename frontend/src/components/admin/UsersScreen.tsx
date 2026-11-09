"use client";

import { useState, type FormEvent } from "react";
import { api, withQuery } from "@/lib/admin/api";
import { formatDateTime, timeAgo } from "@/lib/admin/format";
import { useApi } from "@/lib/admin/hooks";
import { ApiProblem } from "@/lib/admin/problem";
import type { AuditEntry, ManagedUser, Role } from "@/lib/admin/types";
import { useFeedback } from "./feedback";
import { Modal } from "./Modal";
import { useUser } from "./session";
import { Button, Card, EmptyState, ErrorState, Field, Heading, Loading, Notice, StatusPill, Switch } from "./ui";

const ROLE: Record<Role, string> = { super_admin: "Super admin", editor: "Editor" };

function OnlySuperAdmin({ title }: { title: string }) {
  return (
    <>
      <Heading title={title} />
      <Notice kind="warn">Only a super admin can use this page.</Notice>
    </>
  );
}

function problemText(problem: unknown): string {
  return problem instanceof ApiProblem ? (problem.errors[0]?.message ?? problem.message) : "Something went wrong.";
}

function NewUser({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const feedback = useFeedback();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>("editor");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/admin/users", { email, name, role, password });
      feedback.ok("Account created. Give the person their password in person.");
      onDone();
      onClose();
    } catch (problem) {
      setError(problemText(problem));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate>
      {error && <Notice kind="error">{error}</Notice>}
      <Field label="Name" htmlFor="user-name" required>
        <input id="user-name" value={name} onChange={(event) => setName(event.target.value)} autoComplete="off" />
      </Field>
      <Field label="E-mail" htmlFor="user-email" required>
        <input id="user-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="off" />
      </Field>
      <Field label="Role" htmlFor="user-role" help="Editors change the content. Super admins also manage settings and accounts.">
        <select id="user-role" value={role} onChange={(event) => setRole(event.target.value as Role)}>
          <option value="editor">Editor</option>
          <option value="super_admin">Super admin</option>
        </select>
      </Field>
      <Field label="First password" htmlFor="user-password" required help="At least 12 characters. The person can change it in “My account”.">
        <input id="user-password" type="text" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="off" />
      </Field>
      <div className="btnrow">
        <Button type="submit" busy={busy}>
          Create account
        </Button>
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

function EditUser({ user, isSelf, onClose, onDone }: { user: ManagedUser; isSelf: boolean; onClose: () => void; onDone: () => void }) {
  const feedback = useFeedback();
  const [name, setName] = useState(user.name);
  const [role, setRole] = useState<Role>(user.role);
  const [active, setActive] = useState(user.isActive);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(work: () => Promise<unknown>, done: string, close = true) {
    setBusy(true);
    setError(null);
    try {
      await work();
      feedback.ok(done);
      onDone();
      if (close) onClose();
    } catch (problem) {
      setError(problemText(problem));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      {error && <Notice kind="error">{error}</Notice>}
      <Field label="Name" htmlFor="edit-name">
        <input id="edit-name" value={name} onChange={(event) => setName(event.target.value)} />
      </Field>
      <Field label="Role" htmlFor="edit-role" help={isSelf ? "You cannot change your own role." : undefined}>
        <select id="edit-role" value={role} disabled={isSelf} onChange={(event) => setRole(event.target.value as Role)}>
          <option value="editor">Editor</option>
          <option value="super_admin">Super admin</option>
        </select>
      </Field>
      <Switch label="The account can sign in" checked={active} disabled={isSelf} onChange={setActive} />
      <div className="btnrow">
        <Button busy={busy} onClick={() => run(() => api.put(`/admin/users/${user.id}`, { name, ...(isSelf ? {} : { role, isActive: active }) }), "Saved.")}>
          Save
        </Button>
      </div>
      {!isSelf && (
        <>
          <h3 className="asub">Forgot their password?</h3>
          <Field label="New password" htmlFor="edit-password" help="At least 12 characters. It signs the person out everywhere and unlocks the account.">
            <input id="edit-password" type="text" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="off" />
          </Field>
          <Button variant="ghost" busy={busy} disabled={password.length < 12} onClick={() => run(() => api.post(`/admin/users/${user.id}/reset-password`, { newPassword: password }), "Password changed.", false)}>
            Set the new password
          </Button>
          {user.totpEnabled && (
            <>
              <h3 className="asub">Lost phone?</h3>
              <Button
                variant="ghost"
                busy={busy}
                onClick={async () => {
                  const sure = await feedback.confirm({ title: "Turn off their two-factor login?", message: "They are signed out everywhere. A super admin must set it up again at the next sign-in.", confirmLabel: "Turn off" });
                  if (sure) await run(() => api.post(`/admin/users/${user.id}/reset-two-factor`), "Two-factor login turned off.", false);
                }}
              >
                Reset two-factor login
              </Button>
            </>
          )}
        </>
      )}
    </div>
  );
}

export function UsersScreen() {
  const me = useUser();
  const { data, error, loading, reload } = useApi<ManagedUser[]>(me.role === "super_admin" ? "/admin/users" : null);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<ManagedUser | null>(null);
  if (me.role !== "super_admin") return <OnlySuperAdmin title="Users" />;

  return (
    <>
      <Heading title="Users" sub="The people who can sign in to this admin panel." actions={<Button onClick={() => setAdding(true)}>+ Add a user</Button>} />
      {loading && !data && <Loading />}
      {error && <ErrorState problem={error} retry={reload} />}
      {data && (
        <Card>
          <table className="tbl">
            <thead>
              <tr>
                <th>Name</th>
                <th>Role</th>
                <th>Status</th>
                <th>Two-factor</th>
                <th>Last sign-in</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.map((user) => {
                const locked = user.lockedUntil && new Date(user.lockedUntil) > new Date();
                return (
                  <tr key={user.id}>
                    <td>
                      <b>{user.name}</b>
                      {user.id === me.id && <small> (you)</small>}
                      <br />
                      <small>{user.email}</small>
                    </td>
                    <td>{ROLE[user.role]}</td>
                    <td>
                      <StatusPill status={user.isActive ? "active" : "off"} />
                      {locked && <span className="st dr"> locked</span>}
                    </td>
                    <td>{user.totpEnabled ? <span className="st ok">On</span> : <span className="st dr">Off</span>}</td>
                    <td>{user.lastLoginAt ? timeAgo(user.lastLoginAt) : "never"}</td>
                    <td>
                      <button type="button" className="alink" onClick={() => setEditing(user)} aria-label={`Edit ${user.name}`}>
                        Edit
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      )}
      <Modal open={adding} onClose={() => setAdding(false)} title="Add a user">
        {adding && <NewUser onClose={() => setAdding(false)} onDone={reload} />}
      </Modal>
      <Modal open={editing !== null} onClose={() => setEditing(null)} title={editing ? `Edit ${editing.name}` : "Edit"}>
        {editing && <EditUser key={editing.id} user={editing} isSelf={editing.id === me.id} onClose={() => setEditing(null)} onDone={reload} />}
      </Modal>
    </>
  );
}

// ---------------------------------------------------------------- activity log

const WORDS: Record<string, string> = {
  login: "signed in",
  login_failed: "wrong password or code",
  login_refused: "sign-in refused (locked or switched off)",
  logout: "signed out",
  account_locked: "account locked after too many tries",
  password_changed: "changed their password",
  password_change_failed: "wrong current password",
  totp_enabled: "turned on two-factor login",
  totp_disabled: "turned off two-factor login",
  refresh_token_reuse: "a copied login was used: signed out everywhere",
  media_upload: "uploaded a file",
  media_update: "changed a file's description",
  media_delete: "deleted a file",
  user_create: "created an account",
  user_update: "changed an account",
  user_password_reset: "reset a password",
  user_two_factor_reset: "reset two-factor login",
  settings_update: "changed site settings",
  revision_restore: "restored an older version",
  enquiries_export: "downloaded the enquiries",
};

function describe(entry: AuditEntry): string {
  const base = WORDS[entry.action] ?? entry.action.replace(/_/g, " ");
  if (entry.entity && !WORDS[entry.action]) return `${base}${entry.entityId ? ` #${entry.entityId}` : ""}`;
  return base;
}

export function ActivityLogScreen() {
  const me = useUser();
  const users = useApi<ManagedUser[]>(me.role === "super_admin" ? "/admin/users" : null);
  const first = useApi<AuditEntry[]>(me.role === "super_admin" ? withQuery("/admin/audit-log", { limit: 50 }) : null);
  const [more, setMore] = useState<AuditEntry[]>([]);
  const [done, setDone] = useState(false);
  if (me.role !== "super_admin") return <OnlySuperAdmin title="Activity log" />;
  const names = new Map((users.data ?? []).map((user) => [user.id, user.name]));
  const entries = [...(first.data ?? []), ...more];

  async function older() {
    const last = entries.at(-1);
    if (!last) return;
    const page = await api.get<AuditEntry[]>(withQuery("/admin/audit-log", { limit: 50, before_id: last.id }));
    setMore((current) => [...current, ...page]);
    if (page.length < 50) setDone(true);
  }

  return (
    <>
      <Heading title="Activity log" sub="Who did what, and from where. Passwords and the content of changes are never recorded here." />
      {first.loading && !first.data && <Loading />}
      {first.error && <ErrorState problem={first.error} retry={first.reload} />}
      {first.data && (
        <Card>
          {entries.length === 0 ? (
            <EmptyState>Nothing recorded yet.</EmptyState>
          ) : (
            <table className="tbl">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Who</th>
                  <th>What</th>
                  <th>From</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr key={entry.id}>
                    <td>
                      <time dateTime={entry.createdAt}>{formatDateTime(entry.createdAt)}</time>
                    </td>
                    <td>{entry.userId ? (names.get(entry.userId) ?? `#${entry.userId}`) : "—"}</td>
                    <td>{describe(entry)}</td>
                    <td>
                      <small>{entry.ip ?? "—"}</small>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {!done && first.data.length >= 50 && (
            <div className="btnrow">
              <Button variant="ghost" onClick={older}>
                Show older entries
              </Button>
            </div>
          )}
        </Card>
      )}
    </>
  );
}
