import { act, cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { stubApi, summary } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.location.hash = "";
});

const queue = [
  summary(),
  summary({
    claim_id: "CLM-1011",
    customer_name: "Tom Okafor",
    claim_type: "baggage",
    amount_claimed: 1950,
    status: "awaiting_signoff",
    decision: "approve",
    payout: 1950,
  }),
  summary({
    claim_id: "CLM-1012",
    status: "decided",
    decision: "decline",
    payout: 0,
  }),
];

describe("the header", () => {
  it("shows that the backend is up", async () => {
    stubApi({ "GET /api/health": { status: "ok" }, "GET /api/claims": [] });
    render(<App />);
    expect(await screen.findByText("Backend: up")).toBeDefined();
  });

  it("shows that the backend is down", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    render(<App />);
    expect(await screen.findByText("Backend: down")).toBeDefined();
    expect(await screen.findByText("Error: offline")).toBeDefined();
  });
});

describe("the queue", () => {
  it("lists the claims with their status, decision and amounts", async () => {
    stubApi({ "GET /api/claims": queue });
    render(<App />);
    const row = (await screen.findByText("Tom Okafor")).closest("tr");
    if (!row) throw new Error("no row");
    const cells = within(row);
    expect(cells.getByText("Baggage")).toBeDefined();
    expect(cells.getAllByText("$1,950.00")).toHaveLength(2);
    expect(cells.getByText("Waiting for sign-off")).toBeDefined();
    expect(cells.getByText("Approved")).toBeDefined();
    expect(cells.getByText("CLM-1011").getAttribute("href")).toBe(
      "#/claims/CLM-1011",
    );
    expect(cells.getByText("Jun 24, 2026")).toBeDefined();
  });

  it("counts the claims in each status", async () => {
    stubApi({ "GET /api/claims": queue });
    render(<App />);
    expect((await screen.findByTestId("count-waiting")).textContent).toBe("1");
    expect(screen.getByTestId("count-in_progress").textContent).toBe("0");
    expect(screen.getByTestId("count-awaiting_signoff").textContent).toBe("1");
    expect(screen.getByTestId("count-decided").textContent).toBe("1");
  });

  it("refreshes while a claim is in progress", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const calls = stubApi({
      "GET /api/claims": [summary({ status: "in_progress" })],
    });
    render(<App />);
    await screen.findByText("Maya Patel");
    await act(() => vi.advanceTimersByTimeAsync(2000));
    expect(
      calls.filter((c) => c.path === "/api/claims").length,
    ).toBeGreaterThan(1);
    vi.useRealTimers();
  });
});

describe("routing", () => {
  it("opens a claim and the instructions from the address", async () => {
    stubApi({ "GET /api/claims": queue });
    render(<App />);
    await screen.findByText("Tom Okafor");

    act(() => {
      window.location.hash = "#/instructions";
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    expect(
      screen
        .getByRole("link", { name: "Agent instructions" })
        .getAttribute("aria-current"),
    ).toBe("page");

    act(() => {
      window.location.hash = "#/claims/CLM-1011";
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    expect(
      await screen.findByRole("heading", { name: /CLM-1011/ }),
    ).toBeDefined();
  });
});
