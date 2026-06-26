import { test, expect, authBundleFor, authedContext } from "./helpers";

const USER_PW = "userpass123";

// End-to-end RBAC: an admin creates two collections, a regular user, and grants
// that user access to ONLY one collection. The user must then see exactly that
// collection — never the other — proving backend collection scoping reaches the UI.
test("a non-admin user sees only collections granted to them", async ({ page, browser }) => {
  const stamp = Date.now();
  const granted = `rbac-granted-${stamp}`;
  const hidden = `rbac-hidden-${stamp}`;
  const username = `rbac-user-${stamp}`;

  // ── Admin: create two collections ───────────────────────────────────────────
  await page.goto("/organize");
  const newCol = page.getByPlaceholder("New collection...");
  for (const name of [granted, hidden]) {
    await newCol.fill(name);
    await newCol.press("Enter");
    await expect(page.getByRole("button", { name: `Delete ${name}` })).toBeVisible();
  }

  // ── Admin: create a regular user ────────────────────────────────────────────
  await page.goto("/settings");
  await page.getByRole("button", { name: "Users & Access" }).click();
  await page.getByPlaceholder("Username").fill(username);
  await page.getByPlaceholder("Initial password").fill(USER_PW);
  await page.getByRole("button", { name: "Create" }).click();
  await expect(page.getByRole("paragraph").filter({ hasText: username })).toBeVisible();

  // ── Admin: grant the user "view" on the granted collection only ─────────────
  await page.goto("/organize");
  await page.getByRole("button", { name: `Share ${granted}` }).click();
  await expect(page.getByRole("heading", { name: "Collection access" })).toBeVisible();
  await page
    .getByRole("combobox")
    .filter({ has: page.getByRole("option", { name: "Select user" }) })
    .selectOption({ label: username });
  await Promise.all([
    page.waitForResponse(
      (r) => /\/collections\/\d+\/permissions\/\d+/.test(r.url()) && r.request().method() === "PUT",
    ),
    page.getByRole("button", { name: "Save" }).click(),
  ]);
  await page.getByRole("button", { name: "Close" }).click();

  // ── User: open a separate browser and check visibility ──────────────────────
  const bundle = await authBundleFor(username, USER_PW);
  const { context, page: userPage } = await authedContext(browser, bundle);
  try {
    await userPage.goto("/organize");
    await expect(userPage.getByText(granted, { exact: true }).first()).toBeVisible();
    await expect(userPage.getByText(hidden, { exact: true })).toHaveCount(0);
  } finally {
    await context.close();
  }
});
