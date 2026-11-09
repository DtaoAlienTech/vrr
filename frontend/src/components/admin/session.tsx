"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, fetchSession, onSessionLost, renewSession, setCsrfToken } from "@/lib/admin/api";
import type { AdminUser, SessionInfo } from "@/lib/admin/types";

type State = { status: "loading" } | { status: "anonymous" } | { status: "ready"; user: AdminUser };

type SessionApi = {
  state: State;
  /** Asks the server again who is signed in (after changing the profile or two-factor setting). */
  reload: () => Promise<void>;
  /** Takes over a fresh login (used by the sign-in page). */
  start: (info: SessionInfo) => void;
  signOut: () => Promise<void>;
};

const Context = createContext<SessionApi | null>(null);

/** Who is signed in? Tries the current login, then renews it once from the refresh cookie. */
async function currentSession(): Promise<SessionInfo | null> {
  const info = await fetchSession();
  if (info) return info;
  return (await renewSession()) ? fetchSession() : null;
}

const toState = (info: SessionInfo | null): State => (info ? { status: "ready", user: info.user } : { status: "anonymous" });

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>({ status: "loading" });

  const reload = useCallback(async () => {
    setState(toState(await currentSession()));
  }, []);

  useEffect(() => {
    let cancelled = false;
    onSessionLost(() => {
      setCsrfToken(null);
      setState({ status: "anonymous" });
    });
    currentSession().then((info) => {
      if (!cancelled) setState(toState(info));
    });
    return () => {
      cancelled = true;
      onSessionLost(null);
    };
  }, []);

  const value = useMemo<SessionApi>(
    () => ({
      state,
      reload,
      start: (info) => {
        setCsrfToken(info.csrfToken);
        setState({ status: "ready", user: info.user });
      },
      signOut: async () => {
        try {
          await api.post("/auth/logout", undefined, { auth: false });
        } finally {
          setCsrfToken(null);
          setState({ status: "anonymous" });
        }
      },
    }),
    [state, reload],
  );

  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useSession(): SessionApi {
  const value = useContext(Context);
  if (!value) throw new Error("useSession needs a SessionProvider");
  return value;
}

/** The signed-in person (only for screens inside the gate, which shows them nothing otherwise). */
export function useUser(): AdminUser {
  const { state } = useSession();
  if (state.status !== "ready") throw new Error("useUser used before sign-in");
  return state.user;
}

/** Where a visitor goes after signing in: only addresses inside /admin are accepted. */
export function safeNext(value: string | null | undefined): string {
  if (value && /^\/admin(\/[A-Za-z0-9\-_/.]*)?$/.test(value) && !value.includes("//") && !value.startsWith("/admin/login")) {
    return value;
  }
  return "/admin";
}

/** Shows its children only to a signed-in person; everyone else is sent to the sign-in page. */
export function Gate({ children }: { children: ReactNode }) {
  const { state } = useSession();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (state.status === "anonymous") router.replace(`/admin/login?next=${encodeURIComponent(pathname)}`);
    if (state.status === "ready" && state.user.needsTotpSetup && pathname !== "/admin/account") {
      router.replace("/admin/account?setup=1");
    }
  }, [state, router, pathname]);

  if (state.status !== "ready") return <p className="aloading" role="status">Checking your sign-in…</p>;
  if (state.user.needsTotpSetup && pathname !== "/admin/account") return null;
  return <>{children}</>;
}
