import { expect, test } from "@playwright/test";

test("the queue shows every claim", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Backend: up")).toBeVisible();
  await expect(page.locator("tbody tr")).toHaveCount(25);
  await expect(page.getByTestId("count-waiting")).toHaveText(/\d+/);
  await expect(page.getByRole("link", { name: "CLM-1001" })).toBeVisible();
});

test("a claim's page shows the claim, its policy and its customer", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("link", { name: "CLM-1001" }).click();
  await expect(page).toHaveURL(/#\/claims\/CLM-1001$/);
  await expect(page.getByText(/My flight home from Rome/)).toBeVisible();
  await expect(
    page.getByText("Meridian Air cancellation notice"),
  ).toBeVisible();
  await expect(page.getByText("UnderCover Premium")).toBeVisible();
  await expect(page.getByText("CLM-0412")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Run the agent" }),
  ).toBeVisible();
});

test("the instructions are read only", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Agent instructions" }).click();
  await expect(page.getByText(/^You are the UnderCover Agent\./)).toBeVisible();
  await expect(page.getByRole("textbox")).toHaveCount(0);
  await expect(page.getByRole("main").getByRole("button")).toHaveCount(0);
});
