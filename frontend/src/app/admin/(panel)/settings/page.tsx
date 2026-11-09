import type { Metadata } from "next";
import { SettingsScreen } from "@/components/admin/SettingsScreen";

export const metadata: Metadata = { title: "Site settings" };

export default function Page() {
  return <SettingsScreen />;
}
