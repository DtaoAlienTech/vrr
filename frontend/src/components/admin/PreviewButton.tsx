"use client";

import { useState } from "react";
import { api } from "@/lib/admin/api";
import { ApiProblem } from "@/lib/admin/problem";
import { useFeedback } from "./feedback";
import { Button } from "./ui";

/** Opens the saved draft on the real website layout, through a signed link that lasts 30 minutes.
 * The link is made on click (so it is always fresh) and opens in a new tab. */
export function PreviewButton({ kind, id, unsaved = false }: { kind: "page" | "news"; id: number; unsaved?: boolean }) {
  const feedback = useFeedback();
  const [busy, setBusy] = useState(false);

  const open = async () => {
    // The tab is opened right in the click, because browsers block tabs opened after a wait.
    const tab = window.open("about:blank", "_blank");
    if (tab) tab.opener = null;
    setBusy(true);
    try {
      const link = await api.post<{ path: string }>("/admin/preview-links", { kind, id });
      if (tab) tab.location.href = link.path;
      else window.location.assign(link.path);
    } catch (error) {
      tab?.close();
      feedback.error(error instanceof ApiProblem ? error.message : "The preview could not be opened. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Button
      variant="ghost"
      busy={busy}
      onClick={() => void open()}
      title={unsaved ? "Shows the last saved version. Your unsaved changes are not included." : "Shows how it will look when published"}
    >
      {unsaved ? "Preview (saved version)" : "Preview"}
    </Button>
  );
}
