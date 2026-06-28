import { test, expect } from "./helpers";
import { modelCard, uploadGcodeModel } from "./util";

test("log a manual print against an ad-hoc printer; it shows in history", async ({ page }) => {
  const name = `e2e-hist-${Date.now()}`;
  const printerName = `E2E Rig ${Date.now()}`;
  await uploadGcodeModel(page, name);

  await modelCard(page, name).click();
  await expect(page.getByRole("heading", { name })).toBeVisible();
  await page.getByRole("button", { name: "History" }).click();
  await page.getByRole("button", { name: /Add Record/ }).click();

  // Free-text printer name path: pick "Other (not listed)…" and type a name.
  await page
    .locator("select")
    .filter({ has: page.getByRole("option", { name: /Other \(not listed\)/ }) })
    .selectOption("__adhoc__");
  await page.getByPlaceholder("e.g. Garage Prusa MK4").fill(printerName);

  // The G-code revision defaults to the model's only revision; result defaults
  // to Completed. Save and confirm the record renders.
  await page.getByRole("button", { name: /^Save$/ }).click();
  await expect(page.getByText(printerName)).toBeVisible();
});

test("download a G-code revision", async ({ page }) => {
  const name = `e2e-dl-${Date.now()}`;
  await uploadGcodeModel(page, name);

  await modelCard(page, name).click();
  await expect(page.getByRole("heading", { name })).toBeVisible();
  await page.getByRole("button", { name: "Revisions" }).click();

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByTitle("Download").first().click(),
  ]);
  expect(download.suggestedFilename()).toBe(`${name}.gcode`);
});
