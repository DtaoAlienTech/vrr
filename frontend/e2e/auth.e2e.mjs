import assert from "node:assert/strict";
import { after, before, describe, it } from "node:test";
import { ADMIN, BASE, EDITOR, SKIP_ADMIN, SKIP_EDITOR, launch, signIn } from "./helpers.mjs";

describe("signing in", () => {
  let session;
  before(async () => {
    session = await launch();
  });
  after(async () => {
    await session.browser.close();
  });

  it("sends a signed-out visitor to the sign-in page and remembers where they wanted to go", async () => {
    const { page } = session;
    await page.goto("/admin/news");
    await page.waitForURL(/\/admin\/login\?next=%2Fadmin%2Fnews/, { timeout: 15000 });
  });

  it("answers every failure with the same message", async () => {
    const { page } = session;
    await page.goto("/admin/login");
    await page.getByLabel("E-mail").fill("nobody@example.org");
    await page.getByLabel("Password").fill("not the password at all");
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.locator(".anotice-error").waitFor();
    assert.match(await page.locator(".anotice-error").innerText(), /Incorrect e-mail, password or code/);
  });

  it("sends the admin pages with a strict security policy and no indexing", async () => {
    const response = await session.page.request.get(`${BASE}/admin/login`);
    const policy = response.headers()["content-security-policy"] ?? "";
    if (BASE.startsWith("http://localhost") && !policy) return; // development mode has no policy
    assert.match(policy, /default-src 'self'/);
    assert.match(policy, /frame-ancestors 'none'/);
    assert.match(policy, /object-src 'none'/);
    assert.doesNotMatch(policy, /unsafe-eval/);
    assert.match(response.headers()["x-robots-tag"] ?? "", /noindex/);
  });

  it("signs an editor in, shows only their menu, and signs out", { skip: SKIP_EDITOR }, async () => {
    const { page } = session;
    await signIn(page, EDITOR);
    assert.equal(await page.getByRole("link", { name: "Users" }).count(), 0);
    assert.equal(await page.getByRole("link", { name: "Site settings" }).count(), 0);
    await page.getByRole("button", { name: "Sign out" }).click();
    await page.waitForURL(/\/admin\/login/);
    await page.goto("/admin/news");
    await page.waitForURL(/\/admin\/login/); // really signed out
  });

  it("asks a super admin for a code after the password, and shows the extra menu", { skip: SKIP_ADMIN }, async () => {
    const { page } = session;
    await page.context().clearCookies();
    await page.goto("/admin/login");
    await page.getByLabel("E-mail").fill(ADMIN.email);
    await page.getByLabel("Password").fill(ADMIN.password);
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.getByLabel(/6-digit code/).waitFor();
    await page.getByLabel(/6-digit code/).fill("000000");
    await page.getByRole("button", { name: /Verify/ }).click();
    await page.locator(".anotice-error").waitFor(); // a wrong code is refused
    await signIn(page, ADMIN);
    assert.ok(await page.getByRole("link", { name: "Users" }).isVisible());
    assert.ok(await page.getByRole("link", { name: "Site settings" }).isVisible());
  });
});
