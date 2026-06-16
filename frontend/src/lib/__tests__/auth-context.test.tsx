import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import { AuthProvider, useAuth } from "@/lib/auth-context";
import { storeLogin } from "@/lib/auth-store";

vi.mock("@/lib/api", () => ({
  getMe: vi.fn(),
  login: vi.fn(),
}));

function AuthProbe() {
  const { loading, user } = useAuth();
  if (loading) return <div>loading</div>;
  return <div>{user ? `signed in:${user.username}` : "signed out"}</div>;
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe("AuthProvider", () => {
  it("observes first-run setup login in the same tab", async () => {
    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    );

    await screen.findByText("signed out");

    storeLogin("setup-token", {
      id: 1,
      username: "admin",
      email: null,
      is_superuser: true,
    });

    await waitFor(() => {
      expect(screen.getByText("signed in:admin")).toBeTruthy();
    });
  });
});
