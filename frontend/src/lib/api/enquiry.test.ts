import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { submitEnquiry } from "./enquiry.ts";

const realFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = realFetch;
});

const reply = (status: number) => async () => new Response(null, { status });
const payload = { name: "Asha", phone: "9876543210" };

test("201 means the enquiry was saved", async () => {
  globalThis.fetch = reply(201);
  assert.deepEqual(await submitEnquiry(payload), { ok: true });
});

test("each failure gives a clear message", async () => {
  for (const status of [400, 403, 422, 429, 500, 503]) {
    globalThis.fetch = reply(status);
    const result = await submitEnquiry(payload);
    assert.equal(result.ok, false);
    assert.ok("message" in result && result.message.length > 10, String(status));
  }
});

test("a network failure is reported, not thrown", async () => {
  globalThis.fetch = async () => {
    throw new TypeError("network down");
  };
  const result = await submitEnquiry(payload);
  assert.equal(result.ok, false);
});

test("posts JSON to the public enquiries address", async () => {
  let seen: { url: string; init: RequestInit } | undefined;
  globalThis.fetch = async (url, init) => {
    seen = { url: String(url), init: init ?? {} };
    return new Response(null, { status: 201 });
  };
  await submitEnquiry(payload);
  assert.equal(seen?.url, "/api/v1/public/enquiries");
  assert.equal(seen?.init.method, "POST");
  assert.deepEqual(JSON.parse(String(seen?.init.body)), payload);
});
