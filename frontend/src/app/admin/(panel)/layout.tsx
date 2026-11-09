import type { ReactNode } from "react";
import { MediaPickerProvider } from "@/components/admin/media";
import { Shell } from "@/components/admin/Shell";
import { Gate } from "@/components/admin/session";

export default function PanelLayout({ children }: { children: ReactNode }) {
  return (
    <Gate>
      <MediaPickerProvider>
        <Shell>{children}</Shell>
      </MediaPickerProvider>
    </Gate>
  );
}
