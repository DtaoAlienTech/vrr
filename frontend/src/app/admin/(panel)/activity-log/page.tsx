import type { Metadata } from "next";
import { ActivityLogScreen } from "@/components/admin/UsersScreen";

export const metadata: Metadata = { title: "Activity log" };

export default function Page() {
  return <ActivityLogScreen />;
}
