"use client";

import { Mail, MessageSquare } from "lucide-react";
import type { Business } from "@/lib/api";

const STATUS_BADGE: Record<Business["website_status"], { text: string; cls: string }> = {
  yok: { text: "Site yok", cls: "bg-slate-100 text-slate-600" },
  eski: { text: "Eski görünümlü", cls: "bg-amber-100 text-amber-800" },
  erisilemedi: { text: "Ulaşılamadı", cls: "bg-red-100 text-red-700" },
};

export default function ResultsTable({ businesses, onEmail, onSms }: {
  businesses: Business[];
  onEmail: (b: Business) => void;
  onSms: (b: Business) => void;
}) {
  if (!businesses.length) return null;
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">Firma Adı</th>
            <th className="px-4 py-3">Konum</th>
            <th className="px-4 py-3">Telefon</th>
            <th className="px-4 py-3">Web Sitesi</th>
            <th className="px-4 py-3 text-right">Aksiyon</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {businesses.map((b) => {
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
        </tbody>
      </table>
    </div>
  );
}
