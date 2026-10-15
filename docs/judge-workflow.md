# FinanceGuard demonstration and connection model

The working credential check on 14 October 2026 captured a plan and issued
an ArmorIQ intent token. Safe invocation returned Internal Proxy Error.
External execution is unresolved; do not claim a successful end-to-end demo.

## Intended customer flow

1. Sign in to a workspace (not yet implemented in this repository).
2. Authorize a billing provider with read access, or import invoice data.
3. Store provider credentials only in the backend, scoped to that workspace.
4. The assistant proposes named tool actions and parameters.
5. The user approves the exact plan; the backend obtains an intent token.
6. Execute through the protected ArmorIQ path, with the original token.
7. Show the returned outcome and audit provenance; failures remain failures.
8. Revoke authorization or let approval expire when work is finished.

## Current hackathon implementation

This repository uses existing sandbox invoices, a single local operator,
two deterministic request intents, and real server-side ArmorIQ SDK calls.
It does not currently have user authentication, bank/card access, provider
OAuth, general LLM reasoning, or multi-user isolation. The prior AsmoneyKit
prototype is a separate codebase; its partial Firebase UI is not integrated.

## Explain security to judges

The plan allows summarize_overdue_invoices only. Requesting simulate_refunds
with the same token should trigger an actual IntentMismatchException. No
frontend flag grants permission. Tokens/API keys stay on the backend.
The MCP itself only simulates financial actions, so no real money moves.
The SDK's verified=True is its execution verification result; it is not an
independent review of invoice correctness or evidence that bank access exists.

## Resolve current blocker

Confirm the finance-mcp origin is running, its public URL has not changed,
and ArmorIQ registry health/discovery works. Match the registered identifier
and proxy configuration used by the working friend demo. Then rerun plan,
safe execution, and refund denial. If a healthy origin still returns Internal
Proxy Error, provide the sanitized timestamp/error to the ArmorIQ organizers.
