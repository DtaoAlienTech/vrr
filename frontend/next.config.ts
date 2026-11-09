import type { NextConfig } from "next";

const isProd = process.env.NODE_ENV === "production";
const isHttps = (process.env.SITE_URL ?? "").startsWith("https://");
const hasTurnstile = Boolean(process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY);
const TURNSTILE = "https://challenges.cloudflare.com";
// Where /api requests go when no reverse proxy sits in front (local development and tests).
const backendUrl = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

// Public pages are static and cached, so a per-request nonce is not possible for them.
// This policy still blocks foreign scripts, plugins, framing, form hijacking and base-tag tricks.
// The admin area (dynamic) gets a stricter nonce-based policy from the proxy in Phase 3.
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
  // The Docker image sets BUILD_STANDALONE=1 (Phase 5). Locally, plain `next start` is used.
  ...(process.env.BUILD_STANDALONE ? { output: "standalone" as const } : {}),
  poweredByHeader: false,
  reactStrictMode: true,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
  async headers() {
    return [
      { source: "/:path*", headers: baseHeaders },
      ...(isProd
        ? [{ source: "/((?!admin).*)", headers: [{ key: "Content-Security-Policy", value: publicCsp }] }]
        : []),
    ];
  },
};

export default nextConfig;
