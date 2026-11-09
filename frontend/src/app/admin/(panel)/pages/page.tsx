import type { Metadata } from "next";
import { PagesList } from "@/components/admin/PagesScreens";

export const metadata: Metadata = { title: "Page content" };

export default function PagesPage() {
  return <PagesList />;
}
