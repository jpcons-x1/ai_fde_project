"""The UnderCover backend."""

import json
import sqlite3
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
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
    NewDecision,
    NewPayment,
    NewSignOff,
    NewStep,
    Payment,
    Plan,
    Policy,
    PreviousClaim,
    SignOff,
    StartClaim,
    Step,
    Text,
)

INSTRUCTIONS = Path(__file__).resolve().parent / "instructions.md"


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


@app.get("/api/instructions", operation_id="get_instructions")
def get_instructions() -> Text:
    """Get the agent's instructions."""
    return Text(text=INSTRUCTIONS.read_text(encoding="utf-8"))


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def require_status(claim: Claim, status: str) -> None:
    """Raise 409 unless the claim stands where the operation needs it."""
    if claim.status != status:
        raise HTTPException(409, f"Claim {claim.claim_id} is {claim.status}")


@app.post("/api/claims/{claim_id}/start", operation_id="start_claim")
def start_claim(claim_id: str, body: StartClaim, db: Db) -> Claim:
    """Mark a waiting claim as in progress for an agent run."""
    require_status(load_claim(db, claim_id), "waiting")
    db.execute(
        "UPDATE claims SET status = 'in_progress', thread_id = ? WHERE claim_id = ?",
        (body.thread_id, claim_id),
    )
    db.commit()
    return load_claim(db, claim_id)


@app.post("/api/claims/{claim_id}/release", operation_id="release_claim")
def release_claim(claim_id: str, db: Db) -> Claim:
    """Put a claim in progress back in the queue, undecided."""
    require_status(load_claim(db, claim_id), "in_progress")
    db.execute("UPDATE claims SET status = 'waiting' WHERE claim_id = ?", (claim_id,))
    db.commit()
    return load_claim(db, claim_id)


@app.post("/api/claims/{claim_id}/steps", operation_id="record_step")
def record_step(claim_id: str, body: NewStep, db: Db) -> Step:
    """Record one step the agent took on a claim."""
    load_claim(db, claim_id)
    step = Step(
        **body.model_dump(),
        number=db.execute(
            "SELECT COALESCE(MAX(number), 0) + 1 FROM steps WHERE claim_id = ?",
            (claim_id,),
        ).fetchone()[0],
        created_at=now(),
    )
    db.execute(
        "INSERT INTO steps VALUES (?, ?, ?, ?, ?, ?)",
        (claim_id, step.number, step.thread_id, step.kind, step.text, step.created_at),
    )
    db.commit()
    return step


@app.get("/api/claims/{claim_id}/steps", operation_id="list_steps")
def list_steps(claim_id: str, db: Db) -> list[Step]:
    """List the steps the agent took on a claim, in order."""
    load_claim(db, claim_id)
    rows = db.execute(
        "SELECT * FROM steps WHERE claim_id = ? ORDER BY number", (claim_id,)
    ).fetchall()
    return [Step(**dict(row)) for row in rows]


@app.post("/api/claims/{claim_id}/decision", operation_id="decide_claim")
def decide_claim(claim_id: str, body: NewDecision, db: Db) -> Claim:
    """Approve, decline or refer a claim in progress, with the payout and reason."""
    claim = load_claim(db, claim_id)
    require_status(claim, "in_progress")
    if body.payout > claim.amount_claimed:
        raise HTTPException(422, "The payout is more than the amount claimed")
    needs_sign_off = body.decision == "approve" and body.payout > approval_limit(db)
    db.execute(
        """UPDATE claims SET status = ?, decision = ?, payout = ?, reason = ?,
           policy_section = ?, decided_at = ? WHERE claim_id = ?""",
        (
            "awaiting_signoff" if needs_sign_off else "decided",
            body.decision,
            round(body.payout, 2),
            body.reason,
            body.policy_section,
            now(),
            claim_id,
        ),
    )
    db.commit()
    return load_claim(db, claim_id)


@app.post("/api/claims/{claim_id}/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, body: NewPayment, db: Db) -> Claim:
    """Pay the approved payout on a claim."""
    claim = load_claim(db, claim_id)
    if claim.decision is None or claim.decision.decision != "approve":
        raise HTTPException(409, f"Claim {claim_id} is not approved")
    if claim.payment:
        raise HTTPException(409, f"Claim {claim_id} is already paid")
    if claim.status == "awaiting_signoff":
        raise HTTPException(
            403,
            f"A payout over ${claim.payout_approval_limit:,.2f} "
            "needs a handler's sign-off",
        )
    if round(body.amount, 2) != claim.decision.payout:
        raise HTTPException(
            409, f"The approved payout is ${claim.decision.payout:,.2f}"
        )
    db.execute(
        "UPDATE claims SET paid_amount = ?, paid_at = ? WHERE claim_id = ?",
        (claim.decision.payout, now(), claim_id),
    )
    db.commit()
    return load_claim(db, claim_id)


@app.post("/api/claims/{claim_id}/sign-off", operation_id="sign_off_claim")
def sign_off_claim(claim_id: str, body: NewSignOff, db: Db) -> Claim:
    """Sign off an approval over the limit as a handler, which pays it."""
    claim = load_claim(db, claim_id)
    handler = Handler(**fetch(db, "handlers", "handler_id", body.handler_id))
    require_status(claim, "awaiting_signoff")
    if not handler.can_approve_over_limit:
        raise HTTPException(403, f"{handler.name} can't sign off this payout")
    signed_at = now()
    db.execute(
        """UPDATE claims SET status = 'decided', signed_off_by = ?, signed_off_at = ?,
           paid_amount = payout, paid_at = ? WHERE claim_id = ?""",
        (handler.handler_id, signed_at, signed_at, claim_id),
    )
    db.commit()
    return load_claim(db, claim_id)
