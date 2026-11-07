# Plan: the claims pilot

This plan builds the pilot in `docs/SPEC.md`: a backend that holds the claims queue, the UnderCover Agent that decides claims through the backend's API, and a dashboard where the handlers watch the queue, read each claim and decision, follow the agent step by step and sign off large payouts.

It starts from the hello-world skeleton in `docs/STATUS.md` and keeps every check in `docs/PROCESS.md` green after each phase.

## The shape of the build

```
data/*.json, *.md ──seed──> backend (FastAPI + SQLite) <──HTTP── agent (create_agent on OpenRouter)
                                   ^
                                   └──/api── dashboard (React + Vite)
```

- **The backend owns the state and enforces the rules.** Claims, decisions, payments and the agent's steps live in SQLite. The payout rule is checked in the backend, not in the agent's prompt, so a payment over $1,000 is blocked even if the agent tries to make it.
- **The agent reaches everything through the API.** Its tools are thin wrappers around API operations, and it fetches its instructions from the backend at the start of each run. It never imports the backend or reads `data/`.
- **The dashboard reads the same API.** It polls while the agent works, which is simpler than a streaming connection and fast enough for a person to follow.

### Key decisions

| Decision | Choice | Why |
|---|---|---|
| Database access | Python's built-in `sqlite3`, no ORM | A handful of tables. An ORM adds a layer without saving any code here. |
| Storing records | Claims, policies, customers, plans and handlers as JSON documents keyed by id; status, decisions, payments and steps as columns | The seed data is nested (items, documents, travelers). Keeping it whole is simplest, and the fields the rules depend on get proper columns. |
| Seeding | On startup, if the database file doesn't exist, load it from `data/`. `uv run -m backend.seed` rebuilds it. | Gives a clean queue on demand for demos and for the end-to-end tests. |
| Database location | `backend/undercover.db`, or the path in `UNDERCOVER_DB` | Lets the end-to-end tests use their own database and leave the dev one alone. |
| Agent instructions | A markdown file, `backend/instructions.md`, served read-only by `GET /api/instructions` | The spec asks for the agent to reach its instructions through the API, and for the handlers to read them. |
| Policy wording | The full `data/policy_wording.md`, served by `GET /api/policy-wording` | The spec says decisions follow the policy wording, and the agent works from the wording alone. The claims manual stays out. |
| Customer data for the agent | Only the claim history, through `GET /api/customers/{id}/claim-history` | The agent needs the history but not the address, phone or date of birth. Less personal data goes to the model. |
| Recording the agent's steps | The agent's `run` streams the graph's updates and posts each one to the backend. The model doesn't call a tool for this. | Every tool call, result and message is recorded, whether or not the model remembers to report it. |
| Starting a run from the dashboard | `POST /api/claims/{id}/run` starts `agent.run` in a FastAPI background task | The handlers can start the agent from the screen. The agent still talks to the backend over HTTP, so the rule above holds. |
| Paying | The agent approves with `decide_claim`, then pays with `pay_claim(amount)`. Over $1,000, `pay_claim` is refused until a handler signs off, and the sign-off releases the payment. | Matches the tech stack (paying is its own operation that takes the amount) and the spec's rule. |
| Routing in the dashboard | Hash routes (`#/`, `#/claims/CLM-1001`, `#/instructions`), no router library | Three pages. A dependency isn't worth it. |
| Live updates | Polling every 2 seconds while a claim is in progress | Simple, and easy to test. |

### Claim statuses

| Status | Label | Color | When |
|---|---|---|---|
| `waiting` | Waiting | Cerulean | Seeded (`open` in `data/claims.json`), or put back after a run that ended without a decision |
| `in_progress` | In progress | Marigold | The agent has started the claim |
| `awaiting_signoff` | Waiting for sign-off | Coral | The agent approved a payout over $1,000 |
| `decided` | Decided | Sea Green | Declined, referred, approved at $1,000 or less, or signed off |

Decisions are `approve`, `decline` or `refer`. The payout is $0 unless the claim is approved, and never more than the amount claimed.

### The API

Every operation has an `operation_id`, a one-line docstring and only required inputs.

| Method and path | `operation_id` | Used by |
|---|---|---|
| `GET /api/health` | `health` | dashboard |
| `GET /api/claims` | `list_claims` | dashboard |
| `GET /api/claims/{claim_id}` | `get_claim` | agent, dashboard |
| `GET /api/policies/{policy_id}` | `get_policy` | agent, dashboard |
| `GET /api/customers/{customer_id}` | `get_customer` | dashboard |
| `GET /api/customers/{customer_id}/claim-history` | `get_claim_history` | agent |
| `GET /api/policy-wording` | `get_policy_wording` | agent |
| `GET /api/instructions` | `get_instructions` | agent, dashboard |
| `GET /api/handlers` | `list_handlers` | dashboard |
| `POST /api/claims/{claim_id}/start` | `start_claim` | agent |
| `POST /api/claims/{claim_id}/steps` | `record_step` | agent |
| `GET /api/claims/{claim_id}/steps` | `list_steps` | dashboard |
| `POST /api/claims/{claim_id}/decision` | `decide_claim` | agent |
| `POST /api/claims/{claim_id}/payment` | `pay_claim` | agent |
| `POST /api/claims/{claim_id}/sign-off` | `sign_off_claim` | dashboard |
| `POST /api/claims/{claim_id}/release` | `release_claim` | agent |
| `POST /api/claims/{claim_id}/run` | `run_agent` | dashboard |

`get_policy` returns the policy with its plan's limits and the details of its add-ons, so the agent sees every number the wording refers to in one call.

### Keeping the answer key out

The backend never reads `data/evals/` or `data/security/`, because the seed names each file it loads. Tests check that the seed reads nothing under those folders, and that the agent's code doesn't import `backend` or open anything in `data/`. Scoring the agent against the handlers' decisions isn't part of the pilot: `docs/PROCESS.md` keeps `data/evals/` closed unless the team asks.

## Phase 1: The records in SQLite and the read API

Builds the database and the operations that read it, so that everything after has real data to work on.

- `backend/db.py`: the schema, a connection per request, and the seed from `data/claims.json`, `policies.json`, `customers.json`, `plans.json`, `handlers.json` and `company.json`. The $1,000 limit comes from `company.json`.
- `backend/seed.py`: `uv run -m backend.seed` rebuilds the database.
- `backend/models.py`: Pydantic models for every response.
- `backend/main.py`: `list_claims`, `get_claim`, `get_policy`, `get_customer`, `get_claim_history`, `get_policy_wording`, `list_handlers`.
- `*.db` added to `.gitignore`.
- Tests on a temporary database for each test.

Success criteria:

- [x] `uv run -m backend.seed` creates `backend/undercover.db` and prints that it loaded 25 claims, 50 policies, 49 customers, 3 plans and 3 handlers
- [x] `GET /api/claims` returns 25 claims, all `waiting`, each with the claim id, the customer's name, the claim type, the amount claimed, the submitted date and the status
- [x] `GET /api/claims/CLM-1001` returns the story, the 3 items, the 4 documents and `amount_claimed` 420.0
- [x] `GET /api/policies/POL-2001` returns plan `premium` with its limits, including `trip_delay_max` 800.0 and `deductible` 50.0
- [x] `GET /api/customers/CUS-3001/claim-history` returns one earlier claim, CLM-0412, and no address, phone or email
- [x] `GET /api/claims/CLM-9999` returns 404
- [x] `GET /api/policy-wording` returns the text of `data/policy_wording.md`
- [x] A test confirms that the seed reads no file under `data/evals/` or `data/security/`
- [x] Every route has an `operation_id` and a one-line docstring, checked by a test over `app.routes`
- [x] `npm run check:python` passes with coverage at 80% or more

## Phase 2: Decisions, payments and the sign-off rule

Builds the operations that change a claim, and the rules that guard them. This is where the spec's payment rule is enforced.

- `start_claim` (with the thread id): `waiting` to `in_progress`; 409 from any other status.
- `record_step` and `list_steps`: the agent's steps, each with the thread id, a number, a kind (`tool_call`, `tool_result` or `message`), the text and the time.
- `decide_claim`: takes the decision, the payout, the reason and the policy section. Only on a claim in progress. The payout must be 0 unless approving, and between 0 and the amount claimed. An approval over the limit moves the claim to `awaiting_signoff`; every other decision moves it to `decided`.
- `pay_claim`: takes the amount. Refused with 409 if the claim isn't approved, the amount isn't the approved payout or it's already paid. Refused with 403 and the message "A payout over $1,000.00 needs a handler's sign-off" while the claim waits for sign-off.
- `sign_off_claim`: takes the handler id. Only on a claim waiting for sign-off, and only by a handler who `can_approve_over_limit`. Records the sign-off, makes the payment and moves the claim to `decided`.
- `release_claim`: `in_progress` back to `waiting`, for a run that ends without a decision.
- `get_claim` now includes the decision, the payment and the sign-off.
- `get_instructions`: serves `backend/instructions.md`, written in this phase. It tells the agent how to work a claim: read the claim, the policy, the claim history and the wording; check the dates, the waiting periods, the exclusions and the documents; work out the payout with section 10 of the wording; record the decision with a reason of two or three sentences and the section; then pay an approved payout.

Success criteria:

- [x] A test walks a claim from `waiting` to `in_progress` to `decided` with an approval of $420.00, then pays $420.00, and `get_claim` shows the decision and the payment
- [x] A test approves $1,950.00 on a claim, sees `awaiting_signoff`, and `pay_claim` returns 403 with the sign-off message and records no payment
- [x] After `sign_off_claim` with `HND-01`, that claim is `decided`, paid $1,950.00, and shows Dana Whitfield's sign-off
- [x] A second `pay_claim` on a paid claim returns 409, and so does paying a different amount from the approved payout
- [x] `decide_claim` returns 422 for a decline with a payout, a payout above the amount claimed or an unknown decision, and 409 on a claim that isn't in progress
- [x] `sign_off_claim` returns 404 for an unknown handler and 409 on a claim that isn't waiting for sign-off
- [x] Steps posted to a claim come back from `list_steps` in order
- [x] `GET /api/instructions` returns the instructions
- [x] `npm run check:python` passes with coverage at 80% or more

## Phase 3: The UnderCover Agent

Turns the skeleton agent into one that decides claims, with every step recorded in the backend.

- Tools in `agent/main.py`, each a call to one API operation: `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `decide_claim` and `pay_claim`. A refused call returns the backend's message to the model as the tool's result, so it can see why the payment was blocked.
- `run(claim_id, thread_id)`: starts the claim, fetches the instructions from the backend, streams the agent with `stream_mode="updates"`, and posts each tool call, tool result and message as a step. If the run ends without a decision, it releases the claim and records a step that says so. It returns the final reply.
- `agent/__main__.py`: `uv run -m agent CLM-1001` works one claim; `uv run -m agent` works every waiting claim in turn.
- `run_agent` in the backend: starts `run` in a background task with a new thread id, and returns the thread id.
- The model stays as in the skeleton: `openai/gpt-6-luna` with low reasoning effort, or `MODEL_NAME`.

Success criteria:

- [ ] A test with a stub model runs a claim end to end: it reads the claim, the policy, the history and the wording, approves $375.00 and pays it. The claim is `decided` and paid, and the steps show every tool call in order
- [ ] A test with a stub model that approves $1,950.00 and then calls `pay_claim` sees the 403 message as the tool result, and the claim stays `awaiting_signoff` with no payment
- [ ] A test with a stub model that never decides leaves the claim `waiting` with a final step saying the run ended without a decision
- [ ] A test of `run_agent` with a stub model returns a thread id, and the claim ends up decided
- [ ] A test confirms that no file in `agent/`, apart from its tests, imports `backend` or refers to `data/`
- [ ] A test confirms that the agent's system prompt is the text from `GET /api/instructions`
- [ ] With the backend running, `uv run -m agent CLM-1001` decides the claim with the real model, and `GET /api/claims/CLM-1001` shows a decision, a reason of two or three sentences, a policy section and, if approved, a payment. This costs a few cents
- [ ] `npm run check:python` passes with coverage at 80% or more

## Phase 4: The dashboard's layout and the queue

Builds the dashboard's frame in the UnderCover brand and the page the handlers start from.

- Fonts from Google Fonts in `index.html`: Instrument Sans, Instrument Serif and JetBrains Mono.
- `dashboard/src/styles.css`: the brand colors as CSS variables, light and dark mode from the system setting, rounded panels with no outlines, and darkened Sea Green and Marigold for text on light backgrounds.
- `dashboard/src/api.ts`: types for every response and a function per operation.
- A header with the UnderCover name and links to the queue and the instructions, and hash routes for the three pages.
- The queue page: a count of claims in each status, then a table of claims with the id and amounts in JetBrains Mono, amounts as $1,250.00, and the status as a colored chip. Each row opens its claim.
- The backend health check moves into the header.

Success criteria:

- [ ] Vitest tests with a stubbed `fetch` cover the queue table, the status counts, the money format and the routing
- [ ] In the browser, checked with the Playwright MCP server, `http://localhost:5173/` shows 25 claims, all Waiting, with the right fonts and colors, in light and in dark mode
- [ ] Clicking CLM-1001 goes to `#/claims/CLM-1001`
- [ ] `npm run check:ts` passes with coverage at 80% or more

## Phase 5: The claim page and the instructions page

Builds the pages where the handlers read a claim, follow the agent and sign off.

- The claim page:
  - The claim: summary, story, dates, place, items with amounts and the documents.
  - The policy: plan, add-ons, trip dates and travelers. The customer: name and earlier claims.
  - The decision, once there is one: the decision as a chip, the payout, the reason, the policy section, and the payment or "Waiting for sign-off".
  - Sign-off, on a claim waiting for it: a choice of handler and a "Sign off and pay" button.
  - The agent's activity: its steps in order, as tool calls, results and messages. It polls every 2 seconds while the claim is in progress and stops once it isn't.
  - A "Run the agent" button on a waiting claim.
- The instructions page: the agent's instructions, read only, with no way to edit them.

Success criteria:

- [ ] Vitest tests cover the claim page in each status, the decision panel, sign-off, the activity list and the polling that starts and stops, and the instructions page
- [ ] In the browser, checked with the Playwright MCP server, CLM-1001 shows its story, items, documents, policy and the earlier claim CLM-0412
- [ ] After "Run the agent" on a claim, the activity fills in step by step as the agent works, then the decision appears with its reason and section, without reloading the page. This costs a few cents
- [ ] A claim approved over $1,000 shows "Waiting for sign-off". After choosing a handler and "Sign off and pay", it shows Decided with the payment and the handler's name
- [ ] `#/instructions` shows the instructions with nothing to edit
- [ ] `npm run check:ts` passes with coverage at 80% or more

## Phase 6: End-to-end tests and handover

Proves the whole product works together, without calling a model, and leaves it ready for the student's review.

- Playwright starts its own backend on port 8001 with `UNDERCOVER_DB` pointing at a fresh database under `e2e/`, and its own dashboard on port 5174 whose proxy points at it, so the tests never touch the dev database. The proxy target comes from an environment variable in `vite.config.ts`.
- End-to-end tests:
  - The queue shows 25 claims.
  - A claim page shows the story and documents.
  - The instructions page shows the instructions.
  - The test calls the API to start a claim, record steps and approve $1,950.00, then checks the page shows the steps and "Waiting for sign-off", signs off in the browser and sees Decided and the payment.
  - The test calls `pay_claim` on a claim waiting for sign-off and gets 403.
- `README.md` in the product's section and `docs/STATUS.md`: what's built, how to run it, how to reset the queue and how to run the agent.

Success criteria:

- [ ] `npm run e2e` passes, and the dev database is unchanged afterwards
- [ ] `npm run check` passes in full
- [ ] With `npm run dev`, the agent decides a claim under $1,000 and one over it from the dashboard, checked with the Playwright MCP server, and the one over $1,000 waits for sign-off
- [ ] `docs/STATUS.md` describes the pilot as built

## Not in this plan

- Scoring the agent against `data/evals/`. The spec keeps the answer key for checking the agent later, and it stays closed until the team asks.
- The claims manual, sign-in, real payments and messages to customers, which the spec leaves out.
- The agent's harness, durable state and the swarm, which come in later builds.
