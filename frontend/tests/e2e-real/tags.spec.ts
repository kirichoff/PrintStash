import { test, expect } from "./helpers";
import { uploadModel } from "./util";

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

test("delete a tag that is assigned to a model (with confirm)", async ({ page }) => {
  const tag = `e2e-assigned-${Date.now()}`;
  const model = `e2e-tagged-${Date.now()}`;

  // Inline-create the tag during upload, which also assigns it to the model.
  await uploadModel(page, model, { tag });

  await page.goto("/organize");
  const del = page.getByRole("button", { name: `Delete tag ${tag}` });
  await expect(del).toBeVisible();

  // model_count > 0 triggers a window.confirm before deletion.
  page.once("dialog", (d) => d.accept());
  await del.click();
  await expect(page.getByRole("button", { name: `Delete tag ${tag}` })).toHaveCount(0);
});
