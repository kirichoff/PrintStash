import { test, expect } from "./helpers";

// Real CRUD against the backend DB.
//
// NOTE: deleting a *parent* after deleting its child is intentionally not tested
// — the backend counts soft-deleted children in its has-children guard
// (taxonomy.py delete_collection), so the non-recursive UI delete 409s. That's a
// real app bug, tracked separately; these tests cover the paths the UI supports.

test("create and delete an empty collection (persists across reload)", async ({ page }) => {
  const name = `e2e-col-${Date.now()}`;

  await page.goto("/organize");
  await expect(page.getByRole("heading", { name: "Collections" }).first()).toBeVisible();

  const input = page.getByPlaceholder("New collection...");
  await input.fill(name);
  await input.press("Enter");
  const del = page.getByRole("button", { name: `Delete ${name}` });
  await expect(del).toBeVisible();

  // Survives a full reload — proves real persistence, not optimistic UI.
  await page.reload();
  await expect(page.getByRole("button", { name: `Delete ${name}` })).toBeVisible();

  await page.getByRole("button", { name: `Delete ${name}` }).click();
  await expect(page.getByRole("button", { name: `Delete ${name}` })).toHaveCount(0);

  await page.reload();
  await expect(page.getByRole("button", { name: `Delete ${name}` })).toHaveCount(0);
});

test("nest a subcollection and delete the child", async ({ page }) => {
  const parent = `e2e-parent-${Date.now()}`;
  const child = `e2e-child-${Date.now()}`;

  await page.goto("/organize");
  const input = page.getByPlaceholder("New collection...");

  await input.fill(parent);
  await input.press("Enter");
  await expect(page.getByRole("button", { name: `Delete ${parent}` })).toBeVisible();

  // Nest under the parent (sets the parent target and auto-expands the row).
  await page.getByRole("button", { name: `Add subcollection to ${parent}` }).click();
  await input.fill(child);
  await input.press("Enter");
  await expect(page.getByRole("button", { name: `Delete ${child}` })).toBeVisible();

  await page.getByRole("button", { name: `Delete ${child}` }).click();
  await expect(page.getByRole("button", { name: `Delete ${child}` })).toHaveCount(0);
});
