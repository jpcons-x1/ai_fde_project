# Plan: the harness

This plan builds `docs/HARNESS.md`: the UnderCover Agent grows from a function that decides one claim at a time into an agent that works the whole queue on its own. It plans its work as a to-do list, hands each claim to a fresh helper, looks up the sections of the policy wording and the claims manual that it needs, and recovers from failures without anyone stepping in.

It starts from the finished pilot in `docs/STATUS.md` and keeps every check in `docs/PROCESS.md` green after each phase. `docs/PLAN.md` stays as it is.

## The shape of the build

```
dashboard ──/api──> backend (FastAPI + SQLite) <──HTTP── queue agent
                    holds claims, runs, to-do lists,             │ plans, orders, summarizes
                    reads, steps; enforces the rules             │ tool: work_claim
                                                                 ▼
                                                        claim agent, a fresh one per claim
```

- **Two agents, one harness.** The queue agent organizes the work: it lists the waiting claims, writes the to-do list, chooses the order and writes the summary. The claim agent decides one claim from a clean start. Both are LangChain `create_agent` agents with LangChain's own middleware. No other agent framework is added (`deepagents` is installed in the project, but `docs/HARNESS.md` asks us to build these pieces into our own agent, so it stays unused).
- **The backend still owns the state and the rules.** The to-do list, the cap, the failure count and what the agent read are stored there. A claim is never decided or paid twice because the backend refuses it, not because the agent remembers.
- **The agent still reaches everything through the API.** It never imports `backend` or opens `data/`.

### Key decisions

| Decision | Choice | Why |
|---|---|---|
| To-do list | Our own `write_todos` tool that saves the list in the backend, one item per claim with four statuses | LangChain's `TodoListMiddleware` keeps the list in the agent's memory and has three statuses, so the dashboard couldn't see it and "left for a handler" wouldn't fit |
| The fresh helper | `work_claim(claim_id)` is a tool of the queue agent. It runs a new claim agent in the same process with a new thread, and returns one line | Each claim starts with an empty context, so a step doesn't cost more as the run goes on. Only one line comes back to the queue agent |
| The line that comes back | Written by the harness from the claim's real state in the backend, not by the helper's model | The queue agent can trust it. A crashed helper still reports what went wrong |
| The cap | `limit`, the number of different claims a run may work. `work_claim` refuses a claim beyond it. Working a failed claim again doesn't use up the cap | A trial must cost little, so the harness enforces it, not the prompt |
| Optional inputs | `limit` is always sent. The dashboard and the command line send the number of waiting claims for "no cap" | `docs/TECH_STACK.md` allows no optional inputs on an API operation |
| One claim at a time | `work_claim` holds a lock while it works, so two calls in one model turn run one after the other | Keeps the cap exact and the to-do list in order |
| A new claim status | `left_for_handler`, shown as "Left for a handler" in Raspberry | A claim the agent failed on twice is not waiting for the agent any more, and it is not a real `refer` decision. The same word is the fourth to-do status |
| Failure count | The backend's `finish_run` adds one failure when a claim is still in progress at the end of a run. The first puts it back to `waiting`, the second makes it `left_for_handler` | The rule lives next to the other rules, and `finish_run` already runs at the end of every run |
| Transient errors | LangChain's `ModelRetryMiddleware` and `ToolRetryMiddleware` retry twice with a backoff. `ModelCallLimitMiddleware` stops a run that loops. A failure that survives all that is caught once, where a claim's run starts | Timeouts and provider errors usually pass. The one `except` is needed so a bad claim can't stop the queue |
| Never twice | The backend already returns 409 for a second decision or payment, so a retried call can't repeat one. If a run dies after an approval of $1,000 or less and before the payment, the harness pays the approved amount once | Otherwise that claim would sit decided and unpaid, which is as stuck as being in progress |
| Missed claims | An `after_model` middleware on the queue agent. When the agent tries to finish, it checks the backend. If a claim is missed, it sends the agent back to work, at most twice | A model forgets. The check is the harness's job. See below |
| Looking things up | `search_documents(query)` finds sections of the wording and the manual. `read_section(claim_id, document, section)` returns one and records that this claim's agent read it. The whole-wording tool and `GET /api/policy-wording` go | This is how a handler uses a manual, and the claim page can show what was read |
| Instructions | Two files, `backend/instructions/queue.md` and `claim.md`, served together by `GET /api/instructions` | The instructions page shows both, and each agent gets its own part |
| The model | Default `deepseek/deepseek-v4.1-flash` with low reasoning effort. `MODEL_NAME` still overrides it | As the brief asks |
| Call limits | Model call limits per run, and a `recursion_limit` set from them | LangGraph's default of 25 steps is about 12 model calls. The claim agent now makes more, and the queue agent makes several per claim |

### What "missed" means

When the queue agent tries to finish, the harness lists the waiting claims:

- If the run has worked fewer than `limit` claims, every waiting claim is missed.
- If the run has reached its cap, only a claim the run already worked is missed: one that failed once and went back to waiting.

The agent is sent back with the claim ids. After two such nudges the run ends anyway, and the stored summary ends with the claims still waiting.

### Claim statuses

| Status | Label | Color | When |
|---|---|---|---|
| `waiting` | Waiting | Cerulean | As in the pilot, and after a first failed run |
| `in_progress` | In progress | Marigold | As in the pilot |
| `awaiting_signoff` | Waiting for sign-off | Coral | As in the pilot |
| `decided` | Decided | Sea Green | As in the pilot |
| `left_for_handler` | Left for a handler | Raspberry | The agent's run on the claim failed twice |

To-do statuses reuse the colors: `todo` (To do, Cerulean), `in_progress` (In progress, Marigold), `done` (Done, Sea Green) and `left_for_handler` (Left for a handler, Raspberry).

### The API

New and changed operations. All the pilot's other operations stay as they are. Every operation has an `operation_id`, a one-line docstring and only required inputs.

| Method and path | `operation_id` | Used by | Change |
|---|---|---|---|
| `POST /api/runs` | `run_queue` | dashboard | New. Takes `limit`, starts the queue agent in the background, returns the run |
| `POST /api/runs/{run_id}/start` | `start_queue_run` | agent | New. Takes `limit`. Creates the run, or returns it if it exists |
| `GET /api/runs/latest` | `get_latest_queue_run` | dashboard | New. The newest run with its to-do list and summary, or null |
| `PUT /api/runs/{run_id}/todos` | `write_todos` | agent | New. Replaces the to-do list |
| `POST /api/runs/{run_id}/finish` | `finish_queue_run` | agent | New. Takes the summary and ends the run |
| `GET /api/documents/search` | `search_documents` | agent | New. Takes `query`, returns up to 5 sections of the wording and the manual |
| `POST /api/claims/{claim_id}/reads` | `read_section` | agent | New. Takes the document and the section number, returns the text and records the read |
| `GET /api/claims/{claim_id}/reads` | `list_reads` | dashboard | New |
| `GET /api/instructions` | `get_instructions` | agent, dashboard | Now returns `queue` and `claim` |
| `POST /api/claims/{claim_id}/finish` | `finish_run` | agent | Counts failures |
| `GET /api/policy-wording` | `get_policy_wording` | | Removed |

Claims and their summaries now carry `failures`. A run has its id, `limit`, a status of `running` or `finished`, its to-do list, its summary and its times. A to-do item is a `claim_id` and a status.

### Keeping the answer key out

Nothing changes here. The new instructions are written from `data/policy_wording.md` and `data/claims_manual.md` only. The sections come from those two files and nothing else, and a test checks it, like the seed's test does. The agent's code still never imports `backend` or mentions `data/`.

### Things to watch in the live run

- OpenRouter might ignore `reasoning_effort` for DeepSeek. If the live request shows no low effort, pass it as `extra_body={"reasoning": {"effort": "low"}}`.
- The claim agent runs inside a tool of the queue agent. If LangGraph's nested streams misbehave, give the inner agent its own explicit config.

## Phase 1: Runs, the to-do list and failed claims in the backend

Builds the state the harness keeps, so everything after has somewhere to put it.

- `backend/db.py`: a `runs` table (id, `claim_limit`, status, to-do list as JSON, summary, started and finished times) and a `failures` column on claims.
- `backend/models.py`: `left_for_handler` in `Status`, the run and to-do models, and `failures` on `Claim` and `ClaimSummary`.
- `backend/main.py`: `start_queue_run`, `write_todos`, `finish_queue_run` and `get_latest_queue_run`. `finish_run` counts failures. `start_claim` and `run_agent` already refuse any claim that isn't waiting, so they refuse a claim left for a handler.
- `uv run -m backend.seed` after the schema change.

Success criteria:

- [ ] A test starts a run with limit 5, writes a to-do list of three claims, and `get_latest_queue_run` returns it. Writing again replaces the list. `finish_queue_run` stores the summary, and the run is `finished`
- [ ] `get_latest_queue_run` returns null before any run, and returns the newer of two runs after
- [ ] `start_queue_run` twice with the same id returns the same run
- [ ] `write_todos` returns 422 for an unknown claim, a repeated claim and an unknown status, and `start_queue_run` returns 422 for a limit below 1
- [ ] A claim started and then finished without a decision is `waiting` with `failures` 1. Started and finished again, it is `left_for_handler` with `failures` 2, and `start_claim` and `run_agent` return 409 for it
- [ ] `finish_run` on a decided claim leaves it decided with `failures` 0
- [ ] The pilot's tests still pass: a second decision and a second payment return 409, and a payment over $1,000 returns 403
- [ ] `list_claims` and `get_claim` show `failures`
- [ ] `uv run -m backend.seed` rebuilds the database and prints 25 claims, all `waiting`
- [ ] `npm run check:python` passes with coverage at 80% or more

## Phase 2: Looking things up in the wording and the manual

Builds the lookup that replaces handing the agent the whole policy wording.

- `backend/documents.py`: splits `data/policy_wording.md` and `data/claims_manual.md` at their numbered `##` headings into sections. Search matches a section when it contains the words of the query, ranks by how many words match with the title counting most, and returns up to 5 as document, section number and title.
- `search_documents`, `read_section` and `list_reads`, and a `reads` table (claim, document, section, time). Reading a section twice records it once.
- `get_policy_wording` and its test are removed, because nothing would use it.

Success criteria:

- [ ] `GET /api/documents/search?query=wild animal` returns the manual's section 7, Interpretation notes, first
- [ ] `query=third claim 12 months` returns the manual's section 9, Repeat claims, first, and `query=meals receipts` includes the manual's section 10 and the wording's section 3, Trip Delay
- [ ] A search with no match returns an empty list, and no search returns more than 5 sections
- [ ] `POST /api/claims/CLM-1001/reads` with the wording and section 3 returns the text of section 3, starting with its heading. `GET /api/claims/CLM-1001/reads` then lists it with its title and time, and still lists it once after a second read
- [ ] An unknown claim or section returns 404, and an unknown document returns 422
- [ ] A test confirms that only the two document files are opened, never anything under `data/evals/` or `data/security/`
- [ ] `GET /api/policy-wording` returns 404, and every operation still has an `operation_id` and a one-line docstring
- [ ] `npm run check:python` passes with coverage at 80% or more

## Phase 3: The claim agent as a fresh helper

Turns the pilot's agent into the helper that works one claim from a clean start, looks up what it needs, and always ends cleanly.

- `agent/main.py`:
  - Tools: the pilot's, without `get_policy_wording`, plus `search_documents(query)` and `read_section(claim_id, document, section)`.
  - Middleware on the claim agent: model retries, tool retries and a model call limit, with the retry delays as constants that tests set to 0. A `recursion_limit` set from the call limit.
  - `run(claim_id, thread_id)` catches a failure of the run once, records it as a step ("The run failed: ..."), pays an approved payout of $1,000 or less if the run died before paying, calls `finish_run`, and returns one line, such as "CLM-1001: approved, payout $420.00, paid." or "CLM-1002: failed (TimeoutError). Back in the queue, try 1 of 2."
  - The default model is `deepseek/deepseek-v4.1-flash` at low effort, and `MODEL_NAME` still overrides it.
- `backend/instructions.md`: rewritten for the claim agent from the wording and the manual. It follows the manual's working order. It tells the agent to search for the benefit's section of the wording and the manual's notes, and to read what it needs instead of everything, and it says when to refer to the Special Investigations Unit, when to refer for a missing document, and how to treat meals without receipts. It tells the agent to finish with one short sentence.

Success criteria:

- [ ] A test with a stub model works CLM-1001: it reads the claim, the policy and the history, searches, reads the wording's section 3 and the manual's section 10, approves $375.00 and pays it. The claim is `decided` and paid, `list_reads` shows both sections, the steps show every call in order, and `run` returns "CLM-1001: approved, payout $375.00, paid."
- [ ] A stub that approves $1,950.00 and then calls `pay_claim` sees the 403 message as the result. The claim stays `awaiting_signoff` with no payment, and the line says it is waiting for sign-off
- [ ] A stub that never decides leaves the claim `waiting` with `failures` 1 and a final step saying the run ended without a decision
- [ ] A stub model that raises a timeout does not make `run` raise. The claim is `waiting` with a step "The run failed: ...", and the line says what went wrong
- [ ] A stub model that fails once and then works is retried, and the claim is decided. A backend call that fails once is retried too
- [ ] A claim whose run fails twice, in two runs, ends `left_for_handler`, and the second line says so
- [ ] A stub that approves $375.00 and then fails before paying leaves the claim paid $375.00 once, and paying again returns 409. One that approves $1,950.00 and then fails leaves it `awaiting_signoff` with no payment
- [ ] A stub that never stops calling tools is stopped by the model call limit, the claim goes back in the queue, and the failure is recorded
- [ ] `run_agent` from the backend still works: the claim ends decided, and a second call returns 409
- [ ] A test confirms the default model name and low effort, and that `MODEL_NAME` overrides it
- [ ] The test that no file in `agent/` imports `backend` or refers to `data/` still passes
- [ ] `npm run check:python` passes with coverage at 80% or more

## Phase 4: The queue agent

Builds the agent that works the whole queue, with the cap, the to-do list, the fresh helpers and the check for missed claims.

- `agent/queue_run.py`:
  - Tools: `list_waiting_claims` (id, type, summary, amount claimed, submitted date and failures; no story), `write_todos(todos)` and `work_claim(claim_id)`, built for each run so they share its run id, its cap and the set of claims worked so far.
  - `work_claim` takes a lock, refuses a claim that isn't waiting or that is beyond the cap, and otherwise runs `main.run` on it with a new thread. Each helper is a new agent with only the claim instructions and the claim id.
  - The middleware for missed claims, the model call limit, and a `recursion_limit`.
  - `run_queue(run_id, limit)`: starts the run, runs the agent, and finishes the run with its final reply as the summary. If the queue agent itself fails, it finishes with "The run stopped: ...".
- `backend/main.py`: `run_queue`, which starts `run_queue` in a background task.
- `backend/instructions/queue.md` and `claim.md` (the Phase 3 text moves into `claim.md`), and `get_instructions` returns both. The queue part tells the agent to list the waiting claims, to write a to-do list of at most `limit` claims, oldest first with a claim that has failed before last, to mark a claim in progress before working it and to update the list after each one-line report, to work one claim at a time, to try a failed claim that is back in the queue once more, and to finish with a short summary for the handlers.
- `agent/__main__.py`: `uv run -m agent` works the whole queue in one run, `uv run -m agent --limit 5` caps the run at five claims, and `uv run -m agent CLM-1001` works one named claim.

Success criteria:

- [ ] A test with stub models runs a queue of limit 3. The queue agent writes a three-claim to-do list, works three claims, and updates the list. Afterwards `get_latest_queue_run` is `finished` with three items done and the summary, each claim has its own steps, and the other 22 claims are still `waiting`
- [ ] The queue agent's prompt is the queue part of `GET /api/instructions`. Each helper's prompt is the claim part, and its only message is for its own claim
- [ ] A fourth `work_claim` in a run capped at 3 is refused, and that claim stays `waiting`. With a cap of 1, two `work_claim` calls in one model turn work one claim and refuse the other
- [ ] When one helper fails, the run goes on to the next claim, and the failed claim is `waiting` with `failures` 1. The queue agent tries it again. If it fails again the claim is `left_for_handler`, its to-do item says so, and the run still finishes
- [ ] A queue agent that tries to finish after working 2 of 3 claims is sent back, and works a third. One that finishes with the cap reached is not sent back for the claims it never worked. One that ignores the nudge twice ends the run, and the summary names the claims still waiting
- [ ] A stub queue agent that loops is stopped by the call limit. The run is `finished` with a summary that says it stopped, and no claim is left `in_progress`
- [ ] `POST /api/runs` with a stub model returns a run, and the run ends finished
- [ ] The command line works: `--limit 2` starts a run with limit 2, and a claim id works that claim, tested with stubs
- [ ] `npm run check:python` passes with coverage at 80% or more

## Phase 5: The dashboard

Shows the plan, the run controls, what the agent read, and the new status.

- `dashboard/src/api.ts`: `left_for_handler`, the run, to-do and read types, `getLatestRun`, `runQueue(limit)` and `listReads(id)`, and the new shape of the instructions.
- The queue page: a fifth count tile, "Left for a handler". Above the table, a panel with the current run: its status, the cap, the to-do list with each claim's link, summary and status chip, and the summary once it ends. A "Run the queue" form with a number field for the cap. Blank sends the number of waiting claims. The button is disabled while a run is running. The page polls every 2 seconds while a run is running or a claim is in progress.
- The claim page: a "What the agent read" panel listing each section as "Policy wording, section 3, Trip Delay". A note on a claim left for a handler: "The agent couldn't decide this claim after two tries. A handler needs to decide it."
- The instructions page: the queue instructions, then the claim instructions, read only.

Success criteria:

- [ ] Vitest tests with a stubbed `fetch` cover the plan panel in each state (no run, running, finished), the status chips, the run form (a cap of 5 posts `limit` 5, blank posts the waiting count, disabled while running), the polling, the reads panel, the note on a claim left for a handler and the instructions page
- [ ] In the browser, checked with the Playwright MCP server on a reseeded database, the queue shows five count tiles. After a run and a to-do list are created with API calls, with no model, the plan panel shows the items with their chips, and updating an item through the API changes its chip within 2 seconds without reloading
- [ ] A claim with two reads recorded through the API shows both on its page, and a claim failed twice through the API shows "Left for a handler" in Raspberry and the note
- [ ] `#/instructions` shows both parts with nothing to edit
- [ ] `npm run check:ts` passes with coverage at 80% or more

## Phase 6: End-to-end tests, a live trial and handover

Proves the whole product works together, runs the real model once on a small trial, and brings the documents up to date.

- `e2e/`: the existing tests updated for the new tile and the new instructions page, plus a test that uses the API, with no model, to start a run, write a to-do list, record reads and steps and a decision, and checks the plan, the ticks, the reads and the steps in the browser. A second test fails a claim twice through the API and checks "Left for a handler".
- The live trial, as `docs/HARNESS.md` asks: reseed first, and cap the run at five claims.
- `docs/SPEC.md`: the claims manual comes out of "Not for now" and into what the agent works from, decisions follow the wording and the manual, and the spec describes the run of the queue, the to-do list, what the agent read and "Left for a handler". `docs/TECH_STACK.md`: the agent's two entry points, the middleware, the new default model. `docs/STATUS.md`: what is built, how to run it, how to cap a run and how to reseed.

Success criteria:

- [ ] `npm run e2e` passes, and the dev database is unchanged afterwards
- [ ] Reseeded, with `npm run dev`, a run capped at 5 from the dashboard on the default model works five claims on its own, checked with the Playwright MCP server. The plan fills in and its items are ticked off as the claims finish. Each of the five claims shows its steps and the sections it read. The other 20 stay Waiting. The summary appears when the run ends. A payout over $1,000 waits for sign-off. This costs a few cents
- [ ] The live request used low reasoning effort, or the `extra_body` fallback is in place
- [ ] `uv run -m agent CLM-1001` on one named claim still decides it with the real model
- [ ] `docs/SPEC.md`, `docs/TECH_STACK.md` and `docs/STATUS.md` describe the product as it now is
- [ ] `npm run check` passes in full

## Not in this plan

- Scoring the agent against `data/evals/`. It stays closed until the team asks.
- Sending a claim left for a handler back to the agent, or a handler deciding it from the dashboard. The claim stays as it is until the database is reseeded.
- Recovering a run that a backend restart cut off. Reseed instead.
- Running several claim agents at once. That is the swarm, a later build.
- Showing the queue agent's own tool calls. The to-do list and the summary show what it means to do and has done. Each claim shows the helper's steps.
- Defenses against hidden instructions in a claim's story, durable state and the rest of the later builds.
