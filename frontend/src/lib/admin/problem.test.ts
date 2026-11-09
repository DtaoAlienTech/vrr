import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { parseProblem } from "./problem.ts";

describe("understanding the server's answers", () => {
  it("reads the standard error shape", () => {
    const problem = parseProblem(409, { detail: "That address is taken.", code: "slug_taken" });
    assert.equal(problem.status, 409);
    assert.equal(problem.code, "slug_taken");
    assert.equal(problem.message, "That address is taken.");
    assert.deepEqual(problem.errors, []);
  });

  it("reads field messages and extra data", () => {
    const problem = parseProblem(422, {
      detail: "Please check the fields marked below.",
      code: "validation_error",
      errors: [
        { field: "title", message: "Field required" },
        { field: "title", message: "second message is ignored" },
        { field: "primaryCta.href", message: "bad link" },
        { nope: 1 },
      ],
      usages: [{ entity: "page" }],
    });
    assert.deepEqual(problem.fieldMap(), { title: "Field required", "primaryCta.href": "bad link" });
    assert.deepEqual(problem.extra, { usages: [{ entity: "page" }] });
  });

  it("gives a friendly message for answers that are not in our shape", () => {
    assert.equal(parseProblem(502, "<html>Bad gateway</html>").message, "The server is starting or restarting. Please try again in a moment.");
    assert.equal(parseProblem(404, null).code, "error");
    assert.equal(parseProblem(418, {}).message, "Something went wrong. Please try again.");
    assert.equal(parseProblem(401, undefined).message, "Please sign in again.");
  });
});
