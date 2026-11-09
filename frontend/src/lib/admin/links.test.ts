import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { brokenSitePaths, collectLinks, isSafeHref } from "./links.ts";

describe("link safety (same rule as the server)", () => {
  it("accepts site paths, anchors, https, mailto and tel", () => {
    for (const ok of ["/", "/courses", "/news/open-day", "#apply", "https://example.com/a?b=1", "mailto:a@b.co", "tel:+919876543210", "HTTPS://EXAMPLE.COM"]) {
      assert.equal(isSafeHref(ok), true, ok);
    }
  });

  it("refuses everything else", () => {
    for (const bad of ["", "   ", "javascript:alert(1)", "JaVaScRiPt:x", "data:text/html,x", "//evil.com", "/\\evil.com", "/\t/evil.com", "/\n/evil.com", "http://insecure.example", "https://", "ftp://x.y", "evil.com", "/a\\b", "x".repeat(501)]) {
      assert.equal(isSafeHref(bad), false, JSON.stringify(bad));
    }
  });
});

describe("checking the links of a page", () => {
  it("finds every href in nested data", () => {
    const data = { items: [{ href: "/a" }, { nested: { href: "https://x.y" } }], href: "/top", label: "href" };
    assert.deepEqual(collectLinks(data).sort(), ["/a", "/top", "https://x.y"]);
    assert.deepEqual(collectLinks(null), []);
  });

  it("finds site paths that lead nowhere", () => {
    const known = ["/", "/about", "/courses", "/news"];
    const links = ["/about", "/about/", "/courses/bsc-computer-science", "/news?page=2", "/missing", "/gone/page", "https://x.y/missing", "#top", "mailto:a@b.co", "//evil.example"];
    assert.deepEqual(brokenSitePaths(links, known), ["/missing", "/gone/page"]);
  });
});
