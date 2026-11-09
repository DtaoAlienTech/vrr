import assert from "node:assert/strict";
import { test } from "node:test";
import {
  createRedirectCache,
  normalizePath,
  parseRedirects,
  resolveRedirect,
  type RedirectTable,
} from "./redirects.ts";

const row = (fromPath: string, toPath: string, statusCode = 301) => ({ fromPath, toPath, statusCode });

test("parseRedirects keeps good rows and drops anything unsafe", () => {
  const table = parseRedirects([
    row("/old-about", "/about"),
    row("/news/a", "/news/b", 302),
    row("/x", "//evil.com"), // protocol-relative: would leave the site
    row("/y", "https://evil.com"), // absolute address
    row("/z", "/\\evil.com"), // backslash is read as "/" by browsers
    row("/tab", "/a\tb"), // control character
    row("//evil", "/about"),
    row("/same", "/same"),
    row("/same2/", "/same2"),
    row("/bad-status", "/about", 200),
    { fromPath: 5, toPath: "/a", statusCode: 301 },
    null,
    "text",
  ]);
  assert.deepEqual([...table.keys()], ["/old-about", "/news/a"]);
  assert.deepEqual(table.get("/news/a"), { toPath: "/news/b", statusCode: 302 });
});

test("parseRedirects survives a wrong answer from the API", () => {
  for (const data of [null, undefined, {}, "x", 5, []]) assert.equal(parseRedirects(data).size, 0);
});

test("normalizePath ignores a trailing slash but keeps the home page", () => {
  assert.equal(normalizePath("/news/"), "/news");
  assert.equal(normalizePath("/news//"), "/news");
  assert.equal(normalizePath("/"), "/");
});

test("resolveRedirect sends an old address to the new one", () => {
  const table = parseRedirects([row("/news/old", "/news/new")]);
  assert.deepEqual(resolveRedirect(table, "/news/old"), { location: "/news/new", status: 301 });
  assert.deepEqual(resolveRedirect(table, "/news/old/"), { location: "/news/new", status: 301 });
  assert.equal(resolveRedirect(table, "/news/new"), null);
  assert.equal(resolveRedirect(table, "/"), null);
});

test("resolveRedirect keeps the query string", () => {
  const table = parseRedirects([row("/a", "/b"), row("/c", "/d?x=1")]);
  assert.equal(resolveRedirect(table, "/a", "?utm=1")?.location, "/b?utm=1");
  assert.equal(resolveRedirect(table, "/c", "?utm=1")?.location, "/d?x=1");
});

test("resolveRedirect follows a short chain and uses the last status", () => {
  const table = parseRedirects([row("/a", "/b"), row("/b", "/c", 302)]);
  assert.deepEqual(resolveRedirect(table, "/a"), { location: "/c", status: 302 });
});

test("resolveRedirect gives up on a loop instead of redirecting forever", () => {
  const table = parseRedirects([row("/a", "/b"), row("/b", "/a")]);
  assert.equal(resolveRedirect(table, "/a"), null);
  assert.equal(resolveRedirect(table, "/b"), null);
});

test("resolveRedirect gives up on a very long chain", () => {
  const rows = Array.from({ length: 12 }, (_, i) => row(`/p${i}`, `/p${i + 1}`));
  const table = parseRedirects(rows);
  const result = resolveRedirect(table, "/p0");
  // stops after the hop limit, so the visitor still moves forward and the next request continues
  assert.equal(result?.location, "/p5");
});

test("the cache loads once, reuses the table and reloads after the time is up", async () => {
  let clock = 0;
  let loads = 0;
  const cache = createRedirectCache(
    async () => {
      loads += 1;
      return parseRedirects([row("/a", `/b${loads}`)]);
    },
    1_000,
    () => clock,
  );
  assert.equal((await cache.get()).get("/a")?.toPath, "/b1");
  clock = 999;
  assert.equal((await cache.get()).get("/a")?.toPath, "/b1");
  assert.equal(loads, 1);
  clock = 1_000;
  assert.equal((await cache.get()).get("/a")?.toPath, "/b2");
  cache.clear();
  assert.equal((await cache.get()).get("/a")?.toPath, "/b3");
});

test("many requests at once cause one load", async () => {
  let loads = 0;
  const cache = createRedirectCache(async () => {
    loads += 1;
    await new Promise((resolve) => setTimeout(resolve, 10));
    return new Map();
  }, 1_000);
  await Promise.all([cache.get(), cache.get(), cache.get()]);
  assert.equal(loads, 1);
});

test("when the API is down the last good table keeps working", async () => {
  let clock = 0;
  let fail = false;
  const cache = createRedirectCache(
    async (): Promise<RedirectTable> => {
      if (fail) throw new Error("down");
      return parseRedirects([row("/a", "/b")]);
    },
    1_000,
    () => clock,
  );
  assert.equal((await cache.get()).size, 1);
  fail = true;
  clock = 2_000;
  assert.equal((await cache.get()).size, 1); // failed reload: still the old table
  clock = 2_100;
  assert.equal((await cache.get()).size, 1); // retry waits a few seconds, no hammering
});

test("when the API is down from the start the table is empty, not an error", async () => {
  const cache = createRedirectCache(async () => {
    throw new Error("down");
  }, 1_000);
  assert.equal((await cache.get()).size, 0);
});
