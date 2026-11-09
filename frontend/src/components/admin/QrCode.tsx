"use client";

import { useMemo } from "react";
import { encodeQr, qrPath } from "@/lib/qr";

/** A QR code drawn right here in the browser (nothing is sent anywhere, which matters because the
 * text is a secret). Always black on white with the empty border scanners need, also in dark mode.
 * Shows nothing if the text is too long to fit, so the screen still has the typed key. */
export function QrCode({ value, label }: { value: string; label: string }) {
  const drawing = useMemo(() => {
    try {
      return qrPath(encodeQr(value));
    } catch {
      return null;
    }
  }, [value]);
  if (!drawing) return null;
  return (
    <svg className="qrcode" viewBox={`0 0 ${drawing.size} ${drawing.size}`} role="img" aria-label={label} shapeRendering="crispEdges" data-testid="setup-qr">
      <rect width={drawing.size} height={drawing.size} fill="#fff" />
      <path d={drawing.path} fill="#000" />
    </svg>
  );
}
