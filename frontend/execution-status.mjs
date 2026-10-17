// Only persisted action evidence can establish execution or verification.
export function executionStatus(state, engine, failure) {
  if (failure?.engine === engine)
    return { title: "Execution needs attention", text: failure.reason };
  const event = state?.events?.find(
    (e) =>
      ["REVOKED", "DECLINED"].includes(e.status) ||
      (engine === "armoriq"
        ? ["ARMORIQ", "ARMORIQ_SDK"].includes(e.engine)
        : ["LOCAL", "LOCAL_POLICY"].includes(e.engine)),
  );
  if (event) {
    const title = {
      APPROVED: "Permission approved",
      BLOCKED: "Request blocked",
      HELD: "Waiting for ArmorIQ review",
      DECLINED: "You declined this request",
      ERROR: "Execution needs attention",
      REVOKED: "Approval revoked",
    }[event.status];
    return {
      title:
        title ||
        (event.verified === true
          ? "Intent verified"
          : "Local / unverified result"),
      text:
        event.status === "APPROVED"
          ? "Ready to run the approved task. No invoice tool has executed yet."
          : event.reason || "No verified execution.",
    };
  }
  const issue = engine === "armoriq" && state?.armoriq?.issues?.[0];
  if (issue) return { title: "Configuration needed", text: issue.message };
  return {
    title: "Awaiting execution",
    text: "Run an approved action in this mode. Configured credentials alone do not prove verification.",
  };
}
