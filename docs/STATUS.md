# Status

The pilot from `docs/PLAN.md` is built: all six phases are done.

## What's built

- `backend/`: FastAPI on SQLite. The database is `backend/undercover.db`, or the path in `UNDERCOVER_DB`, and is seeded from `data/` on startup if it doesn't exist. It never reads `data/evals/` or `data/security/`.
  - Reads claims, policies (with their plan and add-ons), customers, claim history (without personal details), the policy wording, the handlers and the agent's instructions (`backend/instructions.md`).
  - Moves a claim through its statuses: `waiting`, `in_progress`, `awaiting_signoff` and `decided`. It records the agent's steps, decisions and payments, and handlers' sign-offs.
  - Refuses a payment over the $1,000 limit with a 403 until a handler signs off. The sign-off makes the payment.
  - `POST /api/claims/{id}/run` marks a waiting claim in progress and starts the agent on it in the background. Each claim has an `agent_running` flag, which `finish_run` clears when the run ends.
- `agent/`: the UnderCover Agent, `run(claim_id, thread_id)`, built with `create_agent` on OpenRouter (`openai/gpt-6-luna` at low reasoning effort, or `MODEL_NAME`).
  - It fetches its instructions from the backend, and each of its six tools calls one API operation: `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `decide_claim` and `pay_claim`.
  - It records every tool call, result and message as a step. When the run ends it calls `finish_run`, which puts the claim back in the queue if it wasn't decided.
  - It reaches the backend at `BACKEND_URL`, or `http://127.0.0.1:8000` by default.
- `dashboard/`: React in the UnderCover brand, light and dark.
  - The queue at `#/` shows a count per status and every claim with its status, decision and payout. It refreshes while a claim is in progress.
  - A claim's page at `#/claims/<id>` shows the claim, its documents, the policy, the customer's earlier claims and the decision. It also shows the agent's activity, which updates every 2 seconds while the agent runs, a "Run the agent" button on a waiting claim, and sign-off for a payout over the limit.
  - `#/instructions` shows the agent's instructions, read only.
  - The `/api` proxy points at `BACKEND_URL`, or `http://127.0.0.1:8000` by default.
- `e2e/`: Playwright tests of the queue, a claim's page, the instructions and the sign-off rule. They run their own backend on port 8001 with the database `e2e/undercover-e2e.db`, and their own dashboard on port 5174, so they leave the dev database alone. No test calls a model.

## Running it

- `npm run dev` starts the backend on port 8000 and the dashboard at http://localhost:5173.
- `uv run -m backend.seed` rebuilds the database, which puts every claim back in the queue as waiting. Run it after a change to the schema, too.
- On a claim's page, "Run the agent" decides the claim with the real model, which costs a few cents.
- `uv run -m agent CLM-1001` works one claim from the command line, with the backend running. `uv run -m agent` works every waiting claim in turn.
- `npm run check` runs every check, including the end-to-end tests.
