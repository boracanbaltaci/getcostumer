"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";

const NAV: { href: string; label: string; role?: "sales" | "manager" | "admin" }[] = [
  { href: "/", label: "Gösterge Paneli" },
  { href: "/businesses", label: "İşletmeler" },
  { href: "/reminders", label: "Takipler" },
  { href: "/quotes", label: "Teklifler" },
  { href: "/review", label: "İnceleme Kuyruğu", role: "sales" },
  { href: "/merge", label: "Mükerrer Eşleştirme", role: "sales" },
  { href: "/import", label: "İçe Aktar", role: "sales" },
  { href: "/sources", label: "Veri Kaynakları" },
  { href: "/jobs", label: "Zamanlanmış Görevler" },
  { href: "/reports", label: "Raporlar" },
  { href: "/users", label: "Kullanıcılar ve Denetim", role: "admin" },
  { href: "/account", label: "Hesabım" },
];

export default function Shell({ children }: { children: React.ReactNode }) {
  const { user, loading, logout, can } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const isLogin = pathname === "/login";

  useEffect(() => {
    if (!loading && !user && !isLogin) router.replace("/login");
  }, [loading, user, isLogin, router]);

  useEffect(() => setOpen(false), [pathname]);

  if (isLogin) return <>{children}</>;
  if (loading || !user) return <div className="p-8 text-center text-sm text-slate-500">Yükleniyor…</div>;

  const nav = NAV.filter((n) => !n.role || can(n.role));
  const active = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <div className="min-h-screen lg:flex">
      <aside className={`${open ? "block" : "hidden"} fixed inset-0 z-40 bg-brand-900/95 p-4 lg:static lg:block lg:w-60 lg:shrink-0 lg:bg-brand-900`}>
        <div className="mb-6 flex items-center justify-between">
          <Link href="/" className="text-base font-bold text-white">Ankara Business Radar</Link>
          <button className="text-white lg:hidden" onClick={() => setOpen(false)} aria-label="Menüyü kapat">✕</button>
        </div>
        <nav className="space-y-0.5">
          {nav.map((n) => (
            <Link key={n.href} href={n.href}
              className={`block rounded-lg px-3 py-2 text-sm ${active(n.href) ? "bg-white/15 font-semibold text-white" : "text-slate-300 hover:bg-white/10 hover:text-white"}`}>
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="mt-8 border-t border-white/10 pt-4 text-xs text-slate-400">
          <div className="font-medium text-slate-200">{user.full_name}</div>
          <div>{user.email}</div>
          <button onClick={logout} className="mt-2 text-slate-300 underline hover:text-white">Çıkış yap</button>
        </div>
      </aside>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 lg:hidden">
          <button onClick={() => setOpen(true)} className="rounded-lg border border-slate-300 px-3 py-1 text-sm" aria-label="Menüyü aç">☰ Menü</button>
          <span className="text-sm font-semibold text-brand-700">Ankara Business Radar</span>
        </div>
        <main className="mx-auto max-w-7xl p-4 lg:p-6">{children}</main>
      </div>
    </div>
  );
}
