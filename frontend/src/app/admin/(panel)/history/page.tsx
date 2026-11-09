import type { Metadata } from "next";
import { HistoryScreen } from "@/components/admin/HistoryScreen";

export const metadata: Metadata = { title: "History & redirects" };

export default function Page() {
  return <HistoryScreen />;
}
