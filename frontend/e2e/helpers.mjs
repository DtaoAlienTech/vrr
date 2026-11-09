// Helpers for the browser tests (they drive a real Chrome against a running site; see e2e/README.md).
import { chromium } from "playwright-core";
import crypto from "node:crypto";
import fs from "node:fs";

export const BASE = (process.env.E2E_BASE ?? "http://localhost:3000").replace(/\/$/, "");
export const ADMIN = {
  email: process.env.E2E_ADMIN_EMAIL,
  password: process.env.E2E_ADMIN_PASSWORD,
  secret: process.env.E2E_ADMIN_TOTP_SECRET,
};
export const EDITOR = { email: process.env.E2E_EDITOR_EMAIL, password: process.env.E2E_EDITOR_PASSWORD };

export const haveEditor = Boolean(EDITOR.email && EDITOR.password);
export const haveAdmin = Boolean(ADMIN.email && ADMIN.password && ADMIN.secret);
export const SKIP_EDITOR = haveEditor ? false : "set E2E_EDITOR_EMAIL and E2E_EDITOR_PASSWORD";
export const SKIP_ADMIN = haveAdmin ? false : "set E2E_ADMIN_EMAIL, E2E_ADMIN_PASSWORD and E2E_ADMIN_TOTP_SECRET";

/** A small valid JPEG for upload tests. */
export const PHOTO = Buffer.from("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", "base64");
export const PDF = Buffer.from("%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n");

const ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
function base32(text) {
  let bits = "";
  for (const char of text.replace(/ /g, "").toUpperCase()) bits += ALPHABET.indexOf(char).toString(2).padStart(5, "0");
  const bytes = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) bytes.push(parseInt(bits.slice(i, i + 8), 2));
  return Buffer.from(bytes);
}

/** The six-digit code of an authenticator app for the current 30-second step (+ step offset). */
export function totp(secret, stepOffset = 0) {
  const counter = Math.floor(Date.now() / 30000) + stepOffset;
  const buffer = Buffer.alloc(8);
  buffer.writeBigUInt64BE(BigInt(counter));
  const hash = crypto.createHmac("sha1", base32(secret)).update(buffer).digest();
  const offset = hash[hash.length - 1] & 15;
  return String((hash.readUInt32BE(offset) & 0x7fffffff) % 1000000).padStart(6, "0");
}

export async function launch(options = {}) {
  const chrome = process.env.E2E_CHROME ?? ["/usr/bin/google-chrome", "/usr/bin/chromium"].find((path) => fs.existsSync(path));
  const browser = await chromium.launch({ ...(chrome ? { executablePath: chrome } : { channel: "chrome" }), args: ["--no-sandbox"] });
  const context = await browser.newContext({ baseURL: BASE, viewport: { width: 1360, height: 900 }, ...options });
  const page = await context.newPage();
  const problems = [];
  page.on("console", (message) => {
    if (/Content Security Policy|Refused to/.test(message.text())) problems.push(message.text().slice(0, 200));
  });
  page.on("pageerror", (error) => problems.push("pageerror: " + error.message.slice(0, 200)));
  return { browser, context, page, problems };
}

export async function signIn(page, account) {
  await page.goto("/admin/login");
  await page.getByLabel("E-mail").fill(account.email);
  await page.getByLabel("Password").fill(account.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  if (account.secret) {
    await page.getByLabel(/6-digit code/).fill(totp(account.secret, 1)); // the next step: never the one used last time
    await page.getByRole("button", { name: /Verify/ }).click();
  }
  await page.getByRole("heading", { name: /Welcome/ }).waitFor({ timeout: 20000 });
}

/** The visible toast with this text. */
export const toast = (page, pattern) => page.locator(".atoast").filter({ hasText: pattern }).first().waitFor({ timeout: 10000 });

/** Reads the website's public API as a visitor would. */
export async function publicApi(page, path) {
  const response = await page.request.get(`${BASE}/api/v1/public${path}`);
  return { status: response.status(), body: response.status() === 200 ? await response.json() : null };
}

/** Calls the staff API with the signed-in page's cookies (for cleanup). */
export async function staff(page, method, path, body) {
  const info = await (await page.request.get(`${BASE}/api/v1/auth/me`)).json();
  const response = await page.request.fetch(`${BASE}/api/v1/admin${path}`, {
    method,
    data: body,
    headers: { "x-csrf-token": info.csrfToken, origin: BASE },
  });
  return { status: response.status(), body: response.status() === 200 || response.status() === 201 ? await response.json() : null };
}
