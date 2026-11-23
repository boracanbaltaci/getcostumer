"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import type { Business } from "@/lib/api";

export type MessageKind = "email" | "sms";

export default function MessageModal({ kind, business, onClose }: {
  kind: MessageKind;
  business: Business;
  onClose: () => void;
}) {
  const [text, setText] = useState("");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const title = kind === "email" ? "E-posta Gönder" : "SMS Gönder";
  const target = kind === "sms"
    ? (business.phone ? `Alıcı: ${business.phone}` : "Telefon numarası bilinmiyor")
    : "E-posta adresi bilinmiyor";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
         onClick={onClose} role="dialog" aria-modal="true" aria-label={title}>
      <div className="w-full max-w-lg rounded-xl bg-white shadow-xl" onClick={(e) => e.stopPropagation()}>
        <header className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
            <p className="text-xs text-slate-500">{business.name} — {target}</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Kapat"
                  className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600">
            <X size={18} />
          </button>
        </header>
        <div className="p-5">
          <textarea
            autoFocus
            rows={6}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={kind === "email" ? "E-posta metnini yazın…" : "SMS metnini yazın…"}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
          <div className="mt-4 flex justify-end gap-2">
            <button type="button" onClick={onClose}
                    className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50">
              Vazgeç
            </button>
            <button type="button" onClick={onClose} disabled={!text.trim()}
                    className="rounded-lg bg-brand-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:bg-slate-300">
              Gönder
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
