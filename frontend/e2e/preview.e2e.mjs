// Draft preview and old addresses, as an editor and a visitor would meet them.
import assert from "node:assert/strict";
import { after, before, describe, it } from "node:test";
import { BASE, EDITOR, SKIP_EDITOR, launch, signIn, staff } from "./helpers.mjs";

const TITLE = `E2E preview ${Date.now()}`;
const doc = (text) => ({ type: "doc", content: [{ type: "paragraph", content: [{ type: "text", text }] }] });

describe("draft preview and old addresses", { skip: SKIP_EDITOR }, () => {
  let session;
  let news; // { id, slug }
  before(async () => {
    session = await launch();
    await signIn(session.page, EDITOR);
    const made = await staff(session.page, "POST", "/news", {
      title: TITLE,
      category: "event",
      summary: "A draft that only the preview link can show.",
      body: doc("Only people with the link can read this sentence."),
      status: "draft",
    });
    assert.equal(made.status, 201);
    news = { id: made.body.id, slug: made.body.slug };
  });
  after(async () => {
    if (news) await staff(session.page, "DELETE", `/news/${news.id}`);
    await session.browser.close();
  });

  it("opens the saved draft in a new tab, marked as a preview and hidden from search engines", async () => {
    const { page, context } = session;
    await page.goto(`/admin/news/${news.id}`);
    await page.getByRole("heading", { name: "Edit news item" }).waitFor();
    const [preview] = await Promise.all([context.waitForEvent("page"), page.getByRole("button", { name: "Preview", exact: true }).click()]);
    await preview.waitForURL(/\/preview\/v1\.news\.\d+\.\d+\.[0-9a-f]+$/, { timeout: 20000 });
    await preview.locator(".preview-bar").waitFor({ timeout: 20000 });
    assert.match(await preview.locator(".preview-bar").innerText(), /Draft preview/i);
    assert.match(await preview.locator("main").innerText(), /Only people with the link can read this sentence\./);
    assert.match(await preview.locator("h1").first().innerText(), new RegExp(TITLE));
    assert.equal(await preview.evaluate(() => window.opener), null, "the preview tab cannot reach the admin tab");
    assert.match((await preview.locator('meta[name="robots"]').getAttribute("content")) ?? "", /noindex/);

    // The same address works for a visitor who is not signed in (that is what a link is for) ...
    const visitor = await session.browser.newContext({ baseURL: BASE });
    const visitorPage = await visitor.newPage();
    await visitorPage.goto(preview.url());
    await visitorPage.locator(".preview-bar").waitFor({ timeout: 20000 });
    // ... but the draft itself is still not public.
    const live = await visitorPage.request.get(`${BASE}/news/${news.slug}`);
    assert.equal(live.status(), 404);
    await visitor.close();
    await preview.close();
  });

  it("says when the preview leaves out unsaved changes", async () => {
    const { page } = session;
    await page.goto(`/admin/news/${news.id}`);
    await page.getByRole("heading", { name: "Edit news item" }).waitFor();
    await page.getByRole("textbox", { name: "Title", exact: true }).fill(`${TITLE} (typing)`);
    await page.getByRole("button", { name: "Preview (saved version)" }).waitFor();
    // leave without saving: the unsaved-changes prompt is expected
    page.once("dialog", (dialog) => void dialog.accept());
    await page.goto("/admin");
  });

  it("previews a page too, with its real sections", async () => {
    const { page, context } = session;
    const pages = await (await page.request.get(`${BASE}/api/v1/admin/pages`)).json();
    const about = pages.find((p) => p.key === "about");
    await page.goto(`/admin/pages/${about.id}`);
    await page.getByRole("button", { name: "Preview", exact: true }).waitFor({ timeout: 15000 });
    const [preview] = await Promise.all([context.waitForEvent("page"), page.getByRole("button", { name: "Preview", exact: true }).click()]);
    await preview.waitForURL(/\/preview\/v1\.page\./, { timeout: 20000 });
    await preview.locator(".preview-bar").waitFor({ timeout: 20000 });
    assert.ok((await preview.locator("main h1").count()) >= 1, "the page content is drawn");
    await preview.close();
  });

  it("sends visitors of an old address to the new one", async () => {
    const { page } = session;
    const body = { title: TITLE, category: "event", summary: "A draft that only the preview link can show.", body: doc("Moved."), status: "published" };
    assert.equal((await staff(page, "PUT", `/news/${news.id}`, { ...body, slug: news.slug })).status, 200);
    assert.equal((await staff(page, "PUT", `/news/${news.id}`, { ...body, slug: `${news.slug}-moved` })).status, 200);

    // what a search engine sees: a permanent redirect, with the query string kept
    const raw = await page.request.get(`${BASE}/news/${news.slug}?utm_source=e2e`, { maxRedirects: 0 });
    assert.equal(raw.status(), 301);
    assert.equal(raw.headers().location, `${BASE}/news/${news.slug}-moved?utm_source=e2e`);

    // what a person sees: the new page opens
    const visitor = await session.browser.newContext({ baseURL: BASE });
    const visitorPage = await visitor.newPage();
    await visitorPage.goto(`/news/${news.slug}`);
    await visitorPage.waitForURL(new RegExp(`/news/${news.slug}-moved$`));
    assert.match(await visitorPage.locator("h1").first().innerText(), new RegExp(TITLE));
    await visitor.close();
  });

  it("does not follow a redirect to another website", async () => {
    const { page } = session;
    for (const to of ["//evil.example", "https://evil.example", "/\\evil.example"]) {
      const response = await staff(page, "POST", "/redirects", { fromPath: "/e2e-evil", toPath: to });
      assert.equal(response.status, 422, `${to} must be refused`);
    }
  });
});
