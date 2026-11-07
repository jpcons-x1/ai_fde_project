import { vi } from "vitest";
import type { Claim, ClaimSummary } from "./api";

type Responses = Record<string, unknown>;

/** Stubs fetch with a JSON response for each "METHOD /path", and records the calls. */
export function stubApi(responses: Responses) {
  const calls: { method: string; path: string; body: unknown }[] = [];
  const fetch = vi.fn((path: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    const body: unknown =
      typeof init?.body === "string" ? JSON.parse(init.body) : undefined;
    calls.push({ method, path, body });
    const key = `${method} ${path}`;
    if (!(key in responses))
      return Promise.resolve(new Response("{}", { status: 404 }));
    return Promise.resolve(new Response(JSON.stringify(responses[key])));
  });
  vi.stubGlobal("fetch", fetch);
  return calls;
}

export function summary(overrides: Partial<ClaimSummary> = {}): ClaimSummary {
  return {
    claim_id: "CLM-1001",
    customer_name: "Maya Patel",
    claim_type: "trip_delay",
    summary: "Flight home canceled",
    amount_claimed: 420,
    submitted_on: "2026-06-24",
    status: "waiting",
    decision: null,
    payout: null,
    ...overrides,
  };
}

export function claim(overrides: Partial<Claim> = {}): Claim {
  return {
    claim_id: "CLM-1001",
    policy_id: "POL-2001",
    customer_id: "CUS-3001",
    claim_type: "trip_delay",
    submitted_on: "2026-06-24",
    incident_date: "2026-06-18",
    incident_location: "Rome, Italy",
    summary: "Flight home canceled",
    story: "My flight home from Rome was canceled.",
    items: [
      { description: "Airport hotel", category: "accommodation", amount: 245 },
    ],
    amount_claimed: 245,
    documents: [
      {
        name: "Hotel receipt",
        type: "receipt",
        content: "One night, $245.00.",
      },
    ],
    status: "waiting",
    thread_id: null,
    agent_running: false,
    payout_approval_limit: 1000,
    decision: null,
    payment: null,
    sign_off: null,
    ...overrides,
  };
}
