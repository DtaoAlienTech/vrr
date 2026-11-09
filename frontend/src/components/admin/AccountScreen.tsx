"use client";

import { useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { api } from "@/lib/admin/api";
import { ApiProblem } from "@/lib/admin/problem";
import { useFeedback } from "./feedback";
import { useSession, useUser } from "./session";
import { Button, Card, Field, Heading, Notice } from "./ui";

type Setup = { secret: string; otpauthUri: string };

function ChangePassword() {
  const feedback = useFeedback();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (next.length < 12) return setError("Use at least 12 characters. A few words together make a strong password.");
    if (next !== again) return setError("The two new passwords are different.");
    setBusy(true);
    try {
      await api.post("/auth/change-password", { currentPassword: current, newPassword: next });
      setCurrent("");
      setNext("");
      setAgain("");
      feedback.ok("Password changed. Other devices were signed out.");
    } catch (problem) {
      setError(problem instanceof ApiProblem ? problem.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Change password">
      <form onSubmit={submit} noValidate className="aform-narrow">
        {error && <Notice kind="error">{error}</Notice>}
        <Field label="Current password" htmlFor="pw-current">
          <input id="pw-current" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
        </Field>
        <Field label="New password" htmlFor="pw-new" help="At least 12 characters. Not your name or e-mail.">
          <input id="pw-new" type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
        </Field>
        <Field label="New password again" htmlFor="pw-again">
          <input id="pw-again" type="password" autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} />
        </Field>
        <Button type="submit" busy={busy}>
          Change password
        </Button>
      </form>
    </Card>
  );
}

function groupKey(secret: string): string {
  return secret.replace(/(.{4})/g, "$1 ").trim();
}

function TwoFactor() {
  const user = useUser();
  const { reload } = useSession();
  const feedback = useFeedback();
  const [setup, setSetup] = useState<Setup | null>(null);
  const [code, setCode] = useState("");
  const [recovery, setRecovery] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [offPassword, setOffPassword] = useState("");
  const [offCode, setOffCode] = useState("");

  async function begin() {
    setBusy(true);
    setError(null);
    try {
      setSetup(await api.post<Setup>("/auth/totp/setup"));
    } catch (problem) {
      setError(problem instanceof ApiProblem ? problem.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  async function confirm(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await api.post<{ recoveryCodes: string[] }>("/auth/totp/enable", { code });
      setRecovery(result.recoveryCodes);
      setSetup(null);
      setCode("");
    } catch (problem) {
      setError(problem instanceof ApiProblem ? problem.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  async function turnOff(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/auth/totp/disable", { password: offPassword, code: offCode });
      setOffPassword("");
      setOffCode("");
      feedback.ok("Two-factor login is off.");
      await reload();
    } catch (problem) {
      setError(problem instanceof ApiProblem ? problem.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  if (recovery) {
    return (
      <Card title="Save your recovery codes">
        <Notice kind="warn">
          <b>These are shown only once.</b> Each code works one time if you lose your phone. Keep them somewhere safe, away from the phone.
        </Notice>
        <ul className="recovery" aria-label="Recovery codes">
          {recovery.map((item) => (
            <li key={item}>
              <code>{item}</code>
            </li>
          ))}
        </ul>
        <div className="btnrow">
          <Button
            variant="ghost"
            onClick={async () => {
              await navigator.clipboard.writeText(recovery.join("\n"));
              feedback.ok("Copied.");
            }}
          >
            Copy all
          </Button>
          <Button
            onClick={async () => {
              setRecovery(null);
              await reload();
            }}
          >
            I have saved them
          </Button>
        </div>
      </Card>
    );
  }

  if (user.totpEnabled) {
    return (
      <Card title="Two-factor login">
        <p>
          <span className="st ok">On</span> You sign in with a code from your authenticator app.
        </p>
        {user.role === "super_admin" ? (
          <p className="fhelp">Super admins must keep two-factor login on.</p>
        ) : (
          <form onSubmit={turnOff} noValidate className="aform-narrow">
            <p className="fhelp">To turn it off, confirm with your password and a current code.</p>
            {error && <Notice kind="error">{error}</Notice>}
            <Field label="Password" htmlFor="off-password">
              <input id="off-password" type="password" autoComplete="current-password" value={offPassword} onChange={(e) => setOffPassword(e.target.value)} />
            </Field>
            <Field label="Code from the app" htmlFor="off-code">
              <input id="off-code" inputMode="numeric" autoComplete="one-time-code" value={offCode} onChange={(e) => setOffCode(e.target.value)} />
            </Field>
            <Button type="submit" variant="ghost" busy={busy}>
              Turn off two-factor login
            </Button>
          </form>
        )}
      </Card>
    );
  }

  return (
    <Card title="Two-factor login">
      <p>
        <span className="st dr">Off</span> {user.role === "super_admin" ? "Required for super admins." : "Recommended: a stolen password alone is then not enough."}
      </p>
      {error && <Notice kind="error">{error}</Notice>}
      {!setup ? (
        <Button onClick={begin} busy={busy}>
          Set up two-factor login
        </Button>
      ) : (
        <form onSubmit={confirm} noValidate className="aform-narrow">
          <ol className="asteps">
            <li>
              Install an authenticator app on your phone (Google Authenticator, Microsoft Authenticator, Authy …).
            </li>
            <li>
              In the app choose “Add account” → “Enter a setup key”, and type this key:
              <div className="setupkey" data-testid="setup-key">
                {groupKey(setup.secret)}
              </div>
              <a className="alink" href={setup.otpauthUri}>
                On a phone? Open it in the authenticator app
              </a>
            </li>
            <li>Type the 6-digit code the app shows:</li>
          </ol>
          <Field label="6-digit code" htmlFor="setup-code">
            <input id="setup-code" inputMode="numeric" autoComplete="one-time-code" autoFocus value={code} onChange={(e) => setCode(e.target.value)} placeholder="123456" />
          </Field>
          <Button type="submit" busy={busy}>
            Turn on two-factor login
          </Button>
        </form>
      )}
    </Card>
  );
}

export function AccountScreen() {
  const user = useUser();
  const forced = useSearchParams().get("setup") === "1" && user.needsTotpSetup;
  return (
    <>
      <Heading title="My account" sub={`${user.name} · ${user.email}`} />
      {forced && (
        <Notice kind="warn">
          <b>One more step.</b> Super admins must use two-factor login. Set it up below to continue.
        </Notice>
      )}
      <TwoFactor />
      <ChangePassword />
    </>
  );
}
