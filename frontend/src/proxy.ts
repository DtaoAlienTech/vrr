import { NextResponse, type NextRequest } from "next/server";
import { SITE_URL } from "@/lib/env";
import { getRedirectTable } from "@/lib/redirect-source";
import { resolveRedirect } from "@/lib/redirects";

// Old addresses (an editor changed a page, course or news address) answer with a real 301/302,
// so Google and old links keep working. The rules come from the backend and are cached for a
// short time (see lib/redirect-source.ts); a hiccup of the API never breaks a page.
export async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const hit = resolveRedirect(await getRedirectTable(), pathname, search);
  if (!hit) return NextResponse.next();

  // The address is built from the configured site address, never from the Host header the visitor
  // sent. Next.js also requires an absolute address here.
  const target = new URL(hit.location, SITE_URL);
  if (target.origin !== new URL(SITE_URL).origin) return NextResponse.next(); // cannot happen: rules are site paths
  return NextResponse.redirect(target, hit.status);
}

export const config = {
  // Public pages only: not the admin panel, the API, uploads, the refresh hook, Next.js files or
  // anything with a file extension (images, robots.txt, sitemap.xml ...).
  matcher: ["/((?!admin|api|uploads|internal|_next|.*\\..*).*)"],
};
