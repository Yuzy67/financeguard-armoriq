from dotenv import load_dotenv
from armoriq_sdk import ArmorIQClient

load_dotenv()

client = ArmorIQClient()
user_email = "yuvraj.test@example.com"

plan = {
    "goal": "Review overdue invoices without authorizing any money movement.",
    "steps": [
        {
            "action": "summarize_overdue_invoices",
            "mcp": "finance-mcp",
            "params": {},
        }
    ],
}

print("--- FinanceGuard: creating approved plan ---")
captured = client.capture_plan(
    llm="financeguard-demo",
    prompt="Review overdue invoices and provide a concise summary.",
    plan=plan,
)

token = client.get_intent_token(captured)

print("--- Safe request: summarize overdue invoices ---")
try:
    safe_result = client.invoke(
        "finance-mcp",
        "summarize_overdue_invoices",
        token,
        {},
        user_email=user_email,
    )
    print("ALLOWED:", safe_result)
except Exception as error:
    print("SAFE REQUEST FAILED:", type(error).__name__, str(error))

print("--- Risky request: simulate refunds ---")
try:
    risky_result = client.invoke(
        "finance-mcp",
        "simulate_refunds",
        token,
        {},
        user_email=user_email,
    )
    print("UNEXPECTED: refund was allowed:", risky_result)
except Exception as error:
    print("BLOCKED AS EXPECTED:", type(error).__name__, str(error))
