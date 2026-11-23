"use client";

import { useState } from "react";
import { Mail, MessageSquare } from "lucide-react";
import type { Business } from "@/lib/api";

const STATUS_BADGE: Record<Business["website_status"], { text: string; cls: string }> = {
  yok: { text: "Site yok", cls: "bg-slate-100 text-slate-600" },
  eski: { text: "Eski görünümlü", cls: "bg-amber-100 text-amber-800" },
  erisilemedi: { text: "Ulaşılamadı", cls: "bg-red-100 text-red-700" },
};

type StatusFilter = "all" | "yok" | "var" | "eski";

function matches(b: Business, f: StatusFilter): boolean {
  if (f === "all") return true;
  if (f === "yok") return b.website_status === "yok";
  if (f === "eski") return b.website_status === "eski";
  return b.website_status !== "yok"; // "var": sitesi olanlar (eski + ulaşılamadı)
}

const HEAD = (
  <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
    <tr>
      <th className="px-4 py-3">Firma Adı</th>
      <th className="px-4 py-3">Konum</th>
      <th className="px-4 py-3">Telefon</th>
      <th className="px-4 py-3">Web Sitesi</th>
      <th className="px-4 py-3 text-right">Aksiyon</th>
    </tr>
  </thead>
);

export default function ResultsTable({ businesses, onEmail, onSms }: {
  businesses: Business[];
  onEmail: (b: Business) => void;
  onSms: (b: Business) => void;
}) {
  const [filter, setFilter] = useState<StatusFilter>("all");
  if (!businesses.length) return null;

  const counts: Record<StatusFilter, number> = {
    all: businesses.length,
    yok: businesses.filter((b) => b.website_status === "yok").length,
    eski: businesses.filter((b) => b.website_status === "eski").length,
    var: businesses.filter((b) => b.website_status !== "yok").length,
  };
  const filters: { key: StatusFilter; label: string }[] = [
    { key: "all", label: "Tümü" },
    { key: "yok", label: "Sitesi yok" },
    { key: "var", label: "Sitesi var" },
    { key: "eski", label: "Eski görünümlü" },
  ];
  const rows = businesses.filter((b) => matches(b, filter));

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-wrap gap-1.5 border-b border-slate-100 px-3 py-2.5">
        {filters.map((f) => (
          <button key={f.key} type="button" onClick={() => setFilter(f.key)}
                  className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                    filter === f.key
                      ? "bg-brand-600 text-white"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}>
            {f.label} <span className="tabular-nums">({counts[f.key]})</span>
          </button>
        ))}
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          {HEAD}
          <tbody className="divide-y divide-slate-100">
            {rows.map((b) => {
              const badge = STATUS_BADGE[b.website_status];
              return (
                <tr key={b.place_id} className="hover:bg-slate-50">
                  <td className="max-w-56 px-4 py-3 font-medium text-slate-900">{b.name}</td>
                  <td className="max-w-72 px-4 py-3 text-slate-600">{b.address || "—"}</td>
                  <td className="whitespace-nowrap px-4 py-3">
                    {b.phone
                      ? <a href={`tel:${b.phone.replace(/[^+\d]/g, "")}`} className="text-brand-600 hover:underline">{b.phone}</a>
                      : <span className="text-slate-400">—</span>}
                  </td>
                  <td className="max-w-60 px-4 py-3">
                    <div className="flex flex-wrap items-center gap-2">
                      {b.website
                        ? <a href={b.website} target="_blank" rel="noreferrer"
                             className="max-w-40 truncate text-brand-600 hover:underline">{b.website.replace(/^https?:\/\//, "")}</a>
                        : <span className="text-slate-400">—</span>}
                      <span title={b.website_notes.join("; ") || badge.text}
                            className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${badge.cls}`}>
                        {badge.text}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-1.5">
                      <button type="button" title="E-posta gönder" aria-label={`${b.name} için e-posta gönder`}
                              onClick={() => onEmail(b)}
                              className="rounded-lg border border-slate-200 p-2 text-slate-500 transition hover:border-brand-500 hover:text-brand-600">
                        <Mail size={16} />
                      </button>
                      <button type="button" title="SMS gönder" aria-label={`${b.name} için SMS gönder`}
                              onClick={() => onSms(b)}
                              className="rounded-lg border border-slate-200 p-2 text-slate-500 transition hover:border-brand-500 hover:text-brand-600">
                        <MessageSquare size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
            {!rows.length && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-sm text-slate-400">Bu filtreye uyan işletme yok.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function ResultsTableSkeleton({ rows = 8 }: { rows?: number }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex gap-1.5 border-b border-slate-100 px-3 py-2.5">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-6 w-24 animate-pulse rounded-full bg-slate-100" />
        ))}
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          {HEAD}
          <tbody>
            {Array.from({ length: rows }).map((_, i) => (
              <tr key={i} className="border-b border-slate-50">
                {[40, 56, 24, 48, 16].map((w, j) => (
                  <td key={j} className="px-4 py-3.5">
                    <div className={`h-4 animate-pulse rounded bg-slate-100`} style={{ width: `${w}%` }} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
