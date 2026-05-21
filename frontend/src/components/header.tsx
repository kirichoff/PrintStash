"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Box } from "lucide-react";

export function Header() {
  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 items-center">
        <Link href="/" className="mr-6 flex items-center space-x-2">
          <Box className="h-6 w-6" />
          <span className="hidden font-bold sm:inline-block">
            Nexus3D Vault
          </span>
        </Link>
        <nav className="flex flex-1 items-center space-x-2 justify-end">
          <Button variant="ghost" size="sm" asChild>
            <Link href="/">Assets</Link>
          </Button>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/printers">Printers</Link>
          </Button>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/upload">Upload</Link>
          </Button>
        </nav>
      </div>
    </header>
  );
}
