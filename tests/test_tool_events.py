from types import SimpleNamespace

from app.agents import defender


def test_defender_records_tool_event_without_calling_openai(monkeypatch):
    tool_call = SimpleNamespace(
        id="call-1",
        function=SimpleNamespace(
            name="search_products",
            arguments='{"search_term": "headphones"}',
        ),
    )
    tool_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=None, tool_calls=[tool_call])
            )
        ]
    )
    final_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="Here are the available headphones.",
                    tool_calls=[],
                )
            )
        ]
    )
    responses = iter([tool_response, final_response])
    events = []

    monkeypatch.setattr(defender, "semantic_input_shield", lambda _: False)
    monkeypatch.setattr(
        defender.client.chat.completions,
        "create",
        lambda **_: next(responses),
    )

    reply = defender.query_defender(
        "Show me headphones.",
        customer_id="customer-demo-001",
        tool_events=events,
    )

    assert reply == "Here are the available headphones."
    assert events[0]["tool_name"] == "search_products"
    assert events[0]["success"] is True
    assert events[0]["customer_id"] == "customer-demo-001"
