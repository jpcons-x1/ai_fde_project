# Status

The pilot is being built from `docs/PLAN.md`. Phase 1 is done.

- `backend/`: FastAPI on SQLite. The database is `backend/undercover.db`, or the path in `UNDERCOVER_DB`, and is seeded from `data/` on startup if it doesn't exist. Read operations for claims, policies (with their plan and add-ons), customers, claim history, the policy wording and the handlers.
- `agent/`: the skeleton entry point `run(claim_id, thread_id)`, with one tool that calls the health route
- `dashboard/`: one page that shows whether the backend is up
- `e2e/`: one test of that page

## Running it

- `npm run dev` starts the backend on port 8000 and the dashboard on port 5173.
- `uv run -m backend.seed` rebuilds the database, which puts every claim back in the queue as waiting.
