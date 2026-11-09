import type { Metadata } from "next";
import { NotFoundContent } from "@/components/NotFoundContent";

export const metadata: Metadata = { title: "Page not found", robots: { index: false, follow: false } };

// For addresses that match no route at all (no site frame is available here).
export default function NotFound() {
  return (
    <main>
      <NotFoundContent />
    </main>
  );
}
