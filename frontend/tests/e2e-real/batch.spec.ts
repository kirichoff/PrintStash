import { test, expect } from "./helpers";
import { modelCard, uploadModel } from "./util";

// Batch move/tag/delete (new in 0.8.0). Models live in their own collection so
// "Select all on screen" is scoped to just them — the shared serial DB is never
// at risk of a batch op hitting another test's models.

test("batch-tag and batch-delete two models from the toolbar", async ({ page }) => {
  const stamp = Date.now();
  const col = `e2e-batch-${stamp}`;
  const tag = `batch-tag-${stamp}`;
  const m1 = `e2e-batch-a-${stamp}`;
  const m2 = `e2e-batch-b-${stamp}`;

  await page.goto("/organize");
  await page.getByPlaceholder("New collection...").fill(col);
  await page.getByPlaceholder("New collection...").press("Enter");
  await expect(page.getByRole("button", { name: `Delete ${col}` })).toBeVisible();
  await uploadModel(page, m1, { collection: col });
  await uploadModel(page, m2, { collection: col });

  await page.goto(`/?c=${col}`);
  await expect(modelCard(page, m1)).toBeVisible();
  await expect(modelCard(page, m2)).toBeVisible();

  // Enter select mode, select both (scoped to this collection), open the toolbar.
  await page.getByRole("button", { name: "Select", exact: true }).click();
  await page.getByRole("button", { name: /Select all on screen \(2\)/ }).click();
  // Both the grid header and the floating toolbar say "2 selected" — either proves it.
  await expect(page.getByText("2 selected").first()).toBeVisible();

  // Batch tag → the chip shows up on the cards.
  await page.getByRole("button", { name: "Tag" }).click();
  const tagInput = page.getByPlaceholder("Search or create — press Enter");
  await tagInput.fill(tag);
  await tagInput.press("Enter");
  await page.getByRole("button", { name: "Apply" }).click();

  await page.goto(`/?c=${col}`);
  await expect(modelCard(page, m1).getByText(tag, { exact: false })).toBeVisible();

  // Batch delete → both move to trash, collection empties.
  await page.getByRole("button", { name: "Select", exact: true }).click();
  await page.getByRole("button", { name: /Select all on screen \(2\)/ }).click();
  // Scope to the floating toolbar — "Delete" otherwise also matches the sidebar's
  // "Delete collection" button (substring match).
  await page.locator("div.fixed.bottom-4").getByRole("button", { name: "Delete" }).click();
  // The toolbar's button and the confirm modal both say "Delete" — scope to the modal.
  await page.getByRole("dialog").getByRole("button", { name: "Delete", exact: true }).click();
  await expect(modelCard(page, m1)).toHaveCount(0);
  await expect(modelCard(page, m2)).toHaveCount(0);

  // Cleanup: purge both from the trash so the shared DB doesn't accumulate. The
  // e2e backend is wiped per run, so the only exact-"Delete" buttons here are the
  // two trash rows. Purge sequentially, waiting for the row count to drop each
  // time (robust against ordering and the busy-disable between clicks).
  await page.goto("/settings");
  await page.getByRole("button", { name: "Trash" }).click();
  const purgeButtons = page.getByRole("button", { name: "Delete", exact: true });
  await expect(purgeButtons).toHaveCount(2);
  await purgeButtons.first().click();
  await page.getByRole("button", { name: "Delete forever" }).click();
  await expect(purgeButtons).toHaveCount(1);
  await purgeButtons.first().click();
  await page.getByRole("button", { name: "Delete forever" }).click();
  await expect(purgeButtons).toHaveCount(0);
});
