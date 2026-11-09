const MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];

/** Splits an ISO date (YYYY-MM-DD) for display. Plain string handling, so no time zone can shift it. */
export function dateParts(iso: string): { day: string; monthYear: string; long: string } {
  const [year = "", month = "", day = ""] = iso.split("-");
  const name = MONTHS[Number(month) - 1] ?? "";
  const pretty = name.charAt(0) + name.slice(1).toLowerCase();
  return {
    day: day.padStart(2, "0"),
    monthYear: `${name} ${year}`,
    long: `${Number(day)} ${pretty} ${year}`,
  };
}

/** "Asha Reddy" -> "AR". Used when a faculty member has no photo yet. */
export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  return words
    .slice(0, 2)
    .map((word) => word.charAt(0).toUpperCase())
    .join("");
}
