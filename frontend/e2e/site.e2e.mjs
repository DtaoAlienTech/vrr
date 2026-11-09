// Other main flows: photos for an activity, page content, enquiries, and phone screens.
import assert from "node:assert/strict";
import { after, before, describe, it } from "node:test";
import { EDITOR, PHOTO, SKIP_EDITOR, launch, publicApi, signIn, staff, toast } from "./helpers.mjs";

describe("activity photos", { skip: SKIP_EDITOR }, () => {
  let session;
  let id;
  before(async () => {
    session = await launch();
    await signIn(session.page, EDITOR);
  });
  after(async () => {
    if (id) await staff(session.page, "DELETE", `/activities/${id}`);
    await session.browser.close();
  });

  it("adds several photos at once and shows them on the website", async () => {
    const { page } = session;
    const title = `E2E camp ${Date.now()}`;
    await page.goto("/admin/activities/new");
    await page.getByRole("heading", { name: "Add activity" }).waitFor();
    await page.getByRole("textbox", { name: "Title", exact: true }).fill(title);
    await page.getByRole("combobox", { name: "Group" }).selectOption("nss");
    await page.getByRole("textbox", { name: "Short summary" }).fill("Volunteers cleaned the campus.");
    await page.getByRole("button", { name: "Choose or upload photos" }).click();
    const dialog = page.locator("dialog[open]");
    const cards = dialog.getByRole("button", { name: /^Choose / });
    await cards.nth(0).click();
    await cards.nth(1).click();
    await dialog.getByRole("button", { name: "Upload", exact: true }).click();
    await dialog.getByTestId("file-input").setInputFiles({ name: "e2e-new.jpg", mimeType: "image/jpeg", buffer: PHOTO });
    await dialog.getByPlaceholder("What does the photo show?").fill("E2E volunteers");
    await dialog.getByRole("button", { name: /Upload 1 file/ }).click();
    await dialog.getByText("Uploaded", { exact: true }).waitFor({ timeout: 20000 });
    await dialog.getByText("3 photos chosen").waitFor(); // the uploaded photo is chosen by itself
    await dialog.getByRole("button", { name: /Add 3 photos/ }).click();
    assert.equal(await page.locator(".alistitem").count(), 3);
    await page.getByRole("button", { name: "Publish", exact: true }).click();
    await toast(page, /Created/);
    await page.waitForURL(/\/admin\/activities\/\d+$/);
    id = page.url().split("/").pop();
    const { body } = await publicApi(page, "/activities");
    assert.equal(body.find((activity) => activity.title === title)?.photos.length, 3);
  });
});

describe("page content", { skip: SKIP_EDITOR }, () => {
  let session;
  before(async () => {
    session = await launch();
    await signIn(session.page, EDITOR);
  });
  after(async () => {
    await session.browser.close();
  });

  it("adds a section (refusing an empty one first), hides it, and can go back", async () => {
    const { page } = session;
    await page.goto("/admin/pages");
    await page.getByRole("link", { name: "About" }).first().click();
    await page.getByRole("heading", { name: /Page: About/ }).waitFor();
    const before = await page.locator(".secrow").count();
    const marker = `E2E band ${Date.now()}`;

    await page.getByRole("button", { name: "+ Add a section" }).click();
    await page.getByLabel("What do you want to add?").selectOption("enquiry_cta");
    await page.getByRole("button", { name: "Save section" }).click();
    await page.locator(".ferr").first().waitFor(); // an empty section is refused, with field messages
    await page.getByRole("textbox", { name: "Heading", exact: true }).fill(marker);
    await page.getByRole("textbox", { name: "Text", exact: true }).fill("Call us today.");
    await page.getByRole("button", { name: "Save section" }).click();
    await toast(page, /Section added/);
    assert.ok(JSON.stringify((await publicApi(page, "/pages/about")).body).includes(marker));

    await page.getByRole("button", { name: "Hide this section" }).last().click();
    await toast(page, /Hidden/);
    assert.ok(!JSON.stringify((await publicApi(page, "/pages/about")).body).includes(marker));

    await page.getByRole("button", { name: "Delete this section" }).last().click();
    await page.locator("dialog[open]").getByRole("button", { name: "Delete" }).click();
    await toast(page, /Section deleted/);
    await page.waitForFunction((n) => document.querySelectorAll(".secrow").length === n, before, { timeout: 5000 });
  });
});

describe("enquiries", { skip: SKIP_EDITOR }, () => {
  let session;
  let name;
  before(async () => {
    session = await launch();
    await signIn(session.page, EDITOR);
  });
  after(async () => {
    await session.browser.close();
  });

  it("lists what a visitor sent, lets staff mark it contacted, and exports a safe CSV", async () => {
    const { page } = session;
    name = `E2E Visitor ${Date.now()}`;
    const sent = await page.request.post("/api/v1/public/enquiries", { data: { name, phone: "9876543210", message: "=1+1", source_page: "/" } });
    assert.equal(sent.status(), 201);
    await page.goto("/admin/enquiries");
    await page.getByText(name).first().waitFor();
    await page.locator("tr", { hasText: name }).getByRole("button", { name: "Mark contacted" }).click();
    await page.locator("tr", { hasText: name }).locator(".st.ok", { hasText: "Contacted" }).waitFor();
    const csv = await (await page.request.get("/api/v1/admin/enquiries/export.csv")).text();
    assert.ok(csv.includes(name));
    assert.ok(csv.includes("'=1+1") && !csv.includes(",=1+1")); // a formula typed by a visitor stays plain text
  });
});

describe("phone screens", { skip: SKIP_EDITOR }, () => {
  let session;
  before(async () => {
    session = await launch({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
    await signIn(session.page, EDITOR);
  });
  after(async () => {
    await session.browser.close();
  });

  for (const path of ["/admin", "/admin/news", "/admin/news/new", "/admin/pages", "/admin/media", "/admin/enquiries", "/admin/account"]) {
    it(`${path} does not scroll sideways`, async () => {
      const { page } = session;
      await page.goto(path);
      await page.waitForTimeout(1200);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth), false);
    });
  }
});
