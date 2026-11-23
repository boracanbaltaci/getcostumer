"use client";

import { Heart, History, LogOut, MessagesSquare, ScanSearch, User } from "lucide-react";

export type View = "scan" | "history" | "favorites" | "messages";

const NAV: { key: View; label: string; icon: typeof ScanSearch }[] = [
  { key: "scan", label: "Tarama", icon: ScanSearch },
  { key: "history", label: "Önceki Taramalar", icon: History },
  { key: "favorites", label: "Favoriler", icon: Heart },
  { key: "messages", label: "Hızlı Mesajlar", icon: MessagesSquare },
];

export default function Sidebar({ view, onNavigate, username, onLogout }: {
  view: View;
  onNavigate: (v: View) => void;
  username: string;
  onLogout: () => void;
}) {
  return (
    <aside className="flex flex-col bg-brand-900 p-4 lg:min-h-screen lg:w-56 lg:shrink-0">
      <div className="mb-4 flex items-center gap-2 lg:mb-6">
        <ScanSearch className="text-white" size={22} />
        <span className="text-base font-bold text-white">İşletme Radarı</span>
      </div>
      <nav className="flex gap-1 lg:flex-col">
        {NAV.map((n) => {
          const Icon = n.icon;
          const active = view === n.key;
          return (
            <button key={n.key} type="button" onClick={() => onNavigate(n.key)}
                    className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition ${
                      active ? "bg-white/15 font-semibold text-white" : "text-slate-300 hover:bg-white/10 hover:text-white"
                    }`}>
              <Icon size={16} />
              {n.label}
            </button>
          );
        })}
      </nav>
      <div className="mt-4 flex items-center gap-2 border-t border-white/10 pt-3 text-sm text-slate-300 lg:mt-auto">
        <User size={14} className="shrink-0" />
        <span className="truncate">{username}</span>
        <button type="button" onClick={onLogout} title="Çıkış yap" aria-label="Çıkış yap"
                className="ml-auto shrink-0 rounded-lg p-1.5 text-slate-400 transition hover:bg-white/10 hover:text-white">
          <LogOut size={15} />
        </button>
      </div>
    </aside>
  );
}
