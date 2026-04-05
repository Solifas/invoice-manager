"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, isLoading, logout, user } = useAuth();
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const isPublicPaymentRoute = pathname.startsWith("/pay/");
  const isAuthRoute =
    pathname.startsWith("/login") ||
    pathname.startsWith("/register") ||
    pathname.startsWith("/forgot-password") ||
    pathname.startsWith("/reset-password");

  useEffect(() => {
    if (isLoading) {
      return;
    }

    if (isPublicPaymentRoute) {
      return;
    }

    if (isAuthRoute && isAuthenticated) {
      window.location.replace("/");
      return;
    }

    if (!isAuthRoute && !isAuthenticated) {
      window.location.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [isAuthRoute, isAuthenticated, isLoading, isPublicPaymentRoute, pathname]);

  if (isPublicPaymentRoute) {
    return <main className="public-shell">{children}</main>;
  }

  if (isAuthRoute) {
    if (isLoading || isAuthenticated) {
      return <main className="auth-shell auth-shell-loading">Checking your session...</main>;
    }
    return <main className="public-shell">{children}</main>;
  }

  if (isLoading || !isAuthenticated) {
    return <main className="app-loading-shell">Loading your workspace...</main>;
  }

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
            <Link className="button button-ghost" href="/recurring-invoices">
              Recurring
            </Link>
            <Link className="button" href="/invoices/new">
              New invoice
            </Link>
            <button
              className="button button-ghost"
              disabled={isLoggingOut}
              onClick={async () => {
                setIsLoggingOut(true);
                try {
                  await logout();
                  router.replace("/login");
                } finally {
                  setIsLoggingOut(false);
                }
              }}
              type="button"
            >
              {isLoggingOut ? "Logging out..." : "Logout"}
            </button>
          </nav>
        </header>
        <div className="session-banner">
          <span>Signed in as {user?.first_name || user?.email}</span>
          <small>{user?.email}</small>
        </div>
        <main>{children}</main>
      </div>
    </div>
  );
}
