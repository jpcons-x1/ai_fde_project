import ast
import itertools
from pathlib import Path

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import __main__ as cli
from agent import main

AGENT = Path(main.__file__).parent


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


ids = itertools.count()


def call(name, **args):
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": str(next(ids))}]
    )


def stub(*replies):
    return StubModel(messages=iter(replies))


def decide(claim_id, payout):
    return call(
        "decide_claim",
        claim_id=claim_id,
        decision="approve",
        payout=payout,
        reason="The loss is covered. The payout follows section 10.",
        policy_section="Section 3, Trip Delay",
    )


def test_run_decides_and_pays(backend):
    replies = [
        call("get_claim", claim_id="CLM-1001"),
        call("get_policy", policy_id="POL-2001"),
        call("get_claim_history", customer_id="CUS-3001"),
        call("get_policy_wording"),
        decide("CLM-1001", 375.0),
        call("pay_claim", claim_id="CLM-1001", amount=375.0),
        AIMessage(content="Approved, paying $375.00."),
    ]
    assert main.run("CLM-1001", "t-1", stub(*replies)) == "Approved, paying $375.00."

    claim = backend.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["agent_running"] is False
    assert claim["payment"]["amount"] == 375.0
    steps = backend.get("/api/claims/CLM-1001/steps").json()
    calls = [s["text"].split("(")[0] for s in steps if s["kind"] == "tool_call"]
    assert calls == [
        "get_claim",
        "get_policy",
        "get_claim_history",
        "get_policy_wording",
        "decide_claim",
        "pay_claim",
    ]
    assert steps[0]["text"] == 'get_claim({"claim_id": "CLM-1001"})'
    assert steps[1]["text"].startswith('get_claim: {"claim_id":"CLM-1001"')
    assert {s["thread_id"] for s in steps} == {"t-1"}
    assert (steps[-1]["kind"], steps[-1]["text"]) == (
        "message",
        "Approved, paying $375.00.",
    )


def test_payment_over_the_limit_is_blocked(backend):
    replies = [
        decide("CLM-1011", 1950.0),
        call("pay_claim", claim_id="CLM-1011", amount=1950.0),
        AIMessage(content="Approved, waiting for sign-off."),
    ]
    main.run("CLM-1011", "t-1", stub(*replies))

    claim = backend.get("/api/claims/CLM-1011").json()
    assert claim["status"] == "awaiting_signoff"
    assert claim["payment"] is None
    steps = backend.get("/api/claims/CLM-1011/steps").json()
    refusal = next(s for s in steps if s["text"].startswith("pay_claim: "))
    assert refusal["text"] == (
        'pay_claim: Refused (403): {"detail":"A payout over $1,000.00 needs a '
        "handler's sign-off\"}"
    )


def test_a_run_without_a_decision_puts_the_claim_back(backend):
    replies = [call("get_claim", claim_id="CLM-1001"), AIMessage(content="Not sure.")]
    main.run("CLM-1001", "t-1", stub(*replies))

    assert backend.get("/api/claims/CLM-1001").json()["status"] == "waiting"
    steps = backend.get("/api/claims/CLM-1001/steps").json()
    assert steps[-1]["text"] == main.NO_DECISION


def test_unknown_records_reach_the_model_as_refusals():
    assert main.get_policy.invoke({"policy_id": "POL-9999"}).startswith("Refused (404)")


def test_instructions_come_from_the_backend(backend, monkeypatch):
    prompts = []
    create_agent = main.create_agent

    def spy(llm, tools, system_prompt):
        prompts.append(system_prompt)
        return create_agent(llm, tools=tools, system_prompt=system_prompt)

    monkeypatch.setattr(main, "create_agent", spy)
    main.run("CLM-1001", "t-1", stub(AIMessage(content="Done.")))
    assert prompts == [backend.get("/api/instructions").json()["text"]]


def test_run_agent_from_the_backend(backend, monkeypatch):
    replies = [decide("CLM-1001", 375.0), AIMessage(content="Approved.")]
    monkeypatch.setattr(main, "model", lambda: stub(*replies))
    response = backend.post("/api/claims/CLM-1001/run")
    assert response.json()["thread_id"]
    claim = backend.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["thread_id"] == response.json()["thread_id"]
    assert backend.post("/api/claims/CLM-1001/run").status_code == 409


def test_cli_works_the_waiting_claims(monkeypatch, capsys):
    worked = []
    monkeypatch.setattr(
        cli, "run", lambda claim_id, _: worked.append(claim_id) or "Done."
    )
    cli.main(["CLM-1002"])
    assert worked == ["CLM-1002"]
    cli.main([])
    assert len(worked) == 26
    assert capsys.readouterr().out.startswith("CLM-1002: Done.\nCLM-1001: Done.\n")


def test_agent_never_reaches_past_the_api():
    for path in AGENT.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        modules = [
            node.module if isinstance(node, ast.ImportFrom) else alias.name
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Import | ast.ImportFrom)
            for alias in node.names
        ]
        assert not [m for m in modules if m and m.split(".")[0] == "backend"], path
        assert "data/" not in source, path
        assert "evals" not in source, path


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"
