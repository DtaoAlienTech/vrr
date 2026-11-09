"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { api } from "@/lib/admin/api";
import { ApiProblem } from "@/lib/admin/problem";
import type { SessionInfo } from "@/lib/admin/types";
import { safeNext, useSession } from "./session";
import { Button, Field, Notice } from "./ui";

/** Email and password, then (when two-factor login is on) the six-digit code or a recovery code. */
export function LoginForm() {
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const { state, start } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [needsCode, setNeedsCode] = useState(false);
  const [useRecovery, setUseRecovery] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (state.status === "ready") router.replace(next);
  }, [state.status, router, next]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body: Record<string, string> = { email, password };
      if (needsCode && code.trim()) body[useRecovery ? "recoveryCode" : "totpCode"] = code.trim();
      const info = await api.post<SessionInfo>("/auth/login", body, { auth: false });
      start(info);
      router.replace(next);
    } catch (problem) {
      if (problem instanceof ApiProblem && problem.code === "totp_required") {
        setNeedsCode(true);
        setError(null);
      } else {
        setError(problem instanceof ApiProblem ? problem.message : "Something went wrong. Please try again.");
        if (needsCode) setCode("");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <div className="box">
        <img className="logo" src="/logo/vrr-mark.svg" width={80} height={93} alt="VRR Degree College" />
        <h1>Admin sign in</h1>
        <p className="s">For college staff only.</p>
        <form onSubmit={submit} noValidate>
          {error && <Notice kind="error">{error}</Notice>}
          <Field label="E-mail" htmlFor="login-email">
            <input id="login-email" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} disabled={needsCode} />
          </Field>
          <Field label="Password" htmlFor="login-password">
            <input id="login-password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} disabled={needsCode} />
          </Field>
          {needsCode && (
            <Field
              label={useRecovery ? "Recovery code" : "6-digit code from your authenticator app"}
              htmlFor="login-code"
              help={
                <button type="button" className="alink" onClick={() => { setUseRecovery(!useRecovery); setCode(""); }}>
                  {useRecovery ? "Use the code from the app instead" : "Lost your phone? Use a recovery code"}
                </button>
              }
            >
              <input
                id="login-code"
                inputMode={useRecovery ? "text" : "numeric"}
                autoComplete="one-time-code"
                autoFocus
                required
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder={useRecovery ? "abc123-def456" : "123456"}
              />
            </Field>
          )}
          <Button type="submit" busy={busy} small={false} className="btn-block">
            {needsCode ? "Verify and sign in" : "Sign in"}
          </Button>
        </form>
      </div>
    </div>
  );
}
