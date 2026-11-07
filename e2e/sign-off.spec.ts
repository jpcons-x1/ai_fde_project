import { expect, test, type APIRequestContext } from "@playwright/test";

const claim = "/api/claims/CLM-1011";

// Plays the agent's part through the API, so no model is called.
async function approveOverTheLimit(request: APIRequestContext) {
  const thread = { thread_id: "e2e" };
  expect((await request.post(`${claim}/start`, { data: thread })).ok()).toBe(
    true,
  );
  for (const [kind, text] of [
    ["tool_call", 'get_claim({"claim_id": "CLM-1011"})'],
    ["message", "Approved, waiting for a handler's sign-off."],
  ]) {
    await request.post(`${claim}/steps`, { data: { ...thread, kind, text } });
  }
  const decision = await request.post(`${claim}/decision`, {
    data: {
      decision: "approve",
      payout: 1950,
      reason:
        "The suitcase was lost by the airline. The payout follows section 10.",
      policy_section: "Section 5, Baggage and Personal Effects",
    },
  });
  expect(decision.ok()).toBe(true);
  expect((await request.post(`${claim}/finish`)).ok()).toBe(true);
}

test("a payout over $1,000 waits for a handler to sign off", async ({
  page,
  request,
}) => {
  await approveOverTheLimit(request);

  const payment = await request.post(`${claim}/payment`, {
    data: { amount: 1950 },
  });
  expect(payment.status()).toBe(403);
  expect(await payment.json()).toEqual({
    detail: "A payout over $1,000.00 needs a handler's sign-off",
  });

  await page.goto("/#/claims/CLM-1011");
  const decision = page.getByRole("region", { name: "Decision" });
  await expect(
    page.locator(".title").getByText("Waiting for sign-off"),
  ).toBeVisible();
  await expect(decision.getByText("$1,950.00")).toBeVisible();
  await expect(
    page.getByText("Approved, waiting for a handler's sign-off."),
  ).toBeVisible();

  await page.getByLabel("Handler").selectOption("HND-01");
  await page.getByRole("button", { name: "Sign off and pay" }).click();

  await expect(page.locator(".title").getByText("Decided")).toBeVisible();
  await expect(
    decision.getByText("Dana Whitfield", { exact: false }),
  ).toBeVisible();
  await expect(decision.getByText(/^\$1,950\.00, /)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Sign off and pay" }),
  ).toHaveCount(0);
});
