"use client";

import { useEffect, useState } from "react";
import { Clock, Loader2, MapPin, Trash2 } from "lucide-react";
import MessageModal, { type MessageKind } from "@/components/MessageModal";
import ResultsTable from "@/components/ResultsTable";
import { deleteScanApi, getScan, listScans, type Business, type ScanRecord, type ScanSummary } from "@/lib/api";

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleString("tr-TR", {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export default function HistoryView() {
  const [scans, setScans] = useState<ScanSummary[] | null>(null);
  const [selected, setSelected] = useState<ScanRecord | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [modal, setModal] = useState<{ kind: MessageKind; business: Business } | null>(null);

  useEffect(() => {
    listScans()
      .then(setScans)
      .catch((e) => setError(e instanceof Error ? e.message : "Geçmiş yüklenemedi"));
  }, []);

  async function toggle(id: string) {
    if (selected?.id === id) { setSelected(null); return; }
    setLoadingDetail(true);
    try {
      setSelected(await getScan(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Kayıt açılamadı");
    } finally {
      setLoadingDetail(false);
    }
  }

  async function remove(id: string) {
    try {
      await deleteScanApi(id);
      setScans((prev) => (prev ?? []).filter((s) => s.id !== id));
      if (selected?.id === id) setSelected(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Kayıt silinemedi");
    }
  }

  if (error) {
    return <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>;
  }
  if (!scans) {
    return <div className="flex items-center gap-2 p-6 text-sm text-slate-500"><Loader2 size={16} className="animate-spin" /> Geçmiş yükleniyor…</div>;
  }
  if (!scans.length) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white px-4 py-10 text-center text-sm text-slate-500 shadow-sm">
        Henüz tarama kaydı yok. Tarama ekranından konum seçip Tara&apos;ya basın.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <header className="border-b border-slate-100 px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-800">Önceki Taramalar ({scans.length})</h2>
        </header>
        <ul className="divide-y divide-slate-100">
          {scans.map((s) => (
            <li key={s.id}>
              <button type="button" onClick={() => toggle(s.id)}
                      className={`flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-left transition hover:bg-slate-50 ${
                        selected?.id === s.id ? "bg-brand-50" : ""}`}>
                <span className="flex items-center gap-1.5 text-sm font-medium text-slate-800">
                  <Clock size={14} className="text-slate-400" /> {fmtTime(s.scanned_at)}
                </span>
                <span className="flex items-center gap-1 text-xs text-slate-500">
                  <MapPin size={13} /> {s.lat.toFixed(4)}, {s.lng.toFixed(4)} — {s.radius_m} m
                </span>
                <span className="flex gap-1.5 text-[11px] font-medium">
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-600">{s.stats.without_website} sitesiz</span>
                  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-amber-800">{s.stats.outdated_website} eski</span>
                  <span className="rounded-full bg-red-100 px-2 py-0.5 text-red-700">{s.stats.unreachable_website} ulaşılamadı</span>
                </span>
                <span className="ml-auto" onClick={(e) => { e.stopPropagation(); remove(s.id); }}>
                  <Trash2 size={15} className="text-slate-300 transition hover:text-red-500" aria-label="Kaydı sil" />
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      {loadingDetail && (
        <div className="flex items-center gap-2 p-4 text-sm text-slate-500"><Loader2 size={16} className="animate-spin" /> Kayıt açılıyor…</div>
      )}
      {selected && !loadingDetail && (
        <section>
          <p className="mb-2 text-sm text-slate-600">
            {fmtTime(selected.scanned_at)} taraması — {selected.businesses.length} işletme
          </p>
          <ResultsTable businesses={selected.businesses}
                        onEmail={(b) => setModal({ kind: "email", business: b })}
                        onSms={(b) => setModal({ kind: "sms", business: b })} />
        </section>
      )}

      {modal && <MessageModal kind={modal.kind} business={modal.business} onClose={() => setModal(null)} />}
    </div>
  );
}
