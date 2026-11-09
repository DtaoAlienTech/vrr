"use client";
// Small data-loading hooks for the admin screens (no extra library needed).
import { useCallback, useEffect, useState } from "react";
import { api } from "./api.ts";
import { ApiProblem } from "./problem.ts";

type Result<T> = { url: string | null; data?: T; error?: ApiProblem };

/** Loads `url` (a staff API address, or null to wait). Keeps the old data while reloading. */
export function useApi<T>(url: string | null): {
  data: T | undefined;
  error: ApiProblem | undefined;
  loading: boolean;
  reload: () => void;
} {
  const [result, setResult] = useState<Result<T>>({ url: null });
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (url === null) return;
    const controller = new AbortController();
    api.get<T>(url, controller.signal).then(
      (data) => setResult({ url, data }),
      (error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setResult({ url, error: error instanceof ApiProblem ? error : new ApiProblem(0, "error", "Something went wrong.") });
      },
    );
    return () => controller.abort();
  }, [url, version]);

  const current = result.url === url;
  return {
    data: current ? result.data : undefined,
    error: current ? result.error : undefined,
    loading: url !== null && !current,
    reload: useCallback(() => setVersion((v) => v + 1), []),
  };
}
