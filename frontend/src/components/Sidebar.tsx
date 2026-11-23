"use client";

import { History, ScanSearch } from "lucide-react";

export type View = "scan" | "history";

const NAV: { key: View; label: string; icon: typeof ScanSearch }[] = [
  { key: "scan", label: "Tarama", icon: ScanSearch },
  { key: "history", label: "Önceki Taramalar", icon: History },
];

export default function Sidebar({ view, onNavigate }: {
  view: View;
  onNavigate: (v: View) => void;
}) {
  return (
    <aside className="bg-brand-900 p-4 lg:min-h-screen lg:w-56 lg:shrink-0">
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
    </aside>
  );
}
