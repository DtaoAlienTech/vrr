// The plan's "done when": a staff member can sign in, publish a notice with a photo and a PDF,
// and see it on the website without help.
import assert from "node:assert/strict";
import { after, before, describe, it } from "node:test";
import { EDITOR, PDF, PHOTO, SKIP_EDITOR, launch, publicApi, signIn, staff, toast } from "./helpers.mjs";

const TITLE = `E2E open day ${Date.now()}`;

describe("publishing a news item", { skip: SKIP_EDITOR }, () => {
  let session;
  let id;
  before(async () => {
    session = await launch();
    await signIn(session.page, EDITOR);
  });
  after(async () => {
    if (id) await staff(session.page, "DELETE", `/news/${id}`); // leave nothing behind
    await session.browser.close();
  });

  it("refuses an empty form and names what is missing", async () => {
    const { page } = session;
    await page.goto("/admin/news/new");
    await page.getByRole("heading", { name: "Add news item" }).waitFor();
    await page.getByRole("button", { name: "Publish", exact: true }).click();
    await page.locator(".anotice-error").waitFor();
    assert.match(await page.locator(".anotice-error").innerText(), /Title: This is required/);
    assert.equal(await page.locator("dialog[open]").count(), 0);
  });

  it("publishes with formatted text, a link, a photo uploaded from the picker and a PDF", async () => {
    const { page } = session;
    await page.getByRole("textbox", { name: "Title", exact: true }).fill(TITLE);
    await page.getByRole("combobox", { name: "Category" }).selectOption("event");
    await page.getByRole("textbox", { name: "Short summary" }).fill("Come and see the college and ask about admission.");

    const editor = page.locator(".rte-content").first();
    await editor.waitFor({ timeout: 15000 });
    await editor.click();
    await page.keyboard.type("Everyone is welcome.");
    await page.keyboard.press("Control+A");
    await page.getByRole("button", { name: "Bold" }).click();
    await page.keyboard.press("End");
    await page.keyboard.press("Enter");
    await page.keyboard.type("Read about admissions");
    await page.keyboard.press("Shift+Home");
    await page.getByRole("button", { name: "Link", exact: true }).click();
    await page.locator("#rte-link").fill("javascript:alert(1)");
    await page.getByRole("button", { name: "Apply link" }).click();
    await page.getByText("Use a site address").waitFor(); // an unsafe link is refused
    await page.locator("#rte-link").fill("/admissions");
    await page.getByRole("button", { name: "Apply link" }).click();

    await page.getByRole("button", { name: "Choose Cover photo" }).click();
    const picker = page.locator("dialog[open]");
    await picker.getByRole("button", { name: "Upload", exact: true }).click();
    await picker.getByTestId("file-input").setInputFiles({ name: "e2e-campus.jpg", mimeType: "image/jpeg", buffer: PHOTO });
    assert.ok(await picker.getByRole("button", { name: /Upload 1 file/ }).isDisabled(), "a description is required first");
    await picker.getByPlaceholder("What does the photo show?").fill("E2E test photo");
    await picker.getByRole("button", { name: /Upload 1 file/ }).click();
    await picker.getByText("Uploaded", { exact: true }).waitFor({ timeout: 20000 });
    await picker.getByRole("button", { name: "Close upload" }).click();
    await picker.getByRole("button", { name: /Choose e2e-campus.jpg/ }).first().click();

    await page.getByRole("button", { name: "+ Add item" }).click();
    await page.getByRole("button", { name: "Choose File" }).click();
    const pdfPicker = page.locator("dialog[open]");
    await pdfPicker.getByRole("button", { name: "Upload", exact: true }).click();
    await pdfPicker.getByTestId("file-input").setInputFiles({ name: "e2e-circular.pdf", mimeType: "application/pdf", buffer: PDF });
    await pdfPicker.getByRole("button", { name: /Upload 1 file/ }).click();
    await pdfPicker.getByText("Uploaded", { exact: true }).waitFor({ timeout: 20000 });
    await pdfPicker.getByRole("button", { name: "Close upload" }).click();
    await pdfPicker.getByRole("button", { name: /Choose e2e-circular.pdf/ }).first().click();
    await page.getByRole("textbox", { name: "Label", exact: true }).fill("Circular");

    await page.getByRole("button", { name: "Publish", exact: true }).click();
    await toast(page, /Created/);
    await page.waitForURL(/\/admin\/news\/\d+$/);
    id = page.url().split("/").pop();
  });

  it("shows it on the website's API at once, with clean rich text", async () => {
    const { page } = session;
    const slug = await page.getByRole("textbox", { name: "Web address" }).inputValue();
    const { status, body } = await publicApi(page, `/news/${slug}`);
    assert.equal(status, 200);
    assert.equal(body.title, TITLE);
    assert.equal(body.attachments.length, 1);
    const json = JSON.stringify(body.body);
    assert.ok(json.includes('"bold"') && json.includes('"/admissions"'));
    assert.ok(!json.includes("target") && !json.includes('"rel"')); // only what the server accepts
  });

  it("keeps a history, warns about unsaved changes, and can go back", async () => {
    const { page } = session;
    await page.reload();
    const title = page.getByRole("textbox", { name: "Title", exact: true });
    await title.fill(`${TITLE} (edited)`);
    assert.ok(await page.locator(".st.dr", { hasText: "Unsaved changes" }).isVisible());
    let warned = "";
    page.once("dialog", async (dialog) => {
      warned = dialog.message();
      await dialog.dismiss();
    });
    await page.getByRole("link", { name: "Faculty" }).click();
    await page.waitForTimeout(400);
    assert.match(warned, /unsaved changes/);
    assert.match(page.url(), /\/admin\/news\/\d+$/); // stayed

    await page.getByRole("button", { name: "Save changes" }).click();
    await toast(page, /Saved/);
    await page.getByRole("button", { name: "Show" }).click();
    await page.locator(".history li").nth(1).waitFor();
    await page.getByRole("button", { name: "Restore this version" }).first().click();
    await page.locator("dialog[open]").getByRole("button", { name: "Restore" }).click();
    await toast(page, /Restored/);
    await page.waitForTimeout(600);
    assert.equal(await page.getByRole("textbox", { name: "Title", exact: true }).inputValue(), TITLE);
  });

  it("removes it from the website when deleted", async () => {
    const { page } = session;
    const slug = await page.getByRole("textbox", { name: "Web address" }).inputValue();
    await page.getByRole("button", { name: "Delete this news item" }).click();
    await page.locator("dialog[open]").getByRole("button", { name: "Delete" }).click();
    await toast(page, /Deleted/);
    id = undefined;
    assert.equal((await publicApi(page, `/news/${slug}`)).status, 404);
  });

  it("raised no security-policy violations", () => {
    assert.deepEqual(session.problems, []);
  });
});
