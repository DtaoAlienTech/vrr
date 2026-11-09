import type { NextConfig } from "next";

const isProd = process.env.NODE_ENV === "production";
const isHttps = (process.env.SITE_URL ?? "").startsWith("https://");
const hasTurnstile = Boolean(process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY);
const TURNSTILE = "https://challenges.cloudflare.com";
// Where /api requests go when no reverse proxy sits in front (local development and tests).
const backendUrl = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

// Pages are pre-built and cached (Cache Components), so a per-request nonce is not possible: Next.js
// documents that nonce policies cannot work with a pre-built shell. These policies still block
// foreign scripts, plugins, framing, form hijacking and <base> tricks.
const publicCsp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${hasTurnstile ? ` ${TURNSTILE}` : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: https://i.ytimg.com",
  "font-src 'self'",
  "connect-src 'self'",
  `frame-src https://www.youtube-nocookie.com https://www.google.com${hasTurnstile ? ` ${TURNSTILE}` : ""}`,
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  ...(isHttps ? ["upgrade-insecure-requests"] : []),
].join("; ");

// The admin panel: no other websites at all (no maps, videos or spam checks), and never indexed.
const adminCsp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self'",
  "connect-src 'self'",
  "frame-src 'none'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  ...(isHttps ? ["upgrade-insecure-requests"] : []),
].join("; ");

const baseHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  ...(isHttps ? [{ key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" }] : []),
];

const nextConfig: NextConfig = {
  cacheComponents: true,
  // partialPrefetching is off on purpose: with it, the first visit to an unknown address gets an
  // instant shell with status 200 (a "soft 404"). Without it the real 404 status is sent at once.
  poweredByHeader: false,
  reactStrictMode: true,
  async rewrites() {
    // In Docker, Caddy answers /api and /uploads itself; these are for development without it.
    return [
      { source: "/api/:path*", destination: `${backendUrl}/api/:path*` },
      { source: "/uploads/:path*", destination: `${backendUrl}/uploads/:path*` },
    ];
  },
  async headers() {
    return [
      { source: "/:path*", headers: baseHeaders },
      ...(isProd
        ? [
            { source: "/((?!admin).*)", headers: [{ key: "Content-Security-Policy", value: publicCsp }] },
            { source: "/admin/:path*", headers: [{ key: "Content-Security-Policy", value: adminCsp }] },
          ]
        : []),
      { source: "/admin/:path*", headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow, noarchive" }] },
      // Draft previews: private, never stored by a cache or search engine, and the link (which holds
      // the token) is not passed on to other websites.
      {
        source: "/preview/:path*",
        headers: [
          { key: "X-Robots-Tag", value: "noindex, nofollow, noarchive" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "Cache-Control", value: "private, no-store" },
        ],
      },
    ];
  },
};

export default nextConfig;
