import { test, expect, authBundleFor, authedContext } from "./helpers";
import { modelCard, uploadModel } from "./util";

const USER_PW = "userpass123";

// Grant `username` a role on collection `colName` via the share modal.
async function grant(
  page: import("@playwright/test").Page,
  colName: string,
  username: string,
  roleLabel: "View" | "Edit",
) {
  await page.goto("/organize");
  await page.getByRole("button", { name: `Share ${colName}` }).click();
  await expect(page.getByRole("heading", { name: "Collection access" })).toBeVisible();
  await page
    .getByRole("combobox")
    .filter({ has: page.getByRole("option", { name: "Select user" }) })
    .selectOption({ label: username });
  await page
    .getByRole("combobox")
    .filter({ has: page.getByRole("option", { name: "View", exact: true }) })
    .selectOption({ label: roleLabel });
  await Promise.all([
    page.waitForResponse(
      (r) => /\/collections\/\d+\/permissions\/\d+/.test(r.url()) && r.request().method() === "PUT",
    ),
    page.getByRole("button", { name: "Save" }).click(),
  ]);
  await page.getByRole("button", { name: "Close" }).click();
}

async function createUser(page: import("@playwright/test").Page, username: string) {
  await page.goto("/settings");
  await page.getByRole("button", { name: "Users & Access" }).click();
  await page.getByPlaceholder("Username").fill(username);
  await page.getByPlaceholder("Initial password").fill(USER_PW);
  await page.getByRole("button", { name: "Create" }).click();
  await expect(page.getByRole("paragraph").filter({ hasText: username })).toBeVisible();
}

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

// A view-role user can open a model but not edit it; an edit-role user can.
test("collection role gates whether a user can edit a model", async ({ page, browser }) => {
  const stamp = Date.now();
  const col = `rbac-edit-${stamp}`;
  const model = `rbac-model-${stamp}`;
  const viewer = `rbac-viewer-${stamp}`;
  const editor = `rbac-editor-${stamp}`;

  // Admin: collection + a model inside it; capture the model URL.
  await page.goto("/organize");
  await page.getByPlaceholder("New collection...").fill(col);
  await page.getByPlaceholder("New collection...").press("Enter");
  await expect(page.getByRole("button", { name: `Delete ${col}` })).toBeVisible();
  await uploadModel(page, model, { collection: col });
  await modelCard(page, model).click();
  await expect(page.getByRole("heading", { name: model })).toBeVisible();
  const modelUrl = page.url();

  // Two users, two roles on the same collection.
  await createUser(page, viewer);
  await createUser(page, editor);
  await grant(page, col, viewer, "View");
  await grant(page, col, editor, "Edit");

  // Viewer: Edit is present but disabled.
  const viewBundle = await authBundleFor(viewer, USER_PW);
  const v = await authedContext(browser, viewBundle);
  try {
    await v.page.goto(modelUrl);
    await expect(v.page.getByRole("heading", { name: model })).toBeVisible();
    await expect(v.page.getByRole("button", { name: "Edit", exact: true })).toBeDisabled();
  } finally {
    await v.context.close();
  }

  // Editor: can edit and save a rename.
  const editBundle = await authBundleFor(editor, USER_PW);
  const e = await authedContext(browser, editBundle);
  try {
    await e.page.goto(modelUrl);
    await e.page.getByRole("button", { name: "Edit", exact: true }).click();
    const renamed = `${model}-edited`;
    await e.page.getByPlaceholder("Model name").fill(renamed);
    await e.page.getByRole("button", { name: /^Save$/ }).click();
    await expect(e.page.getByRole("heading", { name: renamed })).toBeVisible();
  } finally {
    await e.context.close();
  }
});
