"""The UnderCover database: SQLite, seeded from the records in data/."""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DEFAULT_DATABASE = ROOT / "backend" / "undercover.db"

SCHEMA = """
CREATE TABLE claims (
    claim_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    status TEXT NOT NULL,
    thread_id TEXT,
    agent_running INTEGER NOT NULL DEFAULT 0,
    decision TEXT,
    payout REAL,
    reason TEXT,
    policy_section TEXT,
    decided_at TEXT,
    paid_amount REAL,
    paid_at TEXT,
    signed_off_by TEXT,
    signed_off_at TEXT
);
CREATE TABLE policies (policy_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE customers (customer_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE plans (plan TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE add_ons (add_on TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE handlers (handler_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE company (id INTEGER PRIMARY KEY CHECK (id = 1), data TEXT NOT NULL);
CREATE TABLE steps (
    claim_id TEXT NOT NULL,
    number INTEGER NOT NULL,
    thread_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (claim_id, number)
);
"""


def database_path() -> Path:
    """Return the database file, from UNDERCOVER_DB or the default."""
    return Path(os.getenv("UNDERCOVER_DB", DEFAULT_DATABASE))


def connect() -> sqlite3.Connection:
    """Open the database, with rows that can be read by column name."""
    connection = sqlite3.connect(database_path(), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def load(name: str) -> Any:
    """Read one JSON file from data/."""
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def seed() -> dict[str, int]:
    """Rebuild the database from data/ and return how many records it loaded."""
    path = database_path()
    path.unlink(missing_ok=True)
    claims = load("claims.json")
    policies = load("policies.json")
    customers = load("customers.json")
    plans = load("plans.json")
    handlers = load("handlers.json")
    with connect() as db:
        db.executescript(SCHEMA)
        db.executemany(
            "INSERT INTO claims (claim_id, data, status) VALUES (?, ?, 'waiting')",
            [(c["claim_id"], json.dumps(c)) for c in claims],
        )
        db.executemany(
            "INSERT INTO policies VALUES (?, ?)",
            [(p["policy_id"], json.dumps(p)) for p in policies],
        )
        db.executemany(
            "INSERT INTO customers VALUES (?, ?)",
            [(c["customer_id"], json.dumps(c)) for c in customers],
        )
        db.executemany(
            "INSERT INTO plans VALUES (?, ?)",
            [(p["plan"], json.dumps(p)) for p in plans["plans"]],
        )
        db.executemany(
            "INSERT INTO add_ons VALUES (?, ?)",
            [(a["add_on"], json.dumps(a)) for a in plans["add_ons"]],
        )
        db.executemany(
            "INSERT INTO handlers VALUES (?, ?)",
            [(h["handler_id"], json.dumps(h)) for h in handlers],
        )
        db.execute(
            "INSERT INTO company VALUES (1, ?)", (json.dumps(load("company.json")),)
        )
    db.close()
    return {
        "claims": len(claims),
        "policies": len(policies),
        "customers": len(customers),
        "plans": len(plans["plans"]),
        "handlers": len(handlers),
    }


def ensure() -> None:
    """Seed the database if it doesn't exist yet."""
    if not database_path().exists():
        seed()
