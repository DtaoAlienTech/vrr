import type { Metadata } from "next";
import { Suspense } from "react";
import { AdminProviders } from "@/components/admin/AdminProviders";
import "@/styles/admin.css";

// The admin is not expected to be an "instant" navigation (it asks the API for its data).
export const instant = false;

export const metadata: Metadata = {
  title: "Admin",
  robots: { index: false, follow: false, nocache: true },
};

// The admin holds no data of its own: the browser asks the API, which checks the login. Its page
// shell is pre-built like every other page, so it has a strict policy (see next.config.ts) rather
// than a per-request nonce, which Next.js cannot combine with a pre-built shell.
export default function AdminLayout({ children }: LayoutProps<"/admin">) {
  return (
    <div className="adm">
      <AdminProviders>
        <Suspense fallback={<p className="aloading">Loading…</p>}>{children}</Suspense>
      </AdminProviders>
    </div>
  );
}
