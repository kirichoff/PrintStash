import type { ReactNode } from "react";
import { renderHook } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { useRouter } from "@/lib/navigation";

function wrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>;
}

describe("useRouter", () => {
  it("keeps router identity stable across consumer rerenders", () => {
    const { result, rerender } = renderHook(() => useRouter(), { wrapper });
    const firstRouter = result.current;

    rerender();

    expect(result.current).toBe(firstRouter);
  });
});
