import type { Metadata } from "next";
import { NotFoundContent } from "@/components/NotFoundContent";

export const metadata: Metadata = { title: "Page not found", robots: { index: false, follow: false } };

// Shown inside the normal site frame (header and footer) for missing courses, news and pages.
export default function PublicNotFound() {
  return <NotFoundContent />;
}
