import { test, expect } from "./helpers";

test("model metadata visibility toggle persists across reload", async ({ page }) => {
  await page.goto("/settings");
  await page.getByRole("button", { name: "Design" }).click();

  const chip = page.getByRole("button", { name: "Supports", exact: true });
  await expect(chip).toBeVisible();
  const before = await chip.getAttribute("aria-pressed");
  await chip.click();
  const after = await chip.getAttribute("aria-pressed");
  expect(after).not.toBe(before);

  await page.reload();
  await page.getByRole("button", { name: "Design" }).click();
  await expect(page.getByRole("button", { name: "Supports", exact: true })).toHaveAttribute(
    "aria-pressed",
    after!,
  );
});

