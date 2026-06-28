import { test, expect } from "./helpers";
import { uploadModel } from "./util";

// Real CRUD against the backend DB.

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

  // The parent deletes cleanly even though it once had a (now soft-deleted)
  // child — regression guard for the has-children check ignoring trashed rows.
  await page.getByRole("button", { name: `Delete ${parent}` }).click();
  await expect(page.getByRole("button", { name: `Delete ${parent}` })).toHaveCount(0);
});

// The /organize page refuses to delete a non-empty collection; the sidebar
// outliner on / does it recursively, moving the contained models to the trash.
test("recursive-delete a non-empty collection from the sidebar", async ({ page }) => {
  const stamp = Date.now();
  const col = `e2e-recur-${stamp}`;
  const model = `e2e-recur-model-${stamp}`;

  await page.goto("/organize");
  await page.getByPlaceholder("New collection...").fill(col);
  await page.getByPlaceholder("New collection...").press("Enter");
  await expect(page.getByRole("button", { name: `Delete ${col}` })).toBeVisible();
  await uploadModel(page, model, { collection: col });

  // Sidebar outliner: hover the collection row, hit its delete, confirm.
  await page.goto("/");
  const sidebar = page.locator("aside");
  const label = sidebar.getByRole("button", { name: col, exact: true });
  await expect(label).toBeVisible();
  await label.hover();
  await label.locator("xpath=following-sibling::button[@title='Delete collection']").click();
  await sidebar.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(sidebar.getByRole("button", { name: col, exact: true })).toHaveCount(0);

  // The contained model landed in the trash (recycle bin), not hard-deleted.
  await page.goto("/settings");
  await page.getByRole("button", { name: "Trash" }).click();
  await expect(page.getByText(model)).toBeVisible();

  // Clean up: purge it forever so the shared DB doesn't accumulate trash.
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await page.getByRole("button", { name: "Delete forever" }).click();
  await expect(page.getByText(model)).toHaveCount(0);
});
