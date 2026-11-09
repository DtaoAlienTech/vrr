import { createHash, timingSafeEqual } from "node:crypto";
import { revalidateTag } from "next/cache";
import { NextResponse, type NextRequest } from "next/server";
import { clearRedirectCache } from "@/lib/redirect-source";

// Called by the backend after an admin saves content, so the public site updates within seconds.
// Protected by a shared secret and blocked from the internet by the reverse proxy (/internal/*).

const TAG_PATTERN = /^[a-z0-9:_-]{1,64}$/i;
const MAX_TAGS = 20;

function secretMatches(given: string, expected: string): boolean {
  // Hash first so both buffers have the same length, then compare in constant time.
  const a = createHash("sha256").update(given).digest();
  const b = createHash("sha256").update(expected).digest();
  return timingSafeEqual(a, b);
}

export async function POST(request: NextRequest) {
  const expected = process.env.REVALIDATE_SECRET ?? "";
  const given = request.headers.get("x-revalidate-secret") ?? "";
  if (expected.length < 24 || !secretMatches(given, expected)) {
    return NextResponse.json({ ok: false }, { status: 401 });
  }

  const body: unknown = await request.json().catch(() => null);
  const rawTags = (body as { tags?: unknown } | null)?.tags;
  const tags = Array.isArray(rawTags)
    ? rawTags.filter((t): t is string => typeof t === "string" && TAG_PATTERN.test(t)).slice(0, MAX_TAGS)
    : [];
  if (tags.length === 0) {
    return NextResponse.json({ ok: false, error: "no valid tags" }, { status: 400 });
  }

  // expire: 0 = the very next visit gets fresh content. (The default "max" would show the old page
  // once more while the new one is prepared, which looks like "my change did not save".)
  for (const tag of tags) revalidateTag(tag, { expire: 0 });
  // The old-address list is not part of the page cache: it has its own short-lived copy.
  if (tags.includes("redirects")) clearRedirectCache();
  return NextResponse.json({ ok: true, tags });
}
