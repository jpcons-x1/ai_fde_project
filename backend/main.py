"""The UnderCover backend."""

import json
import sqlite3
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException

from backend import db as database
from backend.models import (
    AddOn,
    Claim,
    ClaimSummary,
    Customer,
    Decision,
    Handler,
    Payment,
    Plan,
    Policy,
    PreviousClaim,
    SignOff,
    Text,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    database.ensure()
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)


def get_db() -> Iterator[sqlite3.Connection]:
    connection = database.connect()
    try:
        yield connection
    finally:
        connection.close()


Db = Annotated[sqlite3.Connection, Depends(get_db)]


def fetch(db: sqlite3.Connection, table: str, key: str, value: str) -> Any:
    """Return one record's JSON document, or raise 404."""
    row = db.execute(f"SELECT data FROM {table} WHERE {key} = ?", (value,)).fetchone()  # noqa: S608
    if row is None:
        raise HTTPException(404, f"No record {value}")
    return json.loads(row["data"])


def approval_limit(db: sqlite3.Connection) -> float:
    """Return the payout above which a handler must sign off."""
    row = db.execute("SELECT data FROM company").fetchone()
    return json.loads(row["data"])["payout_approval_limit"]


def load_claim(db: sqlite3.Connection, claim_id: str) -> Claim:
    """Return a claim with its decision, payment and sign-off, or raise 404."""
    row = db.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"No claim {claim_id}")
    decision = payment = sign_off = None
    if row["decision"]:
        decision = Decision(
            decision=row["decision"],
            payout=row["payout"],
            reason=row["reason"],
            policy_section=row["policy_section"],
            decided_at=row["decided_at"],
        )
    if row["paid_at"]:
        payment = Payment(amount=row["paid_amount"], paid_at=row["paid_at"])
    if row["signed_off_by"]:
        handler = fetch(db, "handlers", "handler_id", row["signed_off_by"])
        sign_off = SignOff(
            handler_id=handler["handler_id"],
            handler_name=handler["name"],
            signed_at=row["signed_off_at"],
        )
    return Claim(
        **json.loads(row["data"])
        | {
            "status": row["status"],
            "thread_id": row["thread_id"],
            "payout_approval_limit": approval_limit(db),
            "decision": decision,
            "payment": payment,
            "sign_off": sign_off,
        }
    )


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims(db: Db) -> list[ClaimSummary]:
    """List the claims queue with where each claim stands."""
    rows = db.execute(
        """SELECT claims.data, claims.status, claims.decision, claims.payout,
                  json_extract(customers.data, '$.name') AS customer_name
           FROM claims
           JOIN customers
             ON customers.customer_id = json_extract(claims.data, '$.customer_id')
           ORDER BY claims.claim_id"""
    ).fetchall()
    return [
        ClaimSummary(
            **json.loads(row["data"])
            | {
                "status": row["status"],
                "customer_name": row["customer_name"],
                "decision": row["decision"],
                "payout": row["payout"],
            }
        )
        for row in rows
    ]


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str, db: Db) -> Claim:
    """Get one claim in full, with its decision and payment."""
    return load_claim(db, claim_id)


@app.get("/api/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str, db: Db) -> Policy:
    """Get a policy with its plan's limits and its add-ons."""
    policy = fetch(db, "policies", "policy_id", policy_id)
    plan = Plan(**fetch(db, "plans", "plan", policy["plan"]))
    add_ons = [AddOn(**fetch(db, "add_ons", "add_on", a)) for a in policy["add_ons"]]
    return Policy(**policy | {"plan": plan, "add_ons": add_ons})


@app.get("/api/customers/{customer_id}", operation_id="get_customer")
def get_customer(customer_id: str, db: Db) -> Customer:
    """Get a customer's details and claim history."""
    return Customer(**fetch(db, "customers", "customer_id", customer_id))


@app.get("/api/customers/{customer_id}/claim-history", operation_id="get_claim_history")
def get_claim_history(customer_id: str, db: Db) -> list[PreviousClaim]:
    """Get a customer's earlier claims, without their personal details."""
    customer = fetch(db, "customers", "customer_id", customer_id)
    return [PreviousClaim(**c) for c in customer["previous_claims"]]


@app.get("/api/policy-wording", operation_id="get_policy_wording")
def get_policy_wording() -> Text:
    """Get the policy wording that decisions follow."""
    return Text(text=(database.DATA / "policy_wording.md").read_text(encoding="utf-8"))


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers(db: Db) -> list[Handler]:
    """List the claims handlers."""
    rows = db.execute("SELECT data FROM handlers ORDER BY handler_id").fetchall()
    return [Handler(**json.loads(row["data"])) for row in rows]
