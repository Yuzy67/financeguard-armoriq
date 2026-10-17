import test from "node:test";
import assert from "node:assert/strict";
import { executionStatus, activityCounts } from "../frontend/execution-status.mjs";
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
    ["ALLOWED", true, "SDK reports verified"],
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

test("ArmorIQ holds remain distinct from denials and verification", () => {
  const state = { events: [{ engine: "ARMORIQ", status: "HELD", reason: "Reviewer approval required", verified: false }] };
  assert.deepEqual(executionStatus(state, "armoriq"), { title: "Waiting for ArmorIQ review", text: "Reviewer approval required" });
});
test("declining permission remains visible without claiming a provider denial", () => {
  const state = { events: [{ engine: "APPLICATION_CONSENT", status: "DECLINED", reason: "You declined this request." }] };
  assert.equal(executionStatus(state, "armoriq").title, "You declined this request");
});


test("activity never counts approvals, holds, local blocks or malformed truthy flags as SDK executions", () => {
  const events = [
    { status: "ALLOWED", engine: "LOCAL_POLICY", verified: false },
    { status: "BLOCKED", engine: "LOCAL_POLICY", verified: false },
    { status: "APPROVED", engine: "ARMORIQ", verified: true },
    { status: "HELD", engine: "ARMORIQ", verified: true },
    { status: "ERROR", engine: "ARMORIQ", verified: true },
    { status: "ALLOWED", engine: "LOCAL_POLICY", verified: true },
    { status: "ALLOWED", engine: "ARMORIQ", verified: "true" },
    { status: "ALLOWED", engine: "ARMORIQ", verified: true },
  ];
  assert.deepEqual(activityCounts(events), { completed: 4, blocked: 1, sdkReportedVerified: 1 });
  assert.deepEqual(activityCounts([]), { completed: 0, blocked: 0, sdkReportedVerified: 0 });
});

import { ensureWorkspace } from "../frontend/workspace-session.mjs";
test("startup reuses existing workspace without creating a demo", async () => {
  let starts = 0, reads = 0;
  await ensureWorkspace(async () => starts++, async () => reads++);
  assert.equal(starts, 0); assert.equal(reads, 1);
});
test("startup creates a sample only after a real 401", async () => {
  let starts = 0, reads = 0;
  await ensureWorkspace(async (path) => { assert.equal(path, "/api/demo"); starts++; }, async () => {
    if (++reads === 1) throw Object.assign(new Error("Sign in"), { httpStatus: 401 });
  });
  assert.equal(starts, 1); assert.equal(reads, 2);
});
test("network and server failures never reset the user's workspace", async () => {
  for (const httpStatus of [undefined, 403, 500, 503]) {
    let starts = 0;
    await assert.rejects(ensureWorkspace(async () => starts++, async () => {
      throw Object.assign(new Error("unavailable"), { httpStatus });
    }));
    assert.equal(starts, 0);
  }
});
