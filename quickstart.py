from armoriq_sdk import ArmorIQClient

# The only required argument is api_key. After `armoriq login`,
# the client reads it automatically from ~/.armoriq/credentials.json.
client = ArmorIQClient()

# Describe what the agent wants to do - one step per tool call.
plan_definition = {
    "goal": "Get weather for San Francisco",
    "steps": [
        {
            "action": "get_weather",
            "mcp": "weather-mcp",
            "params": {"city": "San Francisco", "units": "fahrenheit"},
        },
    ],
}

# Capture the plan (signs it against the LLM's reasoning).
plan = client.capture_plan(
    llm="gpt-4o",
    prompt="What's the weather in San Francisco?",
    plan=plan_definition,
)

# Get a short-lived intent token (5 minutes by default).
token = client.get_intent_token(plan, validity_seconds=300)

# Invoke the tool. `user_email` attaches the end-user identity
# used for audit trails and per-user policy enforcement.
result = client.invoke(
    mcp="weather-mcp",
    action="get_weather",
    intent_token=token,
    params={"city": "San Francisco", "units": "fahrenheit"},
    user_email="alice@customer.com",
)

print(result.data)
client.close()
