import { test, expect } from "./helpers";
import { modelCard, uploadModel } from "./util";

test("delete an assigned tag from model editing (with confirm)", async ({ page }) => {
  const tag = `e2e-assigned-${Date.now()}`;
  const model = `e2e-tagged-${Date.now()}`;

  await uploadModel(page, model, { tag });
  await modelCard(page, model).click();
  await page.getByRole("button", { name: "Edit", exact: true }).click();
  await page.getByRole("button", { name: `Remove ${tag}` }).click();
  await page.getByPlaceholder("Search or create — press Enter").fill(tag);
  const del = page.getByRole("button", { name: `Delete tag ${tag}` });
  await expect(del).toBeVisible();

  await del.click();
  await page.getByRole("dialog").getByRole("button", { name: "Delete" }).click();
  await expect(del).toHaveCount(0);
});
