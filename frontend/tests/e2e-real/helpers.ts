import { test as base, expect, request as pwRequest } from "@playwright/test";

// Talks straight to the real backend to seed the first admin (once) and mint a
// real JWT, then injects that token into the browser the same way the app does
// after login (localStorage). Order-independent: this runs in the test phase,
// after Playwright has confirmed both web servers are up.
const apiPort = Number(process.env.PLAYWRIGHT_REAL_API_PORT ?? 8410);
const API = `http://127.0.0.1:${apiPort}`;

export const ADMIN = { username: "admin", password: "admin1234" };

let cachedToken: string | null = null;
let cachedUser: string | null = null;

async function ensureAuth(): Promise<{ token: string; user: string }> {
  if (cachedToken && cachedUser) return { token: cachedToken, user: cachedUser };

  const ctx = await pwRequest.newContext();
  try {
    const status = await (await ctx.get(`${API}/api/v1/setup/status`)).json();
    if (!status.configured) {
      const res = await ctx.post(`${API}/api/v1/setup`, {
        data: { ...ADMIN, storage_backend: "local" },
      });
      if (!res.ok() && res.status() !== 409) {
        throw new Error(`setup failed: ${res.status()} ${await res.text()}`);
      }
    }
    const login = await ctx.post(`${API}/api/v1/auth/login`, { data: ADMIN });
    if (!login.ok()) throw new Error(`login failed: ${login.status()} ${await login.text()}`);
    cachedToken = (await login.json()).access_token;

    const me = await ctx.get(`${API}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${cachedToken}` },
    });
    cachedUser = JSON.stringify(await me.json());
  } finally {
    await ctx.dispose();
  }
  return { token: cachedToken!, user: cachedUser! };
}

// `page` override seeds the real token into localStorage before any navigation,
// so the app boots already authenticated against the live backend.
/* eslint-disable react-hooks/rules-of-hooks -- `use` here is Playwright's fixture callback, not a React hook. */
export const test = base.extend({
  page: async ({ page }, use) => {
    const { token, user } = await ensureAuth();
    await page.addInitScript(
      ([t, u]) => {
        localStorage.setItem("printstash.token", t);
        localStorage.setItem("printstash.user", u);
      },
      [token, user] as const,
    );
    await use(page);
  },
});
/* eslint-enable react-hooks/rules-of-hooks */

export { expect };
