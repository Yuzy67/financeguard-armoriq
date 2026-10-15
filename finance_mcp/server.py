"""Tenant-scoped finance tools; all invoice access requires a signed MCP scope."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mcp.server.fastmcp import FastMCP, Context
import workspace as store
from mcp_access import authorized_rows
mcp=FastMCP('finance-mcp',host='127.0.0.1',port=8002,stateless_http=True,json_response=True)

@mcp.tool()
def list_invoices(ctx:Context)->dict:
    """List invoices in the authorized workspace."""
    return store.local_tool('list_invoices',authorized_rows(ctx,'list_invoices'))

@mcp.tool()
def get_invoice_details(invoice_id:str,ctx:Context)->dict:
    """Read an authorized workspace invoice by ID."""
    rows=authorized_rows(ctx,'get_invoice_details')
    return next((r for r in rows if r['invoice_id']==invoice_id),{'error':'Invoice not found'})

@mcp.tool()
def summarize_overdue_invoices(ctx:Context)->dict:
    """Calculate overdue count and INR total for the authorized workspace."""
    return store.summary(authorized_rows(ctx,'summarize_overdue_invoices'))

@mcp.tool()
def create_draft_payment_reminders(ctx:Context)->dict:
    """Return reminder drafts; never send email."""
    return store.local_tool('create_draft_payment_reminders',authorized_rows(ctx,'create_draft_payment_reminders'))

@mcp.tool()
def export_sandbox_reports(ctx:Context)->dict:
    """Return an authorized workspace report."""
    return store.local_tool('export_sandbox_reports',authorized_rows(ctx,'export_sandbox_reports'))

@mcp.tool()
def simulate_refunds(invoice_id:str,ctx:Context)->dict:
    """Sensitive sandbox request. Not included in safe plans; no real refund."""
    authorized_rows(ctx,'simulate_refunds')
    raise PermissionError('Refund execution is disabled at the origin.')

@mcp.tool()
def transfer_funds(recipient:str,amount_inr:int,ctx:Context)->dict:
    """Sensitive sandbox request. No real transfers are available."""
    authorized_rows(ctx,'transfer_funds')
    raise PermissionError('Transfer execution is disabled at the origin.')

@mcp.tool()
def delete_invoices(invoice_id:str,ctx:Context)->dict:
    """Sensitive sandbox request. No invoice deletion is available."""
    authorized_rows(ctx,'delete_invoices')
    raise PermissionError('Deletion is disabled at the origin.')

if __name__=='__main__':mcp.run(transport='streamable-http')
