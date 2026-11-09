import assert from "node:assert/strict";
import { test } from "node:test";
import { dateParts, initials } from "./format.ts";

test("splits an ISO date for display", () => {
  assert.deepEqual(dateParts("2026-10-05"), { day: "05", monthYear: "OCT 2026", long: "5 Oct 2026" });
  assert.equal(dateParts("2026-01-28").long, "28 Jan 2026");
});

test("builds initials from the first two words", () => {
  assert.equal(initials("Asha Reddy"), "AR");
  assert.equal(initials("  dr  k  s  rao "), "DK");
  assert.equal(initials("Madonna"), "M");
  assert.equal(initials(""), "");
});
