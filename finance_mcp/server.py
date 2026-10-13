import json
from pathlib import Path

from mcp.server import MCPServer

mcp = MCPServer("finance-mcp")

DATA_FILE = Path(__file__).parent.parent / "data" / "invoices.json"


def load_invoices():
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def find_invoice(invoice_id):
    for invoice in load_invoices():
        if invoice["invoice_id"] == invoice_id:
            return invoice
    return None


@mcp.tool()
def list_invoices():
    """List every invoice in the FinanceGuard sandbox."""
    return load_invoices()


@mcp.tool()
def get_invoice_details(invoice_id: str):
    """Get one sandbox invoice by its invoice ID."""
    invoice = find_invoice(invoice_id)
    if invoice is None:
        return {"error": "Invoice not found", "invoice_id": invoice_id}
    return invoice


@mcp.tool()
def summarize_overdue_invoices():
    """Summarize all overdue sandbox invoices and their total INR value."""
    overdue = []
    for invoice in load_invoices():
        if invoice.get("status") == "overdue":
            overdue.append(invoice)

    total = sum(invoice["amount_inr"] for invoice in overdue)

    return {
        "overdue_invoice_count": len(overdue),
        "total_overdue_amount_inr": total,
        "invoices": overdue,
    }


@mcp.tool()
def create_draft_payment_reminders():
    """Create reminder drafts for overdue invoices. No real emails are sent."""
    drafts = []

    for invoice in load_invoices():
        if invoice.get("status") == "overdue":
            drafts.append(
                {
                    "invoice_id": invoice["invoice_id"],
                    "customer_name": invoice["customer_name"],
                    "status": "draft_only",
                    "message": "No real email was sent.",
                }
            )

    return {
        "draft_count": len(drafts),
        "drafts": drafts,
    }


@mcp.tool()
def export_sandbox_reports():
    """Create a local sandbox report. No external data or systems are used."""
    report = summarize_overdue_invoices()

    return {
        "environment": "sandbox",
        "report_created": True,
        "report": report,
    }


@mcp.tool()
def simulate_refunds(invoice_id: str):
    """Simulate a refund. ArmorIQ must block this tool in the final demo."""
    invoice = find_invoice(invoice_id)

    if invoice is None:
        return {"error": "Invoice not found", "invoice_id": invoice_id}

    return {
        "simulation_only": True,
        "action": "refund_requested",
        "invoice_id": invoice_id,
        "amount_inr": invoice["amount_inr"],
        "message": "No real refund was processed.",
    }


@mcp.tool()
def transfer_funds(recipient: str, amount_inr: int):
    """Simulate a fund transfer. ArmorIQ must block this tool in the final demo."""
    return {
        "simulation_only": True,
        "action": "fund_transfer_requested",
        "recipient": recipient,
        "amount_inr": amount_inr,
        "message": "No real funds were transferred.",
    }


@mcp.tool()
def delete_invoices(invoice_id: str):
    """Simulate deleting an invoice. ArmorIQ must block this tool in the final demo."""
    invoice = find_invoice(invoice_id)

    if invoice is None:
        return {"error": "Invoice not found", "invoice_id": invoice_id}

    return {
        "simulation_only": True,
        "action": "invoice_deletion_requested",
        "invoice_id": invoice_id,
        "message": "No invoice was deleted.",
    }
