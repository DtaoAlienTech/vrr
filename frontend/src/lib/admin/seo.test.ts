import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { lengthCheck, seoChecks, serpPreview } from "./seo.ts";

describe("search-engine checks", () => {
  it("checks title and description lengths", () => {
    assert.equal(lengthCheck("t", "Title", "", 30, 60).status, "bad");
    assert.equal(lengthCheck("t", "Title", "Short", 30, 60).status, "warn");
    assert.equal(lengthCheck("t", "Title", "A good length title for a notice about admissions", 30, 60).status, "ok");
    assert.equal(lengthCheck("t", "Title", "x".repeat(61), 30, 60).status, "warn");
  });

  it("checks headings, photo descriptions and links of a page", () => {
    const checks = seoChecks({
      title: "About VRR Degree College in Kallur, Piler Road",
      description: "x".repeat(100),
      h1Count: 2,
      photosWithoutText: 1,
      pageData: { sections: [{ href: "/about" }, { href: "/missing" }] },
      knownPaths: ["/", "/about"],
    });
    const byId = Object.fromEntries(checks.map((c) => [c.id, c.status]));
    assert.deepEqual(byId, { title: "ok", description: "ok", h1: "bad", alt: "bad", links: "bad" });
    const good = seoChecks({ h1Count: 1, photosWithoutText: 0, pageData: {}, knownPaths: [] });
    assert.deepEqual(good.map((c) => c.status), ["ok", "ok", "ok"]);
    assert.equal(seoChecks({ h1Count: 0 })[0].status, "bad");
  });

  it("shows how the page looks on Google", () => {
    const preview = serpPreview({
      title: "Admissions open",
      template: "%s | VRR Degree College",
      description: "y".repeat(200),
      origin: "https://vrrcollege.edu.in",
      path: "/news/admissions-open",
    });
    assert.equal(preview.title, "Admissions open | VRR Degree College");
    assert.equal(preview.url, "vrrcollege.edu.in › news › admissions-open");
    assert.equal(preview.description.length, 160);
    assert.equal(serpPreview({ title: "x".repeat(80), template: "%s", description: "d", origin: "http://a.b", path: "/" }).title.length, 60);
  });
});
