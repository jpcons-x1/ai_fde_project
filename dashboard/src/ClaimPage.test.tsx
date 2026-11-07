import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Claim, Step } from "./api";
import { ClaimPage } from "./ClaimPage";
import { Instructions } from "./Instructions";
import { claim, stubApi } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const policy = {
  policy_id: "POL-2001",
  plan: { plan: "premium", name: "UnderCover Premium" },
  add_ons: [],
  purchased_on: "2026-04-22",
  trip: {
    destination: "Rome, Italy",
    departs_on: "2026-06-10",
    returns_on: "2026-06-18",
    trip_cost: 3100,
  },
  travelers: ["Maya Patel"],
};

const customer = {
  customer_id: "CUS-3001",
  name: "Maya Patel",
  customer_since: "2023-04-11",
  previous_claims: [
    {
      claim_id: "CLM-0412",
      filed_on: "2024-08-19",
      claim_type: "baggage_delay",
      summary: "Checked bag arrived 30 hours late in Lisbon",
      outcome: "approved",
      amount_paid: 140,
    },
  ],
};

const handlers = [
  {
    handler_id: "HND-01",
    name: "Dana Whitfield",
    role: "Senior Claims Handler",
    can_approve_over_limit: true,
  },
  {
    handler_id: "HND-04",
    name: "Sam Trainee",
    role: "Trainee",
    can_approve_over_limit: false,
  },
];

const steps: Step[] = [
  {
    number: 1,
    thread_id: "t-1",
    kind: "tool_call",
    text: 'get_claim({"claim_id": "CLM-1001"})',
    created_at: "2026-11-07T10:00:00+00:00",
  },
  {
    number: 2,
    thread_id: "t-1",
    kind: "message",
    text: "Approved and paid.",
    created_at: "2026-11-07T10:00:05+00:00",
  },
];

const decision = {
  decision: "approve" as const,
  payout: 1950,
  reason: "The bag was lost by the carrier. The payout follows section 10.",
  policy_section: "Section 5, Baggage and Personal Effects",
  decided_at: "2026-11-07T10:00:04+00:00",
};

function show(theClaim: Claim, extra: Record<string, unknown> = {}) {
  const calls = stubApi({
    "GET /api/claims/CLM-1001": theClaim,
    "GET /api/claims/CLM-1001/steps": [],
    "GET /api/policies/POL-2001": policy,
    "GET /api/customers/CUS-3001": customer,
    "GET /api/handlers": handlers,
    ...extra,
  });
  render(<ClaimPage claimId="CLM-1001" />);
  return calls;
}

describe("the claim page", () => {
  it("shows the claim, the policy and the customer", async () => {
    show(claim());
    expect(await screen.findByText(/My flight home from Rome/)).toBeDefined();
    expect(screen.getByText("Airport hotel")).toBeDefined();
    expect(screen.getByText("Hotel receipt")).toBeDefined();
    expect(screen.getByText("Jun 18, 2026, Rome, Italy")).toBeDefined();
    expect(await screen.findByText("UnderCover Premium")).toBeDefined();
    expect(screen.getByText("None")).toBeDefined();
    expect(await screen.findByText("CLM-0412")).toBeDefined();
    expect(screen.getByText("No decision yet.")).toBeDefined();
    expect(
      screen.getByText("The agent hasn't worked on this claim yet."),
    ).toBeDefined();
  });

  it("shows an error for an unknown claim", async () => {
    stubApi({});
    render(<ClaimPage claimId="CLM-9999" />);
    expect(await screen.findByText(/failed: 404/)).toBeDefined();
  });

  it("shows a decision that was paid", async () => {
    show(
      claim({
        status: "decided",
        decision: { ...decision, payout: 420 },
        payment: { amount: 420, paid_at: "2026-11-07T10:00:06+00:00" },
      }),
      { "GET /api/claims/CLM-1001/steps": steps },
    );
    expect(await screen.findByText("Approved")).toBeDefined();
    expect(screen.getByText(decision.reason)).toBeDefined();
    expect(screen.getByText(decision.policy_section)).toBeDefined();
    expect(screen.getByText("Paid")).toBeDefined();
    expect(await screen.findByText("Approved and paid.")).toBeDefined();
    expect(screen.getByText("Tool call")).toBeDefined();
    expect(screen.queryByText("Run the agent")).toBeNull();
  });

  it("runs the agent on a waiting claim", async () => {
    const calls = show(claim(), {
      "POST /api/claims/CLM-1001/run": { thread_id: "t-1" },
    });
    fireEvent.click(await screen.findByText("Run the agent"));
    await vi.waitFor(() => {
      expect(
        calls.filter((c) => c.path === "/api/claims/CLM-1001").length,
      ).toBe(2);
    });
    expect(calls.some((c) => c.method === "POST")).toBe(true);
  });

  it("shows why the agent could not start", async () => {
    show(claim());
    fireEvent.click(await screen.findByText("Run the agent"));
    expect(await screen.findByText(/failed: 404/)).toBeDefined();
  });

  it("polls while the agent is running and stops when it ends", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const calls = show(claim({ status: "in_progress", agent_running: true }));
    expect(
      await screen.findByText("The agent is working on this claim."),
    ).toBeDefined();
    const claimCalls = () =>
      calls.filter((c) => c.path === "/api/claims/CLM-1001").length;

    await act(() => vi.advanceTimersByTimeAsync(2000));
    expect(claimCalls()).toBe(2);

    stubApi({
      "GET /api/claims/CLM-1001": claim({ status: "decided", decision }),
      "GET /api/claims/CLM-1001/steps": steps,
    });
    await act(() => vi.advanceTimersByTimeAsync(2000));
    expect(await screen.findByText("Approved and paid.")).toBeDefined();
    const fetches = vi.mocked(fetch).mock.calls.length;
    await act(() => vi.advanceTimersByTimeAsync(6000));
    expect(vi.mocked(fetch).mock.calls.length).toBe(fetches);
  });
});

describe("sign-off", () => {
  const waiting = claim({ status: "awaiting_signoff", decision });

  it("offers only handlers who can sign off", async () => {
    show(waiting);
    expect(
      await screen.findByText(/Waiting for sign-off\. A payout/),
    ).toBeDefined();
    expect(
      await screen.findByRole("option", { name: "Dana Whitfield" }),
    ).toBeDefined();
    expect(screen.queryByRole("option", { name: "Sam Trainee" })).toBeNull();
    const button = screen.getByRole<HTMLButtonElement>("button", {
      name: "Sign off and pay",
    });
    expect(button.disabled).toBe(true);
  });

  it("signs off and shows the payment", async () => {
    const signedOff = claim({
      status: "decided",
      decision,
      payment: { amount: 1950, paid_at: "2026-11-07T11:00:00+00:00" },
      sign_off: {
        handler_id: "HND-01",
        handler_name: "Dana Whitfield",
        signed_at: "2026-11-07T11:00:00+00:00",
      },
    });
    const calls = show(waiting, {
      "POST /api/claims/CLM-1001/sign-off": signedOff,
    });
    await screen.findByRole("option", { name: "Dana Whitfield" });
    fireEvent.change(screen.getByLabelText("Handler"), {
      target: { value: "HND-01" },
    });
    stubApi({
      "GET /api/claims/CLM-1001": signedOff,
      "GET /api/claims/CLM-1001/steps": [],
      "POST /api/claims/CLM-1001/sign-off": signedOff,
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign off and pay" }));
    expect(await screen.findByText("Signed off by")).toBeDefined();
    expect(screen.getByText(/Dana Whitfield, /)).toBeDefined();
    expect(screen.queryByText("Sign off and pay")).toBeNull();
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });

  it("shows a refused sign-off", async () => {
    show(waiting);
    await screen.findByRole("option", { name: "Dana Whitfield" });
    fireEvent.change(screen.getByLabelText("Handler"), {
      target: { value: "HND-01" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign off and pay" }));
    expect(await screen.findByText(/sign-off failed: 404/)).toBeDefined();
  });
});

describe("the instructions page", () => {
  it("shows the instructions with nothing to edit", async () => {
    stubApi({
      "GET /api/instructions": { text: "You are the UnderCover Agent." },
    });
    render(<Instructions />);
    expect(
      await screen.findByText("You are the UnderCover Agent."),
    ).toBeDefined();
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("shows an error when the instructions can't load", async () => {
    stubApi({});
    render(<Instructions />);
    expect(await screen.findByText(/failed: 404/)).toBeDefined();
  });
});
