import type { Metadata } from "next";
import { Suspense } from "react";
import { AccountScreen } from "@/components/admin/AccountScreen";

export const metadata: Metadata = { title: "My account" };

export default function AccountPage() {
  return (
    <Suspense fallback={null}>
      <AccountScreen />
    </Suspense>
  );
}
