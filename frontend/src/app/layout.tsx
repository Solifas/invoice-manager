import type { Metadata } from "next";
import "./globals.css";

import { AppShell } from "@/components/layout/app-shell";
import { QueryProvider } from "@/components/layout/query-provider";

export const metadata: Metadata = {
  title: "Invoice Manager",
  description: "Minimal invoice management for small businesses and freelancers.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>
          <AppShell>{children}</AppShell>
        </QueryProvider>
      </body>
    </html>
  );
}
