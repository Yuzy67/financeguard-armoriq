# FinanceGuard conversational assistant

## Setup

Set OPENROUTER_API_KEY in the ignored local .env file. The correct variable name
includes ROUTER, not ROUTE. Set OPENROUTER_MODEL to an available tool-capable
OpenRouter model. The current locally tested route is liquid/lfm-2.5-2.6b:free.
It is a small free model with availability/rate limits, not a guarantee of
financial accuracy. The paid gpt-4.1-mini route returned credits unavailable
with the current account; the first alternative free route was rate-limited.
No paid or different-provider fallback happens silently.

The free route also returned rate limits on later turns. Add credits and choose
a funded, tool-capable model if a dependable live demo is required; verify
availability before recording. A successful earlier response does not prove
that the route will be available throughout the demo.

For deployment, import the updated private runtime/vercel-production.env into
Vercel Production and redeploy. That ignored file includes the locally configured
OpenRouter key/model. Do not commit or share it. This does not resolve Vercel's
existing process-local session and temporary-storage limitations.

Start the app using the README commands. If changing the port, set
FINANCEGUARD_PORT to the same port so local MCP calls reach this app.
Sign in with Firebase and open Invoice assistant. Write a natural-language
request, approve the proposed task in the conversation, then inspect the actual
result. Suggested prompts below the composer are optional. Enter sends;
Shift+Enter inserts a new line. Permissions opens manual task controls and the
explicit local/ArmorIQ protection selector. New chat clears conversation memory.

## Execution boundary

- /api/agent calls the actual OpenRouter chat completions API. It does not use
  keyword matching. /api/command preserves explicitly labeled legacy commands.
- Server-owned conversation history is keyed by the verified user. Clients
  cannot submit system, assistant or tool history. History resets when the
  invoice snapshot changes. Invoice strings remain untrusted data.
- The model has no approval tool and cannot choose another user or credentials.
  Only the fixed supported tool names and empty arguments are accepted. Multiple
  tool requests in one response are rejected without execution.
- A safe unapproved tool produces a one-time, owner-bound approval card that
  expires in three minutes. The card captures protection mode and dataset.
  Approval grants one five-minute task plan. Dataset identity is checked inside
  the execution lock. Replaying a consumed card cannot execute it again.
- All model-requested tools use the existing perform() policy and scoped MCP
  path. ArmorIQ setup failure never falls back to local execution. The local
  mode is explicitly labeled and does not claim cloud verification.
- Only actual allowed tool results are supplied for the model explanation.
  Follow-up context includes the real result for the same snapshot. The UI
  separately shows backend counts/totals and downloadable actual tool output;
  model prose is not proof of correctness or execution.
- If the explanation provider fails after execution, the successful tool result
  remains visible and the UI warns not to rerun solely for an explanation.
- Signed-in AI requests are limited to 12 turns per minute per process. At most
  two model calls occur per turn, each capped at 900 output tokens. Context is
  bounded; oversized result rows are truncated and labeled. Usage reflects
  provider-reported tokens, not an independently verified bill.
- The source auto-sync timer makes no model calls. Chat history and invoices
  remain subject to local/temporary hosted storage limits documented in VERCEL.md.

## Verification

38 automated tests passed locally, covering forged arguments, unknown/parallel
tools, user isolation, stale/consumed approvals, provider outage, no fallback
from ArmorIQ failure, real tool facts in follow-up context, and invalid sync
preserving invoices and permissions, alongside the existing MCP tests.

Real browser testing used Firebase sign-in and OpenRouter: the model proposed
summarize_overdue_invoices; human approval executed the actual local MCP; the
model correctly explained one imported invoice totaling INR 275 and named the
matching synthetic invoice/customer. Later attempts hit the free route's rate
limit; mocked tests do not prove those live follow-up turns. A compatibility
issue with tool_choice=none was corrected by exposing no tools during the
explanation call. No generated prose is labeled ArmorIQ verified=True.

The auto-sync browser test used a controlled picker fixture and a real browser
storage file handle. A saved change imported INR 500 -> INR 625 automatically,
cleared the prior task permission, and reset chat context. Disabling Auto-sync
kept INR 625 after the source changed to INR 700 and another polling interval
elapsed. The native OS file picker was not automated. The 390-pixel mobile chat
and permissions dialog passed with no document-level horizontal overflow.

Official tool-calling reference:
https://openrouter.ai/docs/guides/features/tool-calling
