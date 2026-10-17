import test from "node:test";
import assert from "node:assert/strict";
import { executionStatus } from "../frontend/execution-status.mjs";
test("manual failure remains visible independently of empty chat history", () => {
  const state = {
    events: [
      { engine: "ARMORIQ", status: "ERROR", reason: "Credential rejected" },
    ],
  };
  assert.deepEqual(executionStatus(state, "armoriq"), {
    title: "Execution needs attention",
    text: "Credential rejected",
  });
});
test("configured key never claims execution, and selected engine is respected", () => {
  assert.equal(
    executionStatus(
      {
        armoriq: { configuration_status: "configured" },
        events: [{ engine: "LOCAL_POLICY", status: "ALLOWED" }],
      },
      "armoriq",
    ).title,
    "Awaiting execution",
  );
});
test("missing configuration and revocation are visible", () => {
  assert.equal(
    executionStatus(
      { armoriq: { issues: [{ message: "Key missing" }] } },
      "armoriq",
    ).text,
    "Key missing",
  );
  assert.equal(
    executionStatus(
      { events: [{ status: "REVOKED", engine: "LOCAL_POLICY" }] },
      "armoriq",
    ).title,
    "Approval revoked",
  );
});
test("expired approval response overrides earlier successful execution", () => {
  assert.equal(
    executionStatus(
      { events: [{ engine: "ARMORIQ", status: "ALLOWED", verified: true }] },
      "armoriq",
      { engine: "armoriq", reason: "Approve a new plan" },
    ).text,
    "Approve a new plan",
  );
});
test("only actual verified result receives badge; approval and denial do not", () => {
  for (const [status, verified, title] of [
    ["ALLOWED", true, "Intent verified"],
    ["APPROVED", false, "Permission approved"],
    ["BLOCKED", false, "Request blocked"],
  ]) {
    assert.equal(
      executionStatus(
        { events: [{ engine: "ARMORIQ", status, verified }] },
        "armoriq",
      ).title,
      title,
    );
  }
});
