# FinanceGuard

FinanceGuard is a policy-enforced safety layer for financial AI agents.

## Problem

AI agents can analyze invoices, but unrestricted tool access can trigger refunds, transfers, or destructive accounting actions.

## Solution

FinanceGuard combines:

- A live MCP finance server
- ArmorIQ MCP registration and health scanning
- An active FinanceGuard policy
- Cryptographically verified action plans
- End-user-attributed tool authorization

## Security demonstration

Allowed action:

`summarize_overdue_invoices`

Blocked action:

`simulate_refunds`

The safe action is included in the approved plan and permitted by policy. The refund action is rejected because it is outside the original verified plan.

## Architecture

```text
User request
  → FinanceGuard backend
  → ArmorIQ capture_plan()
  → ArmorIQ intent token
  → ArmorIQ invoke()
  → finance-mcp tool

```
## Key message

> The agent can read the invoice. It cannot move the money.
