import type { Metadata } from "next";
import { EnquiriesScreen } from "@/components/admin/EnquiriesScreen";

export const metadata: Metadata = { title: "Enquiries" };

export default function Page() {
  return <EnquiriesScreen />;
}
