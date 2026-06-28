import { test, expect } from "./helpers";

test("theme toggle flips and persists across reload", async ({ page }) => {
  await page.goto("/");
  const isDark = () => page.evaluate(() => document.documentElement.classList.contains("dark"));
  const before = await isDark();

  await page.getByRole("button", { name: "Toggle theme" }).first().click();
  await expect.poll(isDark).toBe(!before);

  await page.reload();
  await expect.poll(isDark).toBe(!before);
});

test("health endpoint reports the app version", async ({ page }) => {
  const res = await page.request.get("/api/v1/health");
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  expect(body.status).toBe("ok");
  expect(body.version).toMatch(/^\d+\.\d+/);
});

test("core routes load without uncaught errors", async ({ page }) => {
  const crashes: string[] = [];
  page.on("pageerror", (e) => crashes.push(e.message));

  for (const route of ["/", "/organize", "/profiles", "/printers", "/statistics", "/settings"]) {
    await page.goto(route);
    await page.waitForLoadState("networkidle");
  }
  expect(crashes).toEqual([]);
});
