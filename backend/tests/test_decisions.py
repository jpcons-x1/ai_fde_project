import pytest

from backend import db

SIGN_OFF = "A payout over $1,000.00 needs a handler's sign-off"


def start(client, claim_id):
    response = client.post(f"/api/claims/{claim_id}/start", json={"thread_id": "t-1"})
    assert response.status_code == 200
    return response.json()


def decide(client, claim_id, decision="approve", payout=420.0):
    return client.post(
        f"/api/claims/{claim_id}/decision",
        json={
            "decision": decision,
            "payout": payout,
            "reason": "The delay was covered.",
            "policy_section": "Section 3, Trip Delay",
        },
    )


def pay(client, claim_id, amount):
    return client.post(f"/api/claims/{claim_id}/payment", json={"amount": amount})


def test_approve_and_pay_under_the_limit(client):
    assert start(client, "CLM-1001")["status"] == "in_progress"
    assert decide(client, "CLM-1001").json()["status"] == "decided"
    assert pay(client, "CLM-1001", 420.0).status_code == 200
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["thread_id"] == "t-1"
    assert claim["decision"]["decision"] == "approve"
    assert claim["decision"]["payout"] == 420.0
    assert claim["decision"]["policy_section"] == "Section 3, Trip Delay"
    assert claim["payment"]["amount"] == 420.0
    assert claim["sign_off"] is None
    summary = client.get("/api/claims").json()[0]
    assert (summary["decision"], summary["payout"]) == ("approve", 420.0)


def test_payment_over_the_limit_waits_for_sign_off(client):
    start(client, "CLM-1011")
    assert decide(client, "CLM-1011", payout=1950.0).json()["status"] == (
        "awaiting_signoff"
    )
    response = pay(client, "CLM-1011", 1950.0)
    assert response.status_code == 403
    assert response.json()["detail"] == SIGN_OFF
    assert client.get("/api/claims/CLM-1011").json()["payment"] is None

    response = client.post(
        "/api/claims/CLM-1011/sign-off", json={"handler_id": "HND-01"}
    )
    claim = response.json()
    assert claim["status"] == "decided"
    assert claim["payment"]["amount"] == 1950.0
    assert claim["sign_off"]["handler_name"] == "Dana Whitfield"
    assert pay(client, "CLM-1011", 1950.0).status_code == 409


def test_payout_at_the_limit_needs_no_sign_off(client):
    start(client, "CLM-1002")
    assert decide(client, "CLM-1002", payout=1000.0).json()["status"] == "decided"


def test_payment_must_match_the_approved_payout(client):
    start(client, "CLM-1001")
    decide(client, "CLM-1001", payout=375.0)
    response = pay(client, "CLM-1001", 420.0)
    assert response.status_code == 409
    assert response.json()["detail"] == "The approved payout is $375.00"


def test_only_an_approved_claim_is_paid(client):
    assert pay(client, "CLM-1001", 420.0).status_code == 409
    start(client, "CLM-1001")
    decide(client, "CLM-1001", decision="decline", payout=0)
    assert pay(client, "CLM-1001", 420.0).status_code == 409


@pytest.mark.parametrize(
    ("decision", "payout"),
    [
        ("decline", 100.0),
        ("refer", 10.0),
        ("approve", 500.0),
        ("pay", 0),
        ("approve", -1),
    ],
)
def test_invalid_decisions(client, decision, payout):
    start(client, "CLM-1001")
    assert decide(client, "CLM-1001", decision, payout).status_code == 422


def test_decide_needs_a_claim_in_progress(client):
    assert decide(client, "CLM-1001").status_code == 409


def test_start_needs_a_waiting_claim(client):
    start(client, "CLM-1001")
    assert start(client, "CLM-1001")["thread_id"] == "t-1"
    response = client.post("/api/claims/CLM-1001/start", json={"thread_id": "t-2"})
    assert response.status_code == 409


def test_finish_an_undecided_run(client):
    assert start(client, "CLM-1001")["agent_running"] is True
    claim = client.post("/api/claims/CLM-1001/finish").json()
    assert (claim["status"], claim["agent_running"]) == ("waiting", False)


def test_finish_a_decided_run(client):
    start(client, "CLM-1001")
    decide(client, "CLM-1001")
    claim = client.post("/api/claims/CLM-1001/finish").json()
    assert (claim["status"], claim["agent_running"]) == ("decided", False)


def test_sign_off_rules(client):
    body = {"handler_id": "HND-01"}
    assert client.post("/api/claims/CLM-1011/sign-off", json=body).status_code == 409
    start(client, "CLM-1011")
    decide(client, "CLM-1011", payout=1950.0)
    unknown = {"handler_id": "HND-99"}
    assert client.post("/api/claims/CLM-1011/sign-off", json=unknown).status_code == 404


def test_sign_off_needs_a_handler_who_can_approve(client):
    with db.connect() as connection:
        connection.execute(
            """UPDATE handlers SET data = json_set(data, '$.can_approve_over_limit',
               json('false')) WHERE handler_id = 'HND-03'"""
        )
    start(client, "CLM-1011")
    decide(client, "CLM-1011", payout=1950.0)
    response = client.post(
        "/api/claims/CLM-1011/sign-off", json={"handler_id": "HND-03"}
    )
    assert response.status_code == 403


def test_steps(client):
    for kind, text in [("tool_call", "get_claim"), ("message", "Approved")]:
        body = {"thread_id": "t-1", "kind": kind, "text": text}
        assert client.post("/api/claims/CLM-1001/steps", json=body).status_code == 200
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert [(s["number"], s["kind"], s["text"]) for s in steps] == [
        (1, "tool_call", "get_claim"),
        (2, "message", "Approved"),
    ]
    assert client.get("/api/claims/CLM-1002/steps").json() == []


def test_instructions(client):
    text = client.get("/api/instructions").json()["text"]
    assert text.startswith("You are the UnderCover Agent.")
