import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";

export const metadata: Metadata = {
  title: "RELATRUM",
  description: "Where expectations meet evidence.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <div className="flex min-h-screen">
          <aside className="hidden w-60 flex-col border-r border-[var(--color-border)] bg-[var(--color-surface)] md:flex">
            <div className="px-4 py-5 text-lg font-semibold">RELATRUM</div>
            <nav className="flex flex-1 flex-col gap-1 px-2 text-sm">
              <Link className="rounded px-3 py-2 hover:bg-[var(--color-bg)]" href="/dashboard">Dashboard</Link>
              <Link className="rounded px-3 py-2 hover:bg-[var(--color-bg)]" href="/login">Login</Link>
            </nav>
            <div className="px-4 py-3 text-xs muted">Evidence intelligence</div>
          </aside>
          <div className="flex flex-1 flex-col">
            <header className="border-b border-[var(--color-border)] bg-[var(--color-surface)]">
              <div className="flex items-center justify-between px-4 py-3">
                <span className="text-sm font-medium md:hidden">RELATRUM</span>
                <span className="text-xs muted">Where expectations meet evidence.</span>
              </div>
            </header>
            <main className="flex-1 px-4 py-6 md:px-6">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
