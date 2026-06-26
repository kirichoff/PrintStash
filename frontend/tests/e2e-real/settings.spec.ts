import { test, expect } from "./helpers";

test("create and revoke an API key", async ({ page }) => {
  const keyName = `e2e-key-${Date.now()}`;
  await page.goto("/settings");
  await page.getByRole("button", { name: "Users & Access" }).click();

  // The key-name field is the input next to the Generate button (pre-filled).
  const keyField = page.getByRole("button", { name: "Generate" }).locator("xpath=../input");
  await keyField.fill(keyName);
  await page.getByRole("button", { name: "Generate" }).click();

  // One-time secret is shown, and the key appears in the active list.
  await expect(page.getByText("It will only be shown once.")).toBeVisible();
  await expect(page.getByText(keyName)).toBeVisible();

  // Revoke it.
  await page.getByTitle("Revoke API key").click();
  await expect(page.getByText(keyName)).toHaveCount(0);
});

test("change display currency persists", async ({ page }) => {
  await page.goto("/settings");
  await page.getByRole("button", { name: "Design" }).click();

  const currency = page
    .getByRole("combobox")
    .filter({ has: page.getByRole("option", { name: "EUR — Euro (€)" }) });

  await Promise.all([
    page.waitForResponse(
      (r) => r.url().includes("/api/v1/config") && r.request().method() === "PUT",
    ),
    currency.selectOption("EUR"),
  ]);

  await page.reload();
  await page.getByRole("button", { name: "Design" }).click();
  await expect(
    page
      .getByRole("combobox")
      .filter({ has: page.getByRole("option", { name: "EUR — Euro (€)" }) }),
  ).toHaveValue("EUR");

  // Restore default so the shared DB doesn't drift for later runs.
  await page
    .getByRole("combobox")
    .filter({ has: page.getByRole("option", { name: "USD — US Dollar ($)" }) })
    .selectOption("USD");
});

test("export library metadata as JSON", async ({ page }) => {
  await page.goto("/settings"); // Overview is the default section.
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: /^JSON$/ }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/\.json$/);
});

test("create a manual backup", async ({ page }) => {
  await page.goto("/settings");
  await page.getByRole("button", { name: "Storage" }).click();

  await Promise.all([
    page.waitForResponse(
      (r) => r.url().endsWith("/api/v1/backups") && r.request().method() === "POST",
    ),
    page.getByRole("button", { name: "Backup now" }).click(),
  ]);

  // The new backup shows up in the Restore-backup list with a Download action.
  await expect(page.getByRole("button", { name: "Download" }).first()).toBeVisible();
});
