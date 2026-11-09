import assert from "node:assert/strict";
import { test } from "node:test";
import { jsonLdString } from "./json-ld.ts";

const LINE_SEPARATOR = String.fromCharCode(0x2028);

test("text from the admin cannot close the script tag", () => {
  const data = { name: "</script><script>alert(1)</script>", note: "<!-- x -->" };
  const out = jsonLdString(data);
  assert.ok(!out.includes("</script"));
  assert.ok(!out.includes("<!--"));
  assert.ok(!out.includes("<"));
});

test("line separators are escaped", () => {
  const out = jsonLdString({ text: `a${LINE_SEPARATOR}b` });
  assert.ok(!out.includes(LINE_SEPARATOR));
});

test("the escaped output still parses back to the same data", () => {
  const data = { name: `A <b> & ${LINE_SEPARATOR} line`, year: 2016, nested: { ok: true } };
  assert.deepEqual(JSON.parse(jsonLdString(data)), data);
});
