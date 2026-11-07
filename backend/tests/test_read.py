from fastapi.routing import APIRoute

from backend import db, seed
from backend.main import app


def test_seed_loads_the_records(capsys):
    seed.main()
    assert capsys.readouterr().out.startswith(
        "Loaded 25 claims, 50 policies, 49 customers, 3 plans, 3 handlers into "
    )


def test_seed_never_reads_the_answer_key(monkeypatch):
    read = []
    original = db.load
    monkeypatch.setattr(db, "load", lambda name: read.append(name) or original(name))
    db.seed()
    assert read
    assert not [name for name in read if "evals" in name or "security" in name]


def test_list_claims(client):
    claims = client.get("/api/claims").json()
    assert len(claims) == 25
    assert {c["status"] for c in claims} == {"waiting"}
    assert claims[0] == {
        "claim_id": "CLM-1001",
        "customer_name": "Maya Patel",
        "claim_type": "trip_delay",
        "summary": "Flight home canceled by the airline, rebooked the next morning",
        "amount_claimed": 420.0,
        "submitted_on": "2026-06-24",
        "status": "waiting",
        "decision": None,
        "payout": None,
    }


def test_get_claim(client):
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["story"].startswith("My flight home from Rome")
    assert len(claim["items"]) == 3
    assert len(claim["documents"]) == 4
    assert claim["amount_claimed"] == 420.0
    assert claim["payout_approval_limit"] == 1000.0
    assert claim["decision"] is None


def test_unknown_records(client):
    assert client.get("/api/claims/CLM-9999").status_code == 404
    assert client.get("/api/policies/POL-9999").status_code == 404
    assert client.get("/api/customers/CUS-9999").status_code == 404


def test_get_policy(client):
    policy = client.get("/api/policies/POL-2001").json()
    assert policy["plan"]["plan"] == "premium"
    assert policy["plan"]["trip_delay_max"] == 800.0
    assert policy["plan"]["deductible"] == 50.0
    assert policy["trip"]["returns_on"] == "2026-06-18"


def test_get_policy_with_add_ons(client):
    policies = db.load("policies.json")
    with_add_on = next(p for p in policies if "electronics_plus" in p["add_ons"])
    policy = client.get(f"/api/policies/{with_add_on['policy_id']}").json()
    electronics = next(
        a for a in policy["add_ons"] if a["add_on"] == "electronics_plus"
    )
    assert electronics["electronics_per_item_limit"] == 1200.0


def test_get_customer(client):
    customer = client.get("/api/customers/CUS-3001").json()
    assert customer["name"] == "Maya Patel"
    assert customer["address"]["city"] == "Jersey City"


def test_claim_history_leaves_out_personal_details(client):
    history = client.get("/api/customers/CUS-3001/claim-history").json()
    assert [c["claim_id"] for c in history] == ["CLM-0412"]
    text = str(history)
    for detail in ("maya.patel@example.com", "555 0143", "Wayne Street", "1988"):
        assert detail not in text


def test_policy_wording(client):
    wording = client.get("/api/policy-wording").json()["text"]
    assert wording == (db.DATA / "policy_wording.md").read_text(encoding="utf-8")


def test_list_handlers(client):
    handlers = client.get("/api/handlers").json()
    assert [h["name"] for h in handlers] == [
        "Dana Whitfield",
        "Marcus Oyelaran",
        "Priya Raman",
    ]


def test_every_operation_is_documented():
    routes = [r for r in app.routes if isinstance(r, APIRoute)]
    assert routes
    for route in routes:
        assert route.operation_id, route.path
        doc = route.endpoint.__doc__ or ""
        assert doc.strip(), route.path
        assert "\n" not in doc.strip(), route.path
