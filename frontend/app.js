import { installProviderUI } from "./providers.mjs";
import { executionStatus } from "./execution-status.mjs";
const $ = (s) => document.querySelector(s),
  money = (n) =>
    new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 2,
    }).format(n);
let state = null,
  auth = null,
  user = null,
  busy = false,
  filter = "all",
  pendingCSV = "",
  revision = 0,
  authReady = false;
let linkedFile = null,
  pendingHandle = null,
  pendingRevision = -1;
let lastRequestFailure = null;
let conversation = null,
  chatSnapshot = "",
  linkedSnapshot = "",
  autoSync = false,
  watchingFile = false;
const $all = (s) => document.querySelectorAll(s);
function el(tag, text, cls) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (cls) node.className = cls;
  return node;
}
async function api(path, body) {
  const headers = {};
  if (user) headers.Authorization = "Bearer " + (await user.getIdToken());
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const controller = new AbortController(),
    timer = setTimeout(
      () => controller.abort(),
      ["/api/agent", "/api/chat/approve"].includes(path) ? 90000 : 45000,
    );
  try {
    const response = await fetch(path, {
      method: body !== undefined ? "POST" : "GET",
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    let data;
    try {
      data = await response.json();
    } catch {
      throw Error(
        "The server returned an unreadable response. Check deployment health and retry.",
      );
    }
    if (!response.ok) {
      const error = Error(
        data.reason ||
          data.detail ||
          "Request failed (" + response.status + ")",
      );
      error.integration = data;
      error.requestPath = path;
      throw error;
    }
    if (data.status) data.status = data.status.toUpperCase();
    return data;
  } catch (error) {
    if (error.name === "AbortError")
      throw Error(
        "The request timed out. Check the action trail before retrying.",
      );
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
let toastTimer;
function toast(text, kind = "info") {
  const node = $("#toast");
  node.textContent = text;
  node.dataset.kind = kind;
  node.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (node.hidden = true), 6500);
}
function route() {
  const aliases = {
      home: "invoices",
      overview: "invoices",
      sources: "invoices",
      agent: "security",
    },
    hash = location.hash.slice(1);
  const active =
    aliases[hash] ||
    (["invoices", "security", "audit"].includes(hash) ? hash : "invoices");
  $all("[data-view]").forEach(
    (node) => (node.hidden = node.dataset.view !== active),
  );
  $all("[data-route]").forEach((link) => {
    link.classList.toggle("selected", link.dataset.route === active);
    if (link.dataset.route === active)
      link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  $("#page-title").textContent = {
    overview: "Overview",
    invoices: "Invoices",
    security: "Assistant & permissions",
    audit: "Activity",
  }[active];
}
const traceStatus = el(
  "p",
  "No SDK trace captured in this workspace.",
  "muted",
);
traceStatus.id = "trace-status";
$("#verified-text").after(traceStatus);
window.addEventListener("hashchange", () => {
  route();
  window.scrollTo({
    top: 0,
    behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
      ? "instant"
      : "smooth",
  });
});
route();

function download(name, data) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
  );
  const link = el("a", "");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function bubble(text, who = "assistant") {
  const div = el("div", text, "bubble " + who);
  $("#messages").append(div);
  $("#messages").scrollTop = $("#messages").scrollHeight;
  return div;
}
function richText(node, text) {
  for (const line of text.split("\n")) {
    const paragraph = el(
      "p",
      "",
      line.startsWith("- ") ? "chat-list-line" : "",
    );
    const parts = line.replace(/^#{1,4}\s+/, "").split(/\*\*([^*]+)\*\*/g);
    parts.forEach((part, index) =>
      paragraph.append(
        index % 2 ? el("strong", part) : document.createTextNode(part),
      ),
    );
    node.append(paragraph);
  }
}
function renderConversation(next) {
  conversation = next;
  $("#messages").replaceChildren();
  if (!next.messages.length) {
    const welcome = el("div", "", "chat-welcome");
    welcome.append(
      el("span", "✦", "welcome-mark"),
      el("h2", "What needs your attention today?"),
      el(
        "p",
        "Ask a question, work through overdue invoices, or prepare your next follow-up. You approve access before invoice tools run.",
      ),
    );
    $("#messages").append(welcome);
  }
  for (const item of next.messages) {
    const message = bubble("", item.role);
    message.append(
      el(
        "span",
        item.role === "user" ? "YOU" : "FINANCEGUARD",
        "message-author",
      ),
    );
    richText(message, item.content);
    for (const action of item.actions || []) {
      const proof = el("div", "", "chat-tool-result");
      proof.append(
        el("span", action.status, "status " + action.status),
        el("p", action.reason),
      );
      proof.append(
        el(
          "small",
          action.verified === true
            ? "ArmorIQ SDK verified=True"
            : (action.event?.engine || "Application") +
                " · No ArmorIQ verification claimed",
        ),
      );
      if (action.result) {
        if (action.result.overdue_invoice_count !== undefined)
          proof.append(
            el(
              "p",
              `${action.result.overdue_invoice_count} overdue invoices · ${money(action.result.total_overdue_amount_inr)}`,
              "actual-total",
            ),
          );
        const details = el("details", "");
        details.append(
          el("summary", "Inspect actual tool result"),
          el("pre", JSON.stringify(action.result, null, 2)),
        );
        const save = el(
          "button",
          action.result.drafts ? "Download reminder drafts" : "Download result",
        );
        save.onclick = () =>
          download("financeguard-result.json", action.result);
        proof.append(details, save);
      }
      message.append(proof);
    }
  }
  renderVerification();
  const pending = next.pending;
  $("#chat-pending").replaceChildren();
  $("#chat-pending").hidden = !pending;
  if (pending) {
    const name =
      [...$("#tool").options]
        .find((option) => option.value === pending.tool)
        ?.textContent.trim() || pending.tool;
    const card = el("div", "", "pending-card");
    card.append(
      el("span", "YOUR PERMISSION IS REQUIRED", "eyebrow"),
      el("h3", name),
      el(
        "p",
        (pending.engine === "armoriq"
          ? "ArmorIQ protection"
          : "Local policy · No ArmorIQ verification") +
          " · Current invoice snapshot · Five-minute permission",
      ),
      el(
        "p",
        "The result will be shared with the AI model to prepare its answer. Refunds, transfers, deletion, and sending emails are excluded.",
      ),
    );
    const approve = el("button", "Approve & run this task", "primary");
    approve.onclick = () =>
      task(async () => {
        const result = await api("/api/chat/approve", {
          request_id: pending.id,
        });
        renderConversation(result.conversation);
        status(result.reply, result.status === "ERROR" ? "error" : "info");
      });
    card.append(approve);
    $("#chat-pending").append(card);
  }
  $("#chat-usage").textContent = next.usage?.total_tokens
    ? next.usage.total_tokens.toLocaleString() + " tokens this conversation"
    : "No reported token usage";
  $("#messages").scrollTop = $("#messages").scrollHeight;
}
async function loadConversation() {
  const version = revision;
  const next = await api("/api/chat");
  if (version === revision) renderConversation(next);
}
function status(text, kind = "info") {
  $("#result").textContent = text;
  $("#result").dataset.kind = kind;
}
function renderVerification() {
  const evidence = executionStatus(
    state,
    $("#engine").value,
    lastRequestFailure,
  );
  $("#verified-title").textContent = evidence.title;
  $("#verified-text").textContent = evidence.text;
}
function render() {
  if (!state) return;
  renderVerification();
  const lastProviderEvent = state.events.find(
    (e) => e.engine === "ARMORIQ" || e.engine === "ARMORIQ_SDK",
  );
  $("#armoriq-connection").textContent = state.armoriq?.issues?.length
    ? "ArmorIQ: " + state.armoriq.issues.map((issue) => issue.message).join(" ")
    : lastProviderEvent?.verified === true
      ? "ArmorIQ: latest SDK execution verified"
      : lastProviderEvent?.status === "ERROR"
        ? "ArmorIQ: setup / execution needs attention"
        : "ArmorIQ: key configured; live execution not verified";
  const latestTrace = state.events.find((e) => e.observability)?.observability;
  $("#trace-status").textContent = latestTrace
    ? "SDK session " +
      latestTrace.session_id +
      " · latest trace delivery " +
      latestTrace.delivery +
      " (accepted " +
      latestTrace.accepted +
      ", rejected " +
      latestTrace.rejected +
      "). Console visibility not independently confirmed."
    : "No SDK trace captured in this workspace. Local activity is not a cloud audit log.";
  if (latestTrace?.agent_id) {
    $("#trace-status").textContent += " Agent: " + latestTrace.agent_id +
      " · organization: " + latestTrace.organization_id +
      " · MCP record: " + (latestTrace.mcp_server_id || "not resolved") +
      " · registry identity: " + (latestTrace.agent_registry_verified ? "matched bootstrap identity" : "unconfirmed");
  }
  const policyReceipt = latestTrace?.runtime_policy;
  if (policyReceipt) {
    $("#trace-status").textContent += policyReceipt.source === "ARMORIQ_ENFORCEMENT_API"
      ? " · enforcement HTTP " + policyReceipt.http_status + ", decision " +
        (policyReceipt.response_valid ? (policyReceipt.allowed ? "ALLOW" : "DENY") : "invalid response") +
        ". Policy target and dashboard record require independent confirmation."
      : " · SDK intent binding denied before proxy execution; not a cloud policy decision.";
  }
  $("#storage-notice").hidden = !state.temporary_storage;
  $("#identity").textContent = state.user.signed_in
    ? state.user.email
    : "Sample workspace";
  $("#account-open").hidden = state.user.signed_in;
  $("#logout").hidden = !state.user.signed_in;
  $("#connection").textContent =
    $("#engine").value === "armoriq"
      ? state.armoriq_configured
        ? "ArmorIQ key configured · execution depends on registered MCP availability"
        : "ArmorIQ backend key required"
      : "Local workspace active · execution is protected by the local plan";
  $("#source-label").textContent =
    "Invoice source: " +
    ({
      sample: "Sample dataset",
      upload: "Your CSV import",
      stripe_sandbox: "Stripe sandbox",
      zoho: "Zoho Invoice snapshot",
      razorpay: "Razorpay test snapshot",
      stripe: "Stripe test snapshot",
    }[state.source] || state.source);
  $("#linked-status").textContent =
    linkedFile && state.source === "upload"
      ? linkedFile.name +
        " · Connected for this session. Refresh to preview changes."
      : state.source === "upload"
        ? "Imported snapshot · Upload again or link a file to refresh your records."
        : state.source === "sample"
          ? "Example records · Add your own invoice source when ready."
          : "Provider snapshot · Open Connections to fetch an updated preview.";
  $("#refresh-file").hidden = !linkedFile || state.source !== "upload";
  $("#auto-sync-control").hidden = !linkedFile || state.source !== "upload";
  $("#auto-sync").checked = autoSync;
  if (autoSync && linkedFile)
    $("#linked-status").textContent =
      linkedFile.name +
      " · Auto-sync on while this page is open. Changes clear old approvals.";
  const assistant = state.assistant || {};
  $("#request").disabled = busy || !authReady || !state.user.signed_in;
  $("#chat .primary").disabled =
    busy || !authReady || !state.user.signed_in || !assistant.configured;
  $("#new-chat").disabled = busy || !authReady;
  $("#model-label").textContent = assistant.configured
    ? assistant.model + " · OpenRouter"
    : "OpenRouter · Setup required";
  $("#assistant-note").textContent = !state.user.signed_in
    ? "Sign in to use AI chat. You can try the sample tools through Permissions."
    : assistant.configured
      ? "AI can make mistakes. Review source records and actual tool results. Tool results are shared with the model after approval."
      : "OPENROUTER_API_KEY is required on the backend. No model response is fabricated.";
  $("#chat-protection").textContent =
    $("#engine").value === "armoriq"
      ? "ArmorIQ protection selected · Provider must verify execution"
      : "Local policy · No ArmorIQ verification";
  $("#nav-count").textContent = state.invoices.length;
  $("#total-invoices").textContent = state.invoices.length;
  $("#outstanding-amount").textContent = money(
    state.invoices
      .filter((i) => ["unpaid", "pending", "overdue"].includes(i.status))
      .reduce((sum, i) => sum + i.amount_inr, 0),
  );
  const paid = state.invoices.filter((i) => i.status === "paid");
  $("#paid-amount").textContent = money(
    paid.reduce((sum, i) => sum + i.amount_inr, 0),
  );
  $("#paid-count").textContent =
    paid.length + (paid.length === 1 ? " paid invoice" : " paid invoices");
  if (
    $("#source-feedback").textContent.startsWith("Sign in to import") &&
    state.user.signed_in
  )
    $("#source-feedback").textContent =
      "Signed in. You can preview and import invoices into your workspace.";
  $("#amount").textContent = money(state.summary.total_overdue_amount_inr);
  $("#count").textContent = state.summary.overdue_invoice_count;
  $("#blocked").textContent = state.events.filter(
    (e) => e.status === "BLOCKED",
  ).length;
  $("#approved-count").textContent = state.events.filter(
    (e) => e.status === "ALLOWED",
  ).length;
  $("#verified-count").textContent = state.events.filter(
    (e) => e.verified === true,
  ).length;
  const plan = state.plans[$("#engine").value];
  $("#plan-badge").textContent = plan
    ? "Approved · " +
      Math.max(0, Math.ceil((plan.expires - Date.now() / 1000) / 60)) +
      " min"
    : "No active plan";
  $("#plan-tool").textContent =
    $("#tool").selectedOptions[0].textContent.trim();
  $("#run").disabled = busy || !plan;
  $("#approve").disabled = busy;
  $("#invoice-count").textContent = "(" + state.invoices.length + ")";
  $("#date-note").textContent =
    state.source === "sample"
      ? "Sample dataset: fixed dates and statuses from the original demo."
      : "Your imported snapshot. Overdue status was calculated at import; sync or import again to refresh it.";
  if ($("#stripe-state"))
    $("#stripe-state").textContent = state.stripe_configured
      ? "Backend credentials configured · operator-only test sync"
      : "Not configured · sandbox key required on backend";
  $("#rows").replaceChildren();
  const search = $("#invoice-search").value.trim().toLocaleLowerCase();
  const visible = state.invoices.filter(
    (i) =>
      (filter === "all" || i.status === filter) &&
      (i.invoice_id + " " + i.customer_name)
        .toLocaleLowerCase()
        .includes(search),
  );
  const sort = $("#invoice-sort").value;
  visible.sort((a, b) =>
    sort === "amount"
      ? b.amount_inr - a.amount_inr
      : sort === "customer"
        ? a.customer_name.localeCompare(b.customer_name)
        : a.due_date.localeCompare(b.due_date),
  );
  $("#visible-count").textContent =
    `Showing ${visible.length} of ${state.invoices.length} invoices`;
  for (const i of visible) {
    const row = el("tr", ""),
      name = el("td", "");
    const invoiceButton = el("button", i.invoice_id, "invoice-link");
    invoiceButton.onclick = () => openInvoice(i);
    name.append(invoiceButton);
    name.append(el("small", i.customer_name));
    const cell = el("td", "");
    cell.append(el("span", i.status, "status " + i.status));
    row.append(
      name,
      el("td", money(i.amount_inr)),
      el("td", formatDate(i.due_date)),
      cell,
      el("td", i.days_overdue ? i.days_overdue + " days" : "—"),
    );
    const detailCell = el("td", ""),
      detailButton = el("button", "↗", "row-arrow");
    detailButton.setAttribute("aria-label", "View " + i.invoice_id);
    detailButton.onclick = () => openInvoice(i);
    detailCell.append(detailButton);
    row.append(detailCell);
    $("#rows").append(row);
  }
  if (!$("#rows").children.length) {
    const tr = el("tr", "");
    const td = el("td", "No invoices match this filter.");
    td.colSpan = 6;
    tr.append(td);
    $("#rows").append(tr);
  }
  $("#events").replaceChildren();
  if (!state.events.length)
    $("#events").append(
      el(
        "p",
        "Your first action will start the trail. No prefilled decisions.",
        "muted",
      ),
    );
  const auditFilter = $("#audit-filter").value;
  const filtered = state.events.filter(
    (e) => auditFilter === "all" || e.status === auditFilter,
  );
  if (state.events.length && !filtered.length)
    $("#events").append(el("p", "No activity matches this filter.", "muted"));
  for (const e of filtered) {
    const row = el("div", "", "event"),
      details = el("div", "");
    details.append(
      el("b", e.action),
      el("p", e.reason),
      el(
        "small",
        e.engine +
          " · " +
          (e.verified ? "SDK verified=True" : "No cloud verification"),
      ),
    );
    if (e.observability) {
      const proof = el("details", "", "trace-details");
      proof.append(
        el("summary", "SDK trace / delivery details"),
        el("p", "Session: " + (e.observability.session_id || "unavailable")),
        el("p", "Trace IDs: " + (e.observability.trace_ids || []).join(", ")),
        el(
          "p",
          "Telemetry delivery: " +
            e.observability.delivery +
            " · accepted " +
            e.observability.accepted +
            " · rejected " +
            e.observability.rejected,
        ),
        el(
          "p",
          "SDK-generated correlation IDs. Console visibility is not independently confirmed.",
        ),
      );
      details.append(proof);
    }
    row.append(
      el(
        "time",
        new Date(e.timestamp).toLocaleString("en-IN", {
          day: "2-digit",
          month: "short",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }),
      ),
      details,
      el("span", e.status, "status " + e.status),
    );
    $("#events").append(row);
  }
}
async function refresh() {
  const version = revision;
  const next = await api("/api/state");
  if (version === revision) {
    if (state?.user?.uid !== next.user.uid) lastRequestFailure = null;
    state = next;
    render();
    const snapshot = JSON.stringify(next.invoices) + next.user.uid;
    if (snapshot !== chatSnapshot) {
      chatSnapshot = snapshot;
      await loadConversation();
    }
  }
}
async function task(work) {
  if (busy) return;
  if (!authReady) {
    toast("Finishing the sign-in check. Try again in a moment.");
    return;
  }
  busy = true;
  lastRequestFailure = null;
  const active =
    document.activeElement?.tagName === "BUTTON"
      ? document.activeElement
      : null;
  const previous = active?.textContent;
  if (active) {
    active.textContent = "Working…";
    active.setAttribute("aria-busy", "true");
  }
  $all("button:not([data-close])").forEach((b) => (b.disabled = true));
  try {
    await work();
  } catch (e) {
    if (
      [
        "/api/approve",
        "/api/execute",
        "/api/attempt-refund",
        "/api/run-approved-action",
        "/api/chat/approve",
      ].includes(e.requestPath)
    ) {
      lastRequestFailure = { engine: $("#engine").value, reason: e.message };
      renderVerification();
    }
    status(e.message, "error");
    toast(e.message, "error");
    bubble(e.message);
  } finally {
    busy = false;
    if (active) {
      active.textContent = previous;
      active.removeAttribute("aria-busy");
    }
    $all("button").forEach((b) => (b.disabled = false));
    await refresh().catch((e) => {
      $("#connection").textContent = e.message;
      toast(e.message, "error");
    });
    window.dispatchEvent(new Event("fg-task-finished"));
  }
}

function outcome(data) {
  data.status = (data.status || "ERROR").toUpperCase();
  const kind =
    data.status === "BLOCKED"
      ? "blocked"
      : data.status === "ERROR"
        ? "error"
        : data.status === "ALLOWED"
          ? "success"
          : "info";
  status(data.status + " · " + (data.reason || ""), kind);
  toast(data.reason || data.status, kind);
  const message = bubble(data.status + " · " + (data.reason || ""));
  if (data.event && state) {
    state.events = [
      data.event,
      ...state.events.filter((event) => event.id !== data.event.id),
    ];
  }
  renderVerification();
  if (data.result) {
    const result = data.result;
    if (result.overdue_invoice_count !== undefined)
      message.append(
        el(
          "p",
          `${result.overdue_invoice_count} overdue invoices · ${money(result.total_overdue_amount_inr)}`,
        ),
      );
    else if (result.drafts) {
      for (const draft of result.drafts) {
        const card = el("details", "");
        card.append(
          el("summary", draft.invoice_id + " · Draft reminder"),
          el("p", draft.body),
        );
        message.append(card);
      }
      message.append(el("p", "Drafts only. No emails sent."));
    } else if (result.invoices && !result.report)
      message.append(
        el("p", `${result.invoices.length} invoice records returned.`),
      );
    else {
      const details = el("details", "");
      details.append(
        el("summary", "Inspect tool result"),
        el("pre", JSON.stringify(result, null, 2)),
      );
      message.append(details);
    }
    const save = el(
      "button",
      result.report ? "Download report" : "Download tool result",
    );
    save.onclick = () => download("financeguard-result.json", result);
    message.append(save);
  }
}
$("#approve").onclick = () =>
  task(async () =>
    outcome(
      await api("/api/approve", {
        tool: $("#tool").value,
        engine: $("#engine").value,
      }),
    ),
  );
const revoke = el("button", "Revoke approvals");
revoke.style.marginTop = "10px";
$("#approve").after(revoke);
revoke.onclick = () => task(async () => outcome(await api("/api/revoke", {})));
$("#run").onclick = () =>
  task(async () =>
    outcome(
      await api(
        (state.plans[$("#engine").value]?.tool || $("#tool").value) ===
          "summarize_overdue_invoices"
          ? "/api/run-approved-action"
          : "/api/execute",
        {
          tool: state.plans[$("#engine").value]?.tool || $("#tool").value,
          engine: $("#engine").value,
        },
      ),
    ),
  );
for (const [id, tool] of [
  ["refund", "simulate_refunds"],
  ["transfer", "transfer_funds"],
  ["delete", "delete_invoices"],
])
  $("#" + id).onclick = () =>
    task(async () =>
      outcome(
        await api(
          tool === "simulate_refunds" ? "/api/attempt-refund" : "/api/execute",
          { tool, engine: $("#engine").value },
        ),
      ),
    );
$("#chat").onsubmit = (e) => {
  e.preventDefault();
  const text = $("#request").value.trim();
  if (!text || busy) return;
  $("#request").value = "";
  bubble(text, "user");
  task(async () => {
    const thinking = bubble("Thinking through your request…", "thinking");
    try {
      const result = await api("/api/agent", {
        message: text,
        engine: $("#engine").value,
      });
      renderConversation(result.conversation);
    } finally {
      thinking.remove();
    }
  });
};
$("#request").onkeydown = (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    $("#chat").requestSubmit();
  }
};
$("#new-chat").onclick = () =>
  task(async () => renderConversation(await api("/api/chat/new", {})));
$("#show-permissions").onclick = () => $("#permissions").showModal();
$all("[data-message]").forEach(
  (b) =>
    (b.onclick = () => {
      $("#request").value = b.dataset.message;
      $("#chat").requestSubmit();
    }),
);
$("#tool").onchange = render;
$("#engine").onchange = () => {
  $("#engine-help").textContent =
    $("#engine").value === "local"
      ? "Runs against your workspace invoices. Local decisions are never labeled as ArmorIQ verification."
      : "Executes via ArmorIQ and the registered workspace-scoped MCP origin. Requires a healthy registered HTTPS MCP origin in the same organization. Out-of-plan requests may be rejected by the SDK before proxy execution.";
  $("#verified-title").textContent = "Awaiting execution";
  $("#verified-text").textContent =
    "Run an action in this mode to inspect its result.";
  render();
};
$all("[data-filter]").forEach(
  (b) =>
    (b.onclick = () => {
      filter = b.dataset.filter;
      $all("[data-filter]").forEach((x) =>
        x.classList.toggle("selected", x === b),
      );
      render();
    }),
);
$("#sample").onclick = () =>
  task(async () => {
    if (
      state?.source !== "sample" &&
      !window.confirm(
        "Replace your imported invoices with the sample dataset? Existing approvals will be cleared.",
      )
    )
      return;
    await api("/api/source/sample", {});
    linkedFile = null;
    autoSync = false;
    linkedSnapshot = "";
    $("#sources").close();
    $("#source-feedback").textContent =
      "Sample invoices loaded. Prior plans cleared.";
  });
if ($("#stripe"))
  $("#stripe").onclick = () =>
    task(async () => {
      const d = await api("/api/source/stripe", {});
      $("#source-feedback").textContent = `Synced ${d.count} test invoices.`;
    });
async function previewFile(file, handle = null) {
  pendingCSV = "";
  pendingHandle = null;
  pendingRevision = -1;
  const version = revision;
  if (file.size > 650000) throw Error("Use a CSV smaller than 650 KB.");
  const csv = await file.text();
  const d = await api("/api/import", { csv });
  if (version !== revision)
    throw Error("Account changed. Select the file again.");
  pendingCSV = csv;
  pendingHandle = handle;
  pendingRevision = version;
  $("#preview-info").textContent =
    `${file.name} · ${d.count} invoices · All amounts INR. Showing the first five. Confirming replaces the current workspace snapshot.`;
  $("#preview-rows").replaceChildren();
  for (const row of d.invoices.slice(0, 5))
    $("#preview-rows").append(
      el(
        "p",
        `${row.invoice_id} · ${row.customer_name} · ${money(row.amount_inr)} · ${row.status}`,
      ),
    );
  $("#sources").close();
  $("#import-preview").showModal();
}
$("#csv").onchange = () => {
  const file = $("#csv").files[0];
  $("#csv").value = "";
  if (file) task(() => previewFile(file));
};
$("#link-file").onclick = async () => {
  if (busy) return;
  if (!state?.user.signed_in) {
    $("#sources").close();
    $("#account").showModal();
    toast("Sign in before connecting your own invoices.");
    return;
  }
  if (!("showOpenFilePicker" in window)) {
    toast(
      "File linking is unavailable in this browser. Choose CSV to import a snapshot instead.",
    );
    return;
  }
  try {
    const version = revision;
    const [handle] = await window.showOpenFilePicker({
      multiple: false,
      types: [{ description: "Invoice CSV", accept: { "text/csv": [".csv"] } }],
    });
    if (version !== revision) return;
    await task(async () => previewFile(await handle.getFile(), handle));
  } catch (error) {
    if (error.name !== "AbortError")
      toast(
        "Could not open the file. Choose CSV to import it instead.",
        "error",
      );
  }
};
$("#refresh-file").onclick = () =>
  task(async () => {
    const handle = linkedFile;
    if (!handle) throw Error("Link your invoice file first.");
    try {
      await previewFile(await handle.getFile(), handle);
    } catch (error) {
      if (["NotAllowedError", "NotFoundError"].includes(error.name))
        throw Error(
          "File access expired or the file moved. Reconnect it through Manage source.",
        );
      throw error;
    }
  });
$("#confirm-import").onclick = () =>
  task(async () => {
    if (!pendingCSV || pendingRevision !== revision)
      throw Error("Preview your file again before importing.");
    const version = revision,
      handle = pendingHandle;
    const d = await api("/api/import", { csv: pendingCSV, confirm: true });
    if (version !== revision) return;
    linkedFile = handle;
    linkedSnapshot = pendingCSV;
    autoSync = false;
    $("#import-preview").close();
    pendingCSV = "";
    pendingHandle = null;
    pendingRevision = -1;
    $("#source-feedback").textContent =
      `Imported ${d.count} invoices. Approve a new plan to use them.`;
    toast(`Imported ${d.count} invoices. Your workspace is ready.`, "success");
    location.hash = "invoices";
  });
$("#auto-sync").onchange = () => {
  if (!linkedFile || !state?.user.signed_in) {
    $("#auto-sync").checked = false;
    return;
  }
  autoSync =
    $("#auto-sync").checked &&
    window.confirm(
      "Automatically upload validated changes from this linked CSV while this page is open? Updates replace this workspace’s invoice snapshot and clear action approvals. No money moves and no emails are sent. Turn this off at any time.",
    );
  render();
};
async function checkLinkedFile() {
  if (
    !autoSync ||
    !linkedFile ||
    busy ||
    watchingFile ||
    document.hidden ||
    document.querySelector("dialog[open]")
  )
    return;
  watchingFile = true;
  const handle = linkedFile,
    version = revision;
  try {
    const file = await handle.getFile();
    if (file.size > 650000)
      throw Error("Auto-sync paused: the CSV exceeds 650 KB.");
    const csv = await file.text();
    if (
      csv === linkedSnapshot ||
      !autoSync ||
      busy ||
      version !== revision ||
      handle !== linkedFile
    )
      return;
    await task(async () => {
      try {
        const result = await api("/api/import", {
          csv,
          confirm: true,
          auto_sync: true,
        });
        if (version !== revision || handle !== linkedFile) return;
        linkedSnapshot = csv;
        toast(
          `Auto-synced ${result.count} invoices. Previous approvals were cleared.`,
          "success",
        );
      } catch (error) {
        autoSync = false;
        throw Error("Auto-sync paused: " + error.message);
      }
    });
  } catch (error) {
    if (version === revision && handle === linkedFile) {
      autoSync = false;
      render();
      toast(
        "Auto-sync paused. Check file access and CSV format, then reconnect or enable it again.",
        "error",
      );
    }
  } finally {
    watchingFile = false;
  }
}
setInterval(checkLinkedFile, 10000);
$("#download-audit").onclick = () =>
  task(async () =>
    download("financeguard-activity.json", await api("/api/audit-log")),
  );
$("#audit-filter").onchange = render;
$("#overview-run").onclick = () => {
  location.hash = "security";
  $("#request").value = "Which overdue invoices should I follow up on first?";
  $("#request").focus();
};
$("#invoice-search").oninput = render;
$("#invoice-sort").onchange = render;
$all("[data-open-sources]").forEach(
  (button) => (button.onclick = () => $("#sources").showModal()),
);
function formatDate(value) {
  const date = new Date(value + "T00:00:00");
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      });
}
function openInvoice(invoice) {
  $("#detail-id").textContent = invoice.invoice_id;
  const content = $("#detail-content");
  content.replaceChildren();
  content.append(
    el("p", money(invoice.amount_inr), "detail-amount"),
    el("span", invoice.status, "status " + invoice.status),
  );
  const list = el("dl", "", "detail-grid");
  for (const [label, value] of [
    ["Customer", invoice.customer_name],
    ["Due date", formatDate(invoice.due_date)],
    ["Days overdue", invoice.days_overdue || "—"],
    [
      "Source",
      state.source === "sample" ? "Sample data" : "Imported invoice snapshot",
    ],
  ]) {
    const group = el("div", "");
    group.append(el("dt", label), el("dd", String(value)));
    list.append(group);
  }
  content.append(
    list,
    el(
      "p",
      "Reminder drafts require approval and cover all overdue invoices. No email is sent.",
      "muted",
    ),
  );
  $("#detail-reminder").hidden = invoice.status !== "overdue";
  $("#invoice-detail").showModal();
}
$("#detail-reminder").onclick = () => {
  $("#invoice-detail").close();
  location.hash = "security";
  $("#tool").value = "create_draft_payment_reminders";
  render();
  $("#request").value =
    "Prepare payment reminder drafts for all my overdue invoices.";
  $("#request").focus();
};
function csvCell(value) {
  let text = String(value);
  if (/^[\s]*[=+@-]/.test(text)) text = "'" + text;
  return '"' + text.replaceAll('"', '""') + '"';
}
$("#export-invoices").onclick = () => {
  if (!state) return;
  const fields = [
    "invoice_id",
    "customer_name",
    "amount_inr",
    "due_date",
    "status",
  ];
  const csv = [
    fields.join(","),
    ...state.invoices.map((row) =>
      fields.map((key) => csvCell(row[key])).join(","),
    ),
  ].join("\r\n");
  const url = URL.createObjectURL(
    new Blob([csv], { type: "text/csv;charset=utf-8" }),
  );
  const a = el("a", "");
  a.href = url;
  a.download = "financeguard-invoices.csv";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
$all("[data-close]").forEach(
  (b) => (b.onclick = () => document.getElementById(b.dataset.close).close()),
);
$("#account-open").onclick = $("#top-account").onclick = () =>
  $("#account").showModal();
async function initializeAuth() {
  try {
    const [appSDK, sdk] = await Promise.all([
      import("https://www.gstatic.com/firebasejs/13.0.0/firebase-app.js"),
      import("https://www.gstatic.com/firebasejs/13.0.0/firebase-auth.js"),
    ]);
    auth = sdk.getAuth(
      appSDK.initializeApp({
        apiKey: "AIzaSyDVla8NqXMDGe7AI7B5_DdOVT-BulMUoec",
        authDomain: "asmoneykit.firebaseapp.com",
        projectId: "asmoneykit",
        storageBucket: "asmoneykit.firebasestorage.app",
        messagingSenderId: "794157772021",
        appId: "1:794157772021:web:c8c68a94418c16f68b29bc",
      }),
    );
    const errors = {
      "auth/operation-not-allowed":
        "Enable Email/Password in Firebase Authentication → Sign-in method.",
      "auth/configuration-not-found":
        "Open Firebase Authentication, get started, and enable Email/Password.",
      "auth/invalid-credential": "Email or password is incorrect.",
      "auth/email-already-in-use":
        "Account already exists. Sign in or reset password.",
      "auth/weak-password":
        "Use a stronger password with at least six characters.",
      "auth/too-many-requests": "Too many attempts. Try again later.",
      "auth/network-request-failed": "Check your internet connection.",
      "auth/unauthorized-domain":
        "Add this hostname to Firebase Authentication authorized domains.",
    };
    async function authWork(work) {
      if (busy) return;
      busy = true;
      $("#auth-feedback").textContent = "Working…";
      $all("#account button").forEach((b) => (b.disabled = true));
      try {
        await work();
      } catch (e) {
        $("#auth-feedback").textContent =
          errors[e.code] || "Authentication failed: " + (e.code || e.message);
      } finally {
        busy = false;
        $all("#account button").forEach((b) => (b.disabled = false));
      }
    }
    const accountSignout = el("button", "Sign out");
    accountSignout.hidden = true;
    $("#account").append(accountSignout);
    accountSignout.onclick = () => authWork(() => sdk.signOut(auth));
    const verifyEmail = el("button", "Send verification email");
    verifyEmail.hidden = true;
    $("#account").append(verifyEmail);
    verifyEmail.onclick = () =>
      authWork(async () => {
        await sdk.sendEmailVerification(auth.currentUser);
        $("#auth-feedback").textContent =
          "Verification email sent. After verifying, sign out and sign back in.";
      });
    sdk.onAuthStateChanged(auth, async (next) => {
      const wasSignedIn = !!user;
      authReady = false;
      revision++;
      user = next;
      state = null;
      window.dispatchEvent(new Event("fg-account-changed"));
      pendingCSV = "";
      linkedFile = null;
      autoSync = false;
      linkedSnapshot = "";
      conversation = null;
      chatSnapshot = "";
      pendingHandle = null;
      pendingRevision = -1;
      accountSignout.hidden = !next;
      verifyEmail.hidden = !next || next.emailVerified;
      $("#account-form").hidden = !!next;
      $("#preview-rows").replaceChildren();
      if ($("#import-preview").open) $("#import-preview").close();
      if ($("#invoice-detail").open) $("#invoice-detail").close();
      $("#rows").replaceChildren();
      $("#events").replaceChildren();
      $("#messages").replaceChildren();
      bubble(
        "Your workspace is ready. Select a plan and approve the action you want to run.",
      );
      $("#password").value = "";
      $("#auth-feedback").textContent = next
        ? "Signed in as " + next.email
        : "Sign in or create an account.";
      if (next && $("#account").open) $("#account").close();
      try {
        if (!next && wasSignedIn) await api("/api/demo", {});
        await refresh();
      } catch (e) {
        $("#connection").textContent = e.message;
      } finally {
        authReady = true;
        render();
        if (next && !sessionStorage.getItem("fg-onboard-" + next.uid)) {
          sessionStorage.setItem("fg-onboard-" + next.uid, "1");
          $("#sources").showModal();
        }
        if (next) window.dispatchEvent(new Event("fg-auth-ready"));
      }
    });
    $("#account-form").onsubmit = (e) => {
      e.preventDefault();
      authWork(() =>
        sdk.signInWithEmailAndPassword(
          auth,
          $("#email").value.trim(),
          $("#password").value,
        ),
      );
    };
    $("#register").onclick = () => {
      if ($("#account-form").reportValidity())
        authWork(() =>
          sdk.createUserWithEmailAndPassword(
            auth,
            $("#email").value.trim(),
            $("#password").value,
          ),
        );
    };
    $("#reset").onclick = () => {
      if (!$("#email").reportValidity()) return;
      authWork(async () => {
        await sdk.sendPasswordResetEmail(auth, $("#email").value.trim());
        $("#auth-feedback").textContent =
          "Reset requested. Check your inbox if the account is eligible.";
      });
    };
    $("#logout").onclick = () => authWork(() => sdk.signOut(auth));
  } catch (e) {
    authReady = true;
    $("#auth-feedback").textContent =
      "Firebase could not load. Sample workflow remains available; check internet access.";
    $all("#account-form button").forEach((b) => (b.disabled = true));
  }
}
try {
  await api("/api/demo", {});
  await refresh();
} catch (error) {
  $("#connection").textContent = error.message;
  toast(error.message, "error");
}
installProviderUI({
  api,
  task,
  refresh,
  isSignedIn: () => !!user,
  clearFile: () => {
    linkedFile = null;
    autoSync = false;
    linkedSnapshot = "";
  },
  account: () => revision,
});
initializeAuth();
setInterval(() => {
  if (!busy) refresh().catch((e) => ($("#connection").textContent = e.message));
}, 15000);
