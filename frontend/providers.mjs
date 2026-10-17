const guides = {
  zoho: [
    "Open Zoho Invoice and locate your organization ID in Settings.",
    "Select the matching data center here: India, United States or Europe.",
    "Choose Connect Zoho. Sign in on Zoho and accept invoice READ permission.",
    "Return here, fetch a preview, then confirm the INR invoice snapshot.",
  ],
  razorpay: [
    "Open the official Razorpay dashboard and select Test Mode.",
    "In Account & Settings, find API Keys and generate test credentials if authorized.",
    "Enter the test key ID and secret in this form. FinanceGuard encrypts them on its backend.",
    "Fetch the invoice preview. Confirm only after reviewing records and INR amounts.",
  ],
  stripe: [
    "Open Stripe Dashboard and switch to a sandbox or Test Mode.",
    "Open Developers / API keys and create a restricted TEST key.",
    "Grant invoice READ permission only. Use its rk_test_ value in this form.",
    "Fetch a preview, review remaining balances, then confirm the snapshot.",
  ],
};
export function installProviderUI({
  api,
  task: executeTask,
  isSignedIn,
  clearFile,
  account,
}) {
  const $ = (s) => document.querySelector(s);
  let catalog = null,
    preview = null,
    previewAccount = null;
  const message = (text) => {
    $("#provider-feedback").textContent = text;
  };
  const task = (work) =>
    executeTask(async () => {
      try {
        await work();
      } catch (error) {
        message(error.message);
        throw error;
      }
    });
  function render() {
    const provider = $("#provider-select").value;
    const entry = catalog?.providers.find((p) => p.id === provider);
    $("#provider-zoho").hidden = provider !== "zoho";
    $("#provider-key-form").hidden = provider === "zoho";
    $("#razorpay-secret").hidden = provider !== "razorpay";
    $("#provider-connect").textContent =
      provider === "zoho" ? "Connect Zoho" : "Save encrypted test credentials";
    $("#provider-connect").disabled = !entry?.available;
    $("#provider-preview").disabled = !entry?.connected;
    $("#provider-disconnect").disabled = !entry?.connected;
    $("#provider-state").textContent = entry?.connected
      ? "Authorization saved. Fetch a preview to verify current access."
      : entry?.available
        ? "Ready for setup. No account connected."
        : "Setup unavailable: persistent backend or operator OAuth configuration required.";
    $("#provider-docs").href =
      entry?.docs || "https://www.zoho.com/invoice/api/v3/oauth/";
    $("#provider-steps").replaceChildren(
      ...guides[provider].map((text) => {
        const li = document.createElement("li");
        li.textContent = text;
        return li;
      }),
    );
  }
  async function load() {
    catalog = await api("/api/connections");
    $("#provider-host").textContent = catalog.persistent_backend
      ? "Imports use explicit consent and a preview. Agent execution still requires its own approval."
      : "This host uses temporary storage. Provider connections require a persistent backend; use sample invoices or CSV for now.";
    render();
  }
  function reset() {
    preview = null;
    $("#provider-preview-panel").hidden = true;
    $("#provider-key").value = "";
    $("#provider-secret").value = "";
  }
  $("#open-providers").onclick = () => {
    if (!isSignedIn()) {
      $("#sources").close();
      $("#account").showModal();
      return;
    }
    $("#sources").close();
    reset();
    $("#providers").showModal();
    task(load);
  };
  $("#provider-select").onchange = () => {
    reset();
    message("");
    render();
  };
  $("#provider-connect").onclick = () =>
    task(async () => {
      const version = account(),
        provider = $("#provider-select").value;
      if (provider === "zoho") {
        const org = $("#zoho-org").value.trim();
        if (!/^\d+$/.test(org))
          throw Error("Enter the numeric Zoho Invoice organization ID.");
        const result = await api("/api/connections/zoho/start", {
          region: $("#zoho-region").value,
          organization_id: org,
        });
        if (version !== account()) throw Error("Account changed. Start again.");
        window.location.assign(result.url);
        return;
      }
      const body =
        provider === "stripe"
          ? { key: $("#provider-key").value.trim() }
          : {
              key_id: $("#provider-key").value.trim(),
              key_secret: $("#provider-secret").value.trim(),
            };
      $("#provider-key").value = "";
      $("#provider-secret").value = "";
      const result = await api(
        "/api/connections/" + provider + "/credentials",
        body,
      );
      if (version !== account()) return;
      reset();
      message(result.reason);
      await load();
    });
  $("#provider-key-form").onsubmit = (event) => event.preventDefault();
  $("#provider-preview").onclick = () =>
    task(async () => {
      const version = account(),
        provider = $("#provider-select").value;
      reset();
      const result = await api("/api/connections/" + provider + "/preview", {});
      if (version !== account() || provider !== $("#provider-select").value)
        return;
      preview = result.preview_id;
      previewAccount = version;
      $("#provider-preview-panel").hidden = false;
      $("#provider-preview-info").textContent =
        `${result.count} invoices · INR ${result.summary.total_overdue_amount_inr.toLocaleString("en-IN")} overdue. Current workspace remains unchanged until confirmation.`;
      $("#provider-preview-rows").replaceChildren(
        ...result.invoices.map((row) => {
          const p = document.createElement("p");
          p.textContent = `${row.invoice_id} · ${row.customer_name} · INR ${row.amount_inr} · ${row.status}`;
          return p;
        }),
      );
      message(result.reason);
    });
  $("#provider-confirm").onclick = () =>
    task(async () => {
      if (!preview || previewAccount !== account())
        throw Error("Fetch a fresh preview for this account.");
      const result = await api(
        "/api/connections/" + $("#provider-select").value + "/import",
        { preview_id: preview },
      );
      clearFile();
      reset();
      message(`Imported ${result.count} invoices. Prior approvals cleared.`);
      $("#providers").close();
    });
  $("#provider-disconnect").onclick = () =>
    task(async () => {
      await api(
        "/api/connections/" + $("#provider-select").value + "/disconnect",
        {},
      );
      reset();
      message(
        "Connection removed and approvals revoked. Imported records from this source were cleared. Revoke access in the provider dashboard to invalidate credentials globally.",
      );
      await load();
    });
  window.addEventListener("fg-account-changed", () => {
    reset();
    catalog = null;
    $("#provider-preview-rows").replaceChildren();
    $("#zoho-org").value = "";
    message("");
    if ($("#providers").open) $("#providers").close();
  });
  window.addEventListener("fg-task-finished", render);
  $("#providers").addEventListener("close", () => reset());
  let result = new URLSearchParams(window.location.search).get("zoho");
  window.addEventListener("fg-auth-ready", () => {
    if (!result || !isSignedIn()) return;
    const outcome = result;
    result = null;
    $("#sources").close();
    $("#provider-select").value = "zoho";
    $("#providers").showModal();
    message(
      outcome === "connected"
        ? "Zoho consent saved. Fetch your first preview to verify access."
        : "Zoho consent was denied or failed. Start again.",
    );
    task(load);
  });
  if (result) {
    message(
      result === "connected"
        ? "Zoho consent saved. Sign in, open Connections and fetch your first preview."
        : "Zoho consent was denied or could not complete. Start again from Connections.",
    );
    window.history.replaceState(
      null,
      "",
      window.location.pathname + window.location.hash,
    );
  }
}
