// The live search-engine checklist of the plan (section 4A): title 30 to 60 characters,
// description 70 to 160, exactly one H1, text on every photo, no broken links.
import { brokenSitePaths, collectLinks } from "./links.ts";

export type SeoStatus = "ok" | "warn" | "bad";
export type SeoCheck = { id: string; status: SeoStatus; label: string; hint?: string };

export function lengthCheck(id: string, name: string, text: string, min: number, max: number): SeoCheck {
  const length = text.trim().length;
  if (length === 0) return { id, status: "bad", label: `${name} is empty`, hint: `Write ${min} to ${max} characters.` };
  if (length < min) return { id, status: "warn", label: `${name} is short (${length})`, hint: `Aim for ${min} to ${max} characters.` };
  if (length > max) return { id, status: "warn", label: `${name} is long (${length})`, hint: `Google may cut it after ${max} characters.` };
  return { id, status: "ok", label: `${name} length is good (${length})` };
}

export type SeoInput = {
  title?: string;
  description?: string;
  /** Number of main headings (H1) on the page, when known (pages only). */
  h1Count?: number;
  /** Photos without a description, when known. */
  photosWithoutText?: number;
  /** All data of the page, to look for links that lead nowhere. */
  pageData?: unknown;
  knownPaths?: string[];
};

export function seoChecks(input: SeoInput): SeoCheck[] {
  const checks: SeoCheck[] = [];
  if (input.title !== undefined) checks.push(lengthCheck("title", "Title", input.title, 30, 60));
  if (input.description !== undefined) checks.push(lengthCheck("description", "Description", input.description, 70, 160));
  if (input.h1Count !== undefined) {
    checks.push(
      input.h1Count === 1
        ? { id: "h1", status: "ok", label: "The page has one main heading" }
        : {
            id: "h1",
            status: "bad",
            label: input.h1Count === 0 ? "The page has no main heading" : `The page has ${input.h1Count} main headings`,
            hint: "Use exactly one “Page title” or “Home banner” section.",
          },
    );
  }
  if (input.photosWithoutText !== undefined) {
    checks.push(
      input.photosWithoutText === 0
        ? { id: "alt", status: "ok", label: "Every photo has a description" }
        : { id: "alt", status: "bad", label: `${input.photosWithoutText} photo(s) have no description`, hint: "Add the description in the media library." },
    );
  }
  if (input.pageData !== undefined && input.knownPaths) {
    const broken = brokenSitePaths(collectLinks(input.pageData), input.knownPaths);
    checks.push(
      broken.length === 0
        ? { id: "links", status: "ok", label: "No broken links" }
        : { id: "links", status: "bad", label: `Broken link${broken.length === 1 ? "" : "s"}: ${broken.slice(0, 3).join(", ")}`, hint: "These addresses are not pages of the website." },
    );
  }
  return checks;
}

function cut(text: string, max: number): string {
  return text.length <= max ? text : `${text.slice(0, max - 1).trimEnd()}…`;
}

/** How the page looks in Google results. */
export function serpPreview(input: { title: string; template: string; description: string; origin: string; path: string }) {
  const full = input.template.includes("%s") ? input.template.replace("%s", input.title) : input.title;
  const url = new URL(input.path, input.origin);
  return {
    title: cut(full, 60),
    url: `${url.host}${url.pathname === "/" ? "" : url.pathname.replace(/\//g, " › ")}`,
    description: cut(input.description, 160),
  };
}
