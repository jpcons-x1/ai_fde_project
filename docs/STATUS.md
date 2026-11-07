# Status

The pilot is being built from `docs/PLAN.md`. Phases 1 to 3 are done.

- `backend/`: FastAPI on SQLite. The database is `backend/undercover.db`, or the path in `UNDERCOVER_DB`, and is seeded from `data/` on startup if it doesn't exist.
  - Reads claims, policies (with their plan and add-ons), customers, claim history, the policy wording, the handlers and the agent's instructions (`backend/instructions.md`).
  - Moves a claim through its statuses: `waiting`, `in_progress`, `awaiting_signoff` and `decided`. It records the agent's steps, decisions and payments, and handlers' sign-offs.
  - Refuses a payment over the $1,000 limit with a 403 until a handler signs off. The sign-off makes the payment.
  - `POST /api/claims/{id}/run` starts the agent on a waiting claim in the background.
- `agent/`: the UnderCover Agent, `run(claim_id, thread_id)`, built with `create_agent` on OpenRouter (`openai/gpt-6-luna` at low reasoning effort, or `MODEL_NAME`). It fetches its instructions from the backend, and its six tools each call one API operation. It records every tool call, result and message as a step, and puts the claim back in the queue if a run ends without a decision. It reaches the backend at `BACKEND_URL`, or `http://127.0.0.1:8000` by default.
- `dashboard/`: one page that shows whether the backend is up
- `e2e/`: one test of that page

## Running it

- `npm run dev` starts the backend on port 8000 and the dashboard on port 5173.
- `uv run -m backend.seed` rebuilds the database, which puts every claim back in the queue as waiting.
- `uv run -m agent CLM-1001` works one claim with the real model, which costs a few cents. `uv run -m agent` works every waiting claim in turn.
