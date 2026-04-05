import Link from "next/link";
import { ReactNode } from "react";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-frame">
      <div className="app-backdrop" />
      <div className="shell">
        <header className="topbar">
          <div className="brand-block">
            <div className="brand-mark">IM</div>
            <div>
              <p className="eyebrow">Invoice Manager</p>
              <h1>Billing that feels calm, not chaotic.</h1>
              <p className="subtle-copy">
                Track invoices, stay ahead of due dates, and keep client billing clean from one place.
              </p>
            </div>
          </div>
          <nav className="topbar-actions">
            <Link className="button button-ghost" href="/">
              Dashboard
            </Link>
            <Link className="button" href="/invoices/new">
              New invoice
            </Link>
          </nav>
        </header>
        <main>{children}</main>
      </div>
    </div>
  );
}
