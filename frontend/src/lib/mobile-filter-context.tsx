"use client";

import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

interface MobileFilterContextValue {
  open: boolean;
  openDrawer: () => void;
  closeDrawer: () => void;
}

const MobileFilterContext = createContext<MobileFilterContextValue | null>(null);

export function MobileFilterProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const openDrawer = useCallback(() => setOpen(true), []);
  const closeDrawer = useCallback(() => setOpen(false), []);

  return (
    <MobileFilterContext.Provider value={{ open, openDrawer, closeDrawer }}>
      {children}
    </MobileFilterContext.Provider>
  );
}

export function useMobileFilterDrawer() {
  const ctx = useContext(MobileFilterContext);
  if (!ctx) {
    throw new Error("useMobileFilterDrawer must be used within MobileFilterProvider");
  }
  return ctx;
}
