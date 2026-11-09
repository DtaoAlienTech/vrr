import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { formatBytes, formatDate, formatDateTime, fromLocalInput, timeAgo, toLocalInput } from "./format.ts";

describe("dates in India time", () => {
  it("shows dates and times in Asia/Kolkata", () => {
    assert.equal(formatDate("2026-10-28T20:00:00Z"), "29 Oct 2026"); // already the next day in India
    assert.match(formatDateTime("2026-10-28T09:30:00+05:30"), /28 Oct 2026/);
    assert.match(formatDateTime("2026-10-28T09:30:00+05:30"), /9:30\s?am/i);
    assert.equal(formatDate(null), "");
    assert.equal(formatDate("not a date"), "");
  });

  it("converts to and from the date-time input", () => {
    assert.equal(toLocalInput("2026-10-28T04:00:00Z"), "2026-10-28T09:30");
    assert.equal(fromLocalInput("2026-10-28T09:30"), "2026-10-28T04:00:00.000Z");
    assert.equal(fromLocalInput(toLocalInput("2026-01-05T18:45:00Z")!), "2026-01-05T18:45:00.000Z");
    assert.equal(fromLocalInput("28/10/2026"), undefined);
    assert.equal(toLocalInput(null), "");
  });

  it("says how long ago something happened", () => {
    const now = new Date("2026-11-09T12:00:00Z");
    assert.equal(timeAgo("2026-11-09T11:59:40Z", now), "just now");
    assert.equal(timeAgo("2026-11-09T11:55:00Z", now), "5 minutes ago");
    assert.equal(timeAgo("2026-11-09T11:00:00Z", now), "1 hour ago");
    assert.equal(timeAgo("2026-11-08T11:00:00Z", now), "yesterday");
    assert.equal(timeAgo("2026-11-05T12:00:00Z", now), "4 days ago");
    assert.equal(timeAgo("2026-10-01T12:00:00Z", now), "1 Oct 2026");
  });

  it("formats file sizes", () => {
    assert.equal(formatBytes(512), "512 B");
    assert.equal(formatBytes(2048), "2 KB");
    assert.equal(formatBytes(5 * 1024 * 1024), "5.0 MB");
  });
});
