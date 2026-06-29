import { type Locator } from "@playwright/test";
import { test, expect } from "./helpers";

// Playwright has no getByDisplayValue, so find a preset row by scanning the
// live input values for the unique name we created.
async function inputByValue(scope: Locator, labelRe: RegExp, value: string): Promise<Locator> {
  const inputs = scope.getByLabel(labelRe);
  await expect
    .poll(async () => {
      const n = await inputs.count();
      for (let i = 0; i < n; i++) if ((await inputs.nth(i).inputValue()) === value) return true;
      return false;
    })
    .toBe(true);
  const n = await inputs.count();
  for (let i = 0; i < n; i++) {
    if ((await inputs.nth(i).inputValue()) === value) return inputs.nth(i);
  }
  throw new Error(`no input with value ${value}`);
}

function rowOf(input: Locator): Locator {
  return input.locator('xpath=ancestor::div[contains(@class,"group")][1]');
}

test("create, edit, and delete a filament preset", async ({ page }) => {
  const name = `e2e-pla-${Date.now()}`;
  await page.goto("/profiles");

  const section = page.locator("section", { hasText: "Filament presets" });
  await section.getByRole("button", { name: "Add preset" }).click();
  await section.getByPlaceholder("Preset name *").fill(name);
  await section.getByPlaceholder("Type (PLA…)").fill("PLA");
  await section.getByPlaceholder("$/kg").fill("25");
  await section.getByRole("button", { name: "Add", exact: true }).click();

  const nameInput = await inputByValue(section, /^Filament preset name/, name);
  await expect(nameInput).toBeVisible();

  // Edit cost; auto-saves on row blur (real PATCH).
  await rowOf(nameInput).getByLabel(/Filament cost per kg/).fill("42");
  await Promise.all([
    page.waitForResponse(
      (r) => /\/api\/v1\/filament-profiles\/\d+/.test(r.url()) && r.request().method() === "PATCH",
    ),
    section.getByRole("heading", { name: "Filament presets" }).click(), // blur the row
  ]);

  // Cost persisted.
  await page.reload();
  const reloaded = await inputByValue(section, /^Filament preset name/, name);
  await expect(rowOf(reloaded).getByLabel(/Filament cost per kg/)).toHaveValue("42");

  // Delete it.
  await rowOf(reloaded).getByTitle("Delete").click();
  await expect
    .poll(async () => {
      const inputs = section.getByLabel(/^Filament preset name/);
      const n = await inputs.count();
      for (let i = 0; i < n; i++) if ((await inputs.nth(i).inputValue()) === name) return true;
      return false;
    })
    .toBe(false);
});

test("create and delete a printer preset", async ({ page }) => {
  const name = `e2e-printer-${Date.now()}`;
  await page.goto("/profiles");

  const section = page.locator("section", { hasText: "Printer presets" });
  await section.getByRole("button", { name: "Add preset" }).click();
  await section.getByPlaceholder("Preset name *").fill(name);
  await section.getByPlaceholder("Printer model").fill("Voron 2.4");
  await section.getByRole("button", { name: "Add", exact: true }).click();

  const nameInput = await inputByValue(section, /^Printer preset name/, name);
  await expect(nameInput).toBeVisible();

  await page.reload();
  const reloaded = await inputByValue(section, /^Printer preset name/, name);
  await rowOf(reloaded).getByTitle("Delete").click();
  await expect
    .poll(async () => {
      const inputs = section.getByLabel(/^Printer preset name/);
      const n = await inputs.count();
      for (let i = 0; i < n; i++) if ((await inputs.nth(i).inputValue()) === name) return true;
      return false;
    })
    .toBe(false);
});
