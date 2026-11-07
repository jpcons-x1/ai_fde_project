"""The UnderCover Agent."""

import json
import os
from collections.abc import Iterator
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"
NO_DECISION = "The run ended without a decision, so the claim is back in the queue."


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    url = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
    return httpx.Client(base_url=url, timeout=30)


def request(
    method: str, path: str, body: dict[str, Any] | None = None
) -> httpx.Response:
    """Call one operation of the backend's API."""
    with backend() as client:
        return client.request(method, path, json=body)


def answer(method: str, path: str, body: dict[str, Any] | None = None) -> str:
    """Call the API and return its answer as text for the model, refusals included."""
    response = request(method, path, body)
    if response.is_success:
        return response.text
    return f"Refused ({response.status_code}): {response.text}"


@tool
def get_claim(claim_id: str) -> str:
    """Get a claim: the customer's story, the items claimed and the documents."""
    return answer("GET", f"/api/claims/{claim_id}")


@tool
def get_policy(policy_id: str) -> str:
    """Get a policy with its plan's limits, its add-ons and the covered trip."""
    return answer("GET", f"/api/policies/{policy_id}")


@tool
def get_claim_history(customer_id: str) -> str:
    """Get a customer's earlier claims."""
    return answer("GET", f"/api/customers/{customer_id}/claim-history")


@tool
def get_policy_wording() -> str:
    """Get the policy wording that every decision follows."""
    return answer("GET", "/api/policy-wording")


@tool
def decide_claim(
    claim_id: str,
    decision: Literal["approve", "decline", "refer"],
    payout: float,
    reason: str,
    policy_section: str,
) -> str:
    """Record the decision on a claim: the payout (0 unless approved), a reason of
    two or three sentences and the relevant section of the policy wording."""
    body = {
        "decision": decision,
        "payout": payout,
        "reason": reason,
        "policy_section": policy_section,
    }
    return answer("POST", f"/api/claims/{claim_id}/decision", body)


@tool
def pay_claim(claim_id: str, amount: float) -> str:
    """Pay the approved payout on a claim."""
    return answer("POST", f"/api/claims/{claim_id}/payment", {"amount": amount})


TOOLS = [
    get_claim,
    get_policy,
    get_claim_history,
    get_policy_wording,
    decide_claim,
    pay_claim,
]


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or GPT-6 Luna by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
    )


def steps(message: BaseMessage) -> Iterator[tuple[str, str]]:
    """Describe a message as the steps the dashboard shows."""
    if isinstance(message, ToolMessage):
        yield "tool_result", f"{message.name}: {message.text}"
    elif isinstance(message, AIMessage):
        if message.text:
            yield "message", message.text
        for call in message.tool_calls:
            yield "tool_call", f"{call['name']}({json.dumps(call['args'])})"


def record(claim_id: str, thread_id: str, kind: str, text: str) -> None:
    """Record one step of the run in the backend."""
    body = {"thread_id": thread_id, "kind": kind, "text": text}
    request("POST", f"/api/claims/{claim_id}/steps", body).raise_for_status()


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run the agent on one claim and return its final reply."""
    start = {"thread_id": thread_id}
    request("POST", f"/api/claims/{claim_id}/start", start).raise_for_status()
    reply = ""
    try:
        instructions = request("GET", "/api/instructions").json()["text"]
        agent = create_agent(llm or model(), tools=TOOLS, system_prompt=instructions)
        updates = agent.stream(
            {"messages": [{"role": "user", "content": f"Decide claim {claim_id}."}]},
            config={"configurable": {"thread_id": thread_id}},
            stream_mode="updates",
        )
        for update in updates:
            for state in update.values():
                for message in state["messages"]:
                    for kind, text in steps(message):
                        record(claim_id, thread_id, kind, text)
                    if isinstance(message, AIMessage) and message.text:
                        reply = message.text
    finally:
        if request("GET", f"/api/claims/{claim_id}").json()["status"] == "in_progress":
            record(claim_id, thread_id, "message", NO_DECISION)
        request("POST", f"/api/claims/{claim_id}/finish").raise_for_status()
    return reply
