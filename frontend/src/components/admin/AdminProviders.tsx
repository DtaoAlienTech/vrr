"use client";

import type { ReactNode } from "react";
import { DirtyGuard } from "./dirty";
import { FeedbackProvider } from "./feedback";
import { SessionProvider } from "./session";

export function AdminProviders({ children }: { children: ReactNode }) {
  return (
    <SessionProvider>
      <FeedbackProvider>
        <DirtyGuard>{children}</DirtyGuard>
      </FeedbackProvider>
    </SessionProvider>
  );
}
