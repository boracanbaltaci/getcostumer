"use client";

import { useEffect, useState } from "react";
import { Loader2, X } from "lucide-react";
import { discoverEmailsApi, listQuickMessages, sendEmailApi,
         type Business, type QuickMessage, type SendEmailResult } from "@/lib/api";

export type MessageKind = "email" | "sms";

const INPUT_CLS = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500";

export default function MessageModal({ kind, businesses, onClose }: {
  kind: MessageKind;
  businesses: Business[];
  onClose: () => void;
}) {
  const [text, setText] = useState("");
  const [subject, setSubject] = useState("");
  const [emails, setEmails] = useState<Record<string, string>>(() =>
    Object.fromEntries(businesses.map((b) => [b.place_id, b.email || ""])));
  const [quickMsgs, setQuickMsgs] = useState<QuickMessage[]>([]);
  const [discovering, setDiscovering] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<SendEmailResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    listQuickMessages().then(setQuickMsgs).catch(() => {});
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Modal açılınca: e-postası bilinmeyen siteli işletmeler için öneri kazı.
  useEffect(() => {
    if (kind !== "email") return;
    const need = businesses
      .filter((b) => !b.email && b.website)
      .map((b) => b.website as string);
    if (!need.length) return;
    setDiscovering(true);
    discoverEmailsApi(need)
      .then(({ results }) => {
        setEmails((prev) => {
          const next = { ...prev };
          for (const b of businesses) {
            if (!next[b.place_id] && b.website && results[b.website]?.length) {
              next[b.place_id] = results[b.website][0];
            }
          }
          return next;
        });
      })
      .catch(() => {})
      .finally(() => setDiscovering(false));
  }, [kind, businesses]);

  const single = businesses.length === 1 ? businesses[0] : null;
  const title = kind === "email"
    ? (single ? "E-posta Gönder" : `Toplu E-posta Gönder (${businesses.length})`)
    : "SMS Gönder";
  const subtitle = kind === "sms"
    ? `${single?.name ?? `${businesses.length} işletme`} — ${single?.phone ? `Alıcı: ${single.phone}` : "Telefon numarası bilinmiyor"}`
    : `${single?.name ?? `${businesses.length} işletme seçili`}`;

  const recipients = businesses
    .map((b) => ({ to: (emails[b.place_id] || "").trim(), name: b.name }))
    .filter((r) => r.to);
  const canSend = kind === "email" && !busy && !result
    && recipients.length > 0 && !!subject.trim() && !!text.trim();

  async function send() {
    if (!canSend) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await sendEmailApi(recipients, subject.trim(), text.trim()));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gönderim başarısız");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
         onClick={onClose} role="dialog" aria-modal="true" aria-label={title}>
      <div className="w-full max-w-lg rounded-xl bg-white shadow-xl" onClick={(e) => e.stopPropagation()}>
        <header className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
            <p className="text-xs text-slate-500">{subtitle}</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Kapat"
                  className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600">
            <X size={18} />
          </button>
        </header>
        <div className="max-h-[75vh] overflow-y-auto p-5">
          {quickMsgs.length > 0 && !result && (
            <select value="" aria-label="Hızlı mesaj seç"
                    onChange={(e) => {
                      const m = quickMsgs.find((q) => q.id === e.target.value);
                      if (m) {
                        if (kind === "email") setSubject(m.title);
                        setText(m.text);
                      }
                    }}
                    className="mb-3 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-600 focus:border-brand-500 focus:outline-none">
              <option value="" disabled>Hızlı mesaj seç…</option>
              {quickMsgs.map((q) => (
                <option key={q.id} value={q.id}>
                  {q.title}{q.text ? ` — ${q.text.slice(0, 50)}${q.text.length > 50 ? "…" : ""}` : ""}
                </option>
              ))}
            </select>
          )}

          {kind === "email" && (
            <div className="mb-3">
              <div className="mb-1 flex items-center justify-between text-xs font-medium text-slate-600">
                <span>Alıcılar ({recipients.length}/{businesses.length})</span>
                {discovering && (
                  <span className="flex items-center gap-1 text-slate-400">
                    <Loader2 size={12} className="animate-spin" /> Adresler aranıyor…
                  </span>
                )}
              </div>
              <div className={single ? "" : "max-h-36 space-y-2 overflow-y-auto rounded-lg border border-slate-100 p-2"}>
                {businesses.map((b) => (
                  <div key={b.place_id} className={single ? "" : "flex items-center gap-2"}>
                    {!single && (
                      <span className="w-40 shrink-0 truncate text-xs text-slate-600" title={b.name}>
                        {b.name}
                      </span>
                    )}
                    <input
                      type="email"
                      value={emails[b.place_id] ?? ""}
                      onChange={(e) => setEmails((prev) => ({ ...prev, [b.place_id]: e.target.value }))}
                      placeholder={b.website ? "e-posta adresi" : "e-posta adresi (site yok)"}
                      aria-label={`${b.name} e-posta adresi`}
                      className={INPUT_CLS}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          {kind === "email" && (
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Konu"
              aria-label="E-posta konusu"
              className={`${INPUT_CLS} mb-3`}
            />
          )}

          <textarea
            autoFocus
            rows={6}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={kind === "email" ? "E-posta metnini yazın… ({firma_adi} tutucusu işletme adıyla değişir)" : "SMS metnini yazın…"}
            className={INPUT_CLS}
          />

          {error && (
            <p className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p>
          )}
          {result && (
            <div className="mt-3 space-y-1">
              <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-700">
                {result.sent} e-posta gönderildi.
              </p>
              {result.failed.map((f) => (
                <p key={f.to} className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                  {f.to}: {f.error}
                </p>
              ))}
            </div>
          )}

          <div className="mt-4 flex justify-end gap-2">
            <button type="button" onClick={onClose}
                    className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50">
              {result ? "Kapat" : "Vazgeç"}
            </button>
            {!result && (
              <button type="button" onClick={kind === "email" ? send : onClose}
                      disabled={kind === "email" ? !canSend : !text.trim()}
                      className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:bg-slate-300">
                {busy && <Loader2 size={14} className="animate-spin" />}
                Gönder
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
