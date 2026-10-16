# Flow State recording runbook (4 minutes 30 seconds)

Do not record a final submission until the live ArmorIQ path and console proof
pass. The earlier 54-second animated explainer is an optional intro/extra; it is
not the required 3-5 minute product/console demonstration.

## Before pressing record

- Start the app and MCP, verify the current public HTTPS origin and org.
- Run tools/check_setup.py and run_financeguard_demo.py successfully.
- Open the application, correct ArmorIQ organization, Policy Studio, and
  Observability session. Hide API-key settings, terminal environment files,
  password fields, tokens, notifications, and unrelated personal tabs.
- Use only the repository's synthetic invoices. Keep an untouched backup CSV.
- Confirm sample data in the app matches the actual registered MCP's dataset.
- Use one monitor, 1080p or higher, readable browser zoom, and quiet audio.

| Time | Screen and narration |
| --- | --- |
| 0:00-0:30 | Overview. "Finance teams want agents to review invoices, but a request to read invoices must never become permission to move money. FinanceGuard helps small businesses and accountants delegate that work with an explicit boundary." |
| 0:30-1:00 | Invoices, then Security. "We connect a CSV or use sample invoices. This is a command-based tool workflow. The user approves one action for five minutes. Our backend keeps the ArmorIQ key private and captures the plan." Show summarize_overdue_invoices in the actual plan. |
| 1:00-1:35 | Select ArmorIQ mode, approve, then run. "The backend asks ArmorIQ to check the plan and invokes our MCP. The result is three overdue invoices totaling 88,000 rupees." Show the actual result and SDK verified=True only if this run returns it. |
| 1:35-2:00 | Attempt refund under the same plan. "Refunding was never in the approved scope. ArmorIQ SDK intent binding rejects the action before it reaches the proxy. Nothing moved." Show the blocked result, then Audit Log and its source label. |
| 2:00-2:30 | Actual ArmorIQ registered MCP and Policy Studio. Show exact server URL/health and actual rules. Explain that platform configuration and our locally hosted tool code are separate. Never invent or redraw a missing rule. |
| 2:30-3:15 | Actual Observability. Find the printed session UUID. Inspect plan, allow/deny spans and tool report. "These are SDK session traces. This denial is SDK-sourced, not a proxy enforcement decision." If the console is empty or delivery fails, show and explain that limitation instead of claiming success. |
| 3:15-4:00 | Return to Security, prepare a reminder draft with its own approval and show the report/export. "Every extra capability needs its own scope. Drafts do not send emails. Workspace credentials bind identity, tool, dataset, and expiry." |
| 4:00-4:30 | Overview. "Our prototype proves useful invoice work can stay inside a declared scope. Next: durable shared hosting, provider onboarding, and a real model integration. FinanceGuard: approved actions execute. Unauthorized actions get blocked." Credit Anuj A Shetty and Yuvraj Singh. |

## Evidence and fallback

Keep the terminal evidence JSON, console screenshot, and app activity export for
this same run. Do not splice older Anuj-workspace results into a new
Yuvaraj-workspace run as though they are the same session.

If Vercel or the tunnel fails, demonstrate the fully local workspace and label
its decisions LOCAL_POLICY. That backup does not satisfy real ArmorIQ proof.
Fix provider configuration before using it as the final hackathon video.

## Publish

Export a continuous 3-5 minute walkthrough. Upload it as an unlisted YouTube,
Loom, or Vimeo video in the founders' chosen account. Check playback and link
access in an unsigned-in browser before inserting the real URL in the form.
No video has been uploaded by this runbook; a recording/publication URL remains
pending until the real live path and founders' publishing account are ready.
