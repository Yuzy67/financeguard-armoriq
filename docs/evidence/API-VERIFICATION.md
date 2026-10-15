# ArmorIQ API verification: what is proven

## Key and workspace

On 15 October 2026 a fresh API-key-authenticated SDK bootstrap returned:

- Organization: anuj shetty's Workspace
- Organization ID: 50bcbee3-3d3f-48cb-8331-61e2b89e607d
- Agent: financeguard-demo
- Agent ID: 74e4e1bf-c327-4605-8411-ea02843cda7b
- MCP registration: finance-mcp

See api-key-audit.json. The key was loaded from the ignored backend .env,
sent by the SDK to ArmorIQ, and never placed in frontend source or deliverables.

The supplied screenshot is Yuvraj Singh's Workspace. It is a different
organization from the one authenticated by this key. Its visible chart activity
is dated October 12–13, while these tests ran on October 15. That screenshot
does not establish whether our later calls produced decision rows.

## Actual execution evidence

armoriq-live-results.json preserves a successful invocation result from the
SDK with three overdue imported invoices and INR 88,000. The actual public
MCP origin required a short-lived workspace/action/data-scoped credential.
The browser also performed this path and exported source-labeled activity.

Important qualification: SDK 0.6.10 constructs its successful invocation
result with verified=True. This is a meaningful SDK status, but the field
alone is not an independently signed audit receipt, a proof of every possible
policy check, or proof of a dashboard decision record. The app displays it
as an SDK result. The local app's event UUIDs are local IDs, not provider IDs.

## Where the refund was blocked

simulate_refunds was not in the summary plan. ArmorIQ SDK invoke() raised
IntentMismatchException before making the unauthorized proxy invocation.
The app records ARMORIQ_SDK, not a proxy decision. We did not send an actual
refund tool invocation and did not observe a cloud audit row for that denial.

## What ArmorIQ hosts

ArmorIQ stores registration/configuration and supplies the intent and proxy
services. The finance-mcp Python process and invoice database run on our
machine. Registering their URL does not move their code/data into ArmorIQ.
The registered agent is an identity/configuration; the FinanceGuard workflow
code runs on our backend. A general AI language model is not connected.

## How to inspect the right dashboard

Select anuj shetty's Workspace in the ArmorIQ account authorized for that
organization. Review October 15 activity and the financeguard-demo agent.
Use the Plans/Observability/Audit views documented for that product version.
An aggregate Decisions chart is not a substitute for per-run inspection.
The SDK's session/observability APIs can explicitly record plan/check/report
spans; our raw invoke path did not independently verify those admin views.

To run in Yuvaraj's organization instead, use a key scoped to it and register
the current reachable origin there. Do not rotate an otherwise valid key
merely because another workspace has a different chart.

Sources: https://docs.armoriq.ai/sdk/sessions and
https://docs.armoriq.ai/platform/observability/python-sdk .
