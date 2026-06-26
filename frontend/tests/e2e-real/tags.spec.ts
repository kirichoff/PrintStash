import { test, expect } from "./helpers";

test("create and delete a tag", async ({ page }) => {
  const tag = `e2e-tag-${Date.now()}`;

  await page.goto("/organize");
  await expect(page.getByRole("heading", { name: "Tags" }).first()).toBeVisible();

  const input = page.getByPlaceholder("New tag...");
  await input.fill(tag);
  await input.press("Enter");

  // Tags are uppercased in the chip; match the delete control instead (stable).
  const del = page.getByRole("button", { name: `Delete tag ${tag}` });
  await expect(del).toBeVisible();

  // Persisted across reload.
  await page.reload();
  await expect(page.getByRole("button", { name: `Delete tag ${tag}` })).toBeVisible();

  // A fresh tag has 0 models, so delete needs no window.confirm.
  await page.getByRole("button", { name: `Delete tag ${tag}` }).click();
  await expect(page.getByRole("button", { name: `Delete tag ${tag}` })).toHaveCount(0);
});
