"use client";

import { useEffect, useState } from "react";
import { ChevronDown, Clock, Heart, Loader2, MapPin, Trash2 } from "lucide-react";
import MessageModal, { type MessageKind } from "@/components/MessageModal";
import ResultsTable from "@/components/ResultsTable";
import { addFavoriteApi, deleteScanApi, getScan, listFavorites, listScans, removeFavoriteApi, type Business, type ScanRecord, type ScanSummary } from "@/lib/api";

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleString("tr-TR", {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export default function HistoryView({ favoritesOnly = false, favoriteIds, onToggleFavorite }: {
  favoritesOnly?: boolean;
  favoriteIds?: Set<string>;
  onToggleFavorite?: (b: Business) => void;
}) {
  const [scans, setScans] = useState<ScanSummary[] | null>(null);
  const [details, setDetails] = useState<Record<string, ScanRecord>>({});
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [loadingIds, setLoadingIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [modal, setModal] = useState<{ kind: MessageKind; business: Business } | null>(null);

  useEffect(() => {
    (favoritesOnly ? listFavorites() : listScans())
      .then(setScans)
      .catch((e) => setError(e instanceof Error ? e.message : "Geçmiş yüklenemedi"));
  }, [favoritesOnly]);

  async function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
    if (details[id] || loadingIds.has(id)) return;
    setLoadingIds((prev) => new Set(prev).add(id));
    try {
      const rec = await getScan(id);
      setDetails((prev) => ({ ...prev, [id]: rec }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Kayıt açılamadı");
      setExpanded((prev) => { const n = new Set(prev); n.delete(id); return n; });
    } finally {
      setLoadingIds((prev) => { const n = new Set(prev); n.delete(id); return n; });
    }
  }

  async function remove(id: string) {
    try {
      await deleteScanApi(id);
      dropRow(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Kayıt silinemedi");
    }
  }

  function dropRow(id: string) {
    setScans((prev) => (prev ?? []).filter((s) => s.id !== id));
    setDetails((prev) => { const n = { ...prev }; delete n[id]; return n; });
    setExpanded((prev) => { const n = new Set(prev); n.delete(id); return n; });
  }

  async function toggleFav(s: ScanSummary) {
    try {
      if (s.is_favorite) await removeFavoriteApi(s.id); else await addFavoriteApi(s.id);
      if (favoritesOnly && s.is_favorite) dropRow(s.id);
      else setScans((prev) => (prev ?? []).map((x) => (x.id === s.id ? { ...x, is_favorite: !s.is_favorite } : x)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Favori güncellenemedi");
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
        {favoritesOnly
          ? "Henüz favori tarama yok. Önceki Taramalar'da kalp ikonuna basarak ekleyin."
          : "Henüz tarama kaydı yok. Tarama ekranından konum seçip Tara'ya basın."}
      </div>
    );
  }

  return (
    <>
      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <header className="border-b border-slate-100 px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-800">
            {favoritesOnly ? "Favori Taramalar" : "Önceki Taramalar"} ({scans.length})
          </h2>
        </header>
        <ul className="divide-y divide-slate-100">
          {scans.map((s) => {
            const open = expanded.has(s.id);
            const rec = details[s.id];
            return (
              <li key={s.id}>
                <button type="button" onClick={() => toggle(s.id)}
                        className={`flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-left transition hover:bg-slate-50 ${
                          open ? "bg-brand-50" : ""}`}>
                  <ChevronDown size={15} className={`text-slate-400 transition-transform ${open ? "" : "-rotate-90"}`} />
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
                  <span className="ml-auto flex items-center gap-2">
                    <span onClick={(e) => { e.stopPropagation(); toggleFav(s); }}>
                      <Heart size={15} fill={s.is_favorite ? "currentColor" : "none"} aria-label="Favori"
                             className={s.is_favorite ? "text-red-500" : "text-slate-300 transition hover:text-red-400"} />
                    </span>
                    <span onClick={(e) => { e.stopPropagation(); remove(s.id); }}>
                      <Trash2 size={15} className="text-slate-300 transition hover:text-red-500" aria-label="Kaydı sil" />
                    </span>
                  </span>
                </button>
                {open && (
                  <div className="border-t border-slate-100 bg-slate-50/60 p-3">
                    {loadingIds.has(s.id) && (
                      <div className="flex items-center gap-2 p-4 text-sm text-slate-500">
                        <Loader2 size={16} className="animate-spin" /> Kayıt açılıyor…
                      </div>
                    )}
                    {rec && !loadingIds.has(s.id) && (
                      <ResultsTable businesses={rec.businesses}
                                    onEmail={(b) => setModal({ kind: "email", business: b })}
                                    onSms={(b) => setModal({ kind: "sms", business: b })}
                                    favoriteIds={favoriteIds}
                                    onToggleFavorite={onToggleFavorite} />
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      {modal && <MessageModal kind={modal.kind} business={modal.business} onClose={() => setModal(null)} />}
    </>
  );
}
