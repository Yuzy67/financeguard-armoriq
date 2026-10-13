# FinanceGuard MCP Tool Contract

MCP server name: finance-mcp

## Allowed tools
- list_invoices
- get_invoice_details
- summarize_overdue_invoices
- create_draft_payment_reminders
- export_sandbox_reports

## Blocked tools
- simulate_refunds
- transfer_funds
- delete_invoices

## Default behavior
- Hold any new or unrecognized tool action.

## Safety
- Use fake sandbox data only.
- No real customer records.
- No live payment or bank transfers.
