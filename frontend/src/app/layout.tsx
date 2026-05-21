import type { Metadata } from "next";
import "./globals.css";
import { Header } from "@/components/header";

export const metadata: Metadata = {
  title: "Nexus3D Vault",
  description: "Self-hosted asset management for 3D printing workflows",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">
        <Header />
        <main className="container py-6">{children}</main>
      </body>
    </html>
  );
}
