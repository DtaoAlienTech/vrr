import type { Metadata } from "next";
import { MediaScreen } from "@/components/admin/screens";

export const metadata: Metadata = { title: "Photos & files" };

export default function MediaPage() {
  return <MediaScreen />;
}
