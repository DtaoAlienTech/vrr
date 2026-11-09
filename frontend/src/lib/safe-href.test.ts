import assert from "node:assert/strict";
import { test } from "node:test";
import { safeHref } from "./safe-href.ts";

test("keeps normal links unchanged", () => {
  for (const href of [
    "/about",
    "/courses/bsc-computer-science",
    "/admissions#enquire",
    "#top",
    "https://example.com/a?b=1",
    "http://example.com",
    "mailto:office@example.com",
    "tel:+911234567890",
  ]) {
    assert.equal(safeHref(href), href);
  }
});

test("trims surrounding spaces", () => {
  assert.equal(safeHref("  /about  "), "/about");
});

test("blocks script and data links", () => {
  for (const href of [
    "javascript:alert(1)",
    "JaVaScRiPt:alert(1)",
    "  javascript:alert(1)",
    "java\nscript:alert(1)",
    "java\tscript:alert(1)",
    "data:text/html;base64,PHNjcmlwdD4=",
    "vbscript:msgbox(1)",
    "file:///etc/passwd",
  ]) {
    assert.equal(safeHref(href), "#", href);
  }
});

test("blocks protocol-relative and backslash tricks", () => {
  for (const href of ["//evil.com", "/\\evil.com", "/\t/evil.com", "/\n/evil.com", "\\\\evil.com"]) {
    assert.equal(safeHref(href), "#", JSON.stringify(href));
  }
});

test("blocks empty and unknown values", () => {
  assert.equal(safeHref(""), "#");
  assert.equal(safeHref("about"), "#");
  assert.equal(safeHref("ftp://example.com"), "#");
});
