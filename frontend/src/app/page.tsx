"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { Loader2, MapPin } from "lucide-react";
import FavoritesView from "@/components/FavoritesView";
import HistoryView from "@/components/HistoryView";
import LoginScreen from "@/components/LoginScreen";
import MessagesView from "@/components/MessagesView";
import MessageModal, { type MessageKind } from "@/components/MessageModal";
import ResultsTable, { ResultsTableSkeleton } from "@/components/ResultsTable";
import Sidebar, { type View } from "@/components/Sidebar";
import { addBusinessFavoriteApi, getConfig, getScan, listBusinessFavorites, listScans, logout, me,
         removeBusinessFavoriteApi, scanArea,
         type Business, type BusinessFavorite, type ScanResponse, type ScanSummary } from "@/lib/api";

const MapPicker = dynamic(() => import("@/components/MapPicker"), {
  ssr: false,
  loading: () => <div className="flex h-full items-center justify-center text-sm text-slate-400">Harita yükleniyor…</div>,
});

const RADIUS_OPTIONS = [
  { value: 500, label: "500 m" },
  { value: 1000, label: "1 km" },
  { value: 2000, label: "2 km" },
  { value: 5000, label: "5 km" },
];

export default function Home() {
  const [view, setView] = useState<View>("scan");
  const [user, setUser] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [location, setLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [radius, setRadius] = useState(1000);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [scanning, setScanning] = useState(false);
  const [result, setResult] = useState<ScanResponse | null>(null);
  const [lastScanAt, setLastScanAt] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modal, setModal] = useState<{ kind: MessageKind; business: Business } | null>(null);
  const [bizFavorites, setBizFavorites] = useState<BusinessFavorite[]>([]);
  const [scans, setScans] = useState<ScanSummary[]>([]);
  const favBizIds = useMemo(() => new Set(bizFavorites.map((f) => f.place_id)), [bizFavorites]);

  useEffect(() => {
    me()
      .then((u) => setUser(u.username))
      .catch(() => setUser(null))
      .finally(() => setAuthReady(true));
    const onExpired = () => setUser(null);
    window.addEventListener("auth:expired", onExpired);
    return () => window.removeEventListener("auth:expired", onExpired);
  }, []);

  useEffect(() => {
    if (!user) return;
    getConfig()
      .then((c) => setConfigured(c.google_places_configured))
      .catch(() => setConfigured(null));
    listBusinessFavorites()
      .then(setBizFavorites)
      .catch(() => setBizFavorites([]));
    restoreLastScan();
  }, [user]);

  // Yenilemede son taramayı geri yükle: kayıtlar kullanıcıya bağlı ve
  // list_scans en yeni başta döner.
  async function restoreLastScan() {
    try {
      const list = await listScans();
      const latest = list[0];
      if (!latest) return;
      const rec = await getScan(latest.id);
      setLocation({ lat: rec.lat, lng: rec.lng });
      setRadius(rec.radius_m);
      setResult({ businesses: rec.businesses, stats: rec.stats, warnings: [] });
      setLastScanAt(new Date(rec.scanned_at));
    } catch { /* son tarama yüklenemezse boş başlar */ }
  }

  // Haritadaki taralı bölge daireleri: tara görünümüne her dönüşte tazelenir
  // ki geçmişte silinen kayıtlar haritada kalmasın.
  useEffect(() => {
    if (user && view === "scan") refreshScans();
  }, [user, view]);

  async function refreshScans() {
    try {
      setScans(await listScans());
    } catch { /* liste alınamazsa harita sessiz kalır */ }
  }

  async function handleScan() {
    if (!location || scanning) return;
    setScanning(true);
    setError(null);
    try {
      const res = await scanArea(location.lat, location.lng, radius);
      setResult(res);
      setLastScanAt(new Date());
      refreshScans();
    } catch (e) {
      setResult(null);
      setError(e instanceof Error ? e.message : "Tarama başarısız oldu");
    } finally {
      setScanning(false);
    }
  }

  async function toggleBizFavorite(b: Business) {
    try {
      if (favBizIds.has(b.place_id)) {
        await removeBusinessFavoriteApi(b.place_id);
        setBizFavorites((prev) => prev.filter((f) => f.place_id !== b.place_id));
      } else {
        await addBusinessFavoriteApi(b);
        setBizFavorites((prev) => [
          { place_id: b.place_id, added_at: new Date().toISOString(), business: b },
          ...prev,
        ]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Favori güncellenemedi");
    }
  }

  async function handleLogout() {
    try {
      await logout();
    } finally {
      window.location.reload();
    }
  }

  if (!authReady) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-slate-400">
        <Loader2 size={16} className="mr-2 animate-spin" /> Yükleniyor…
      </div>
    );
  }
  if (!user) {
    // Giriş/çıkışta tam yeniden yükleme: oturumlar arası eski state kalmasın.
    return <LoginScreen onLogin={() => window.location.reload()} />;
  }

  return (
    <div className="min-h-screen lg:flex">
      <Sidebar view={view} onNavigate={setView} username={user} onLogout={handleLogout} />
      <main className="min-w-0 flex-1 p-4 lg:p-6">
        {error && (
          <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}
        {view === "history" && <HistoryView favoriteIds={favBizIds} onToggleFavorite={toggleBizFavorite} />}
        {view === "favorites" && (
          <FavoritesView favorites={bizFavorites} favoriteIds={favBizIds} onToggleFavorite={toggleBizFavorite} />
        )}
        {view === "messages" && <MessagesView />}
        {view === "scan" && (
          <>
            {configured === false && (
              <div className="mb-4 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                <strong>Google Places API anahtarı tanımlı değil.</strong> Tarama yapabilmek için
                backend <code className="rounded bg-amber-100 px-1">.env</code> dosyasına{" "}
                <code className="rounded bg-amber-100 px-1">GOOGLE_PLACES_API_KEY</code> ekleyip
                servisi yeniden başlatın (README → &quot;Google API anahtarı alma&quot;).
              </div>
            )}

            <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
              <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 px-4 py-3">
                <span className="flex items-center gap-1.5 text-sm text-slate-600">
                  <MapPin size={15} className="text-brand-600" />
                  {location
                    ? `Seçili: ${location.lat.toFixed(5)}, ${location.lng.toFixed(5)}`
                    : "Konum seçmek için haritaya tıklayın"}
                </span>
                <label className="ml-auto flex items-center gap-2 text-sm text-slate-600">
                  Yarıçap
                  <select value={radius} onChange={(e) => setRadius(Number(e.target.value))}
                          className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm focus:border-brand-500 focus:outline-none">
                    {RADIUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </label>
                <button type="button" onClick={handleScan} disabled={!location || scanning || configured === false}
                        className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:bg-slate-300">
                  {scanning && <Loader2 size={15} className="animate-spin" />}
                  {scanning ? "Taranıyor…" : "Tara"}
                </button>
              </div>
              <div className="h-[420px] p-3">
                <MapPicker value={location} radius={radius} scans={scans} onPick={setLocation} />
              </div>
            </section>

            {scanning && (
              <section className="mt-4">
                <p className="mb-2 text-sm text-slate-500">Bölge taranıyor, işletme siteleri inceleniyor…</p>
                <ResultsTableSkeleton />
              </section>
            )}

            {!scanning && result && (
              <section className="mt-4">
                <div className="mb-3 flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-medium text-slate-700">
                    {result.stats.found} işletme tarandı → {result.stats.shown} aday listelendi:
                  </span>
                  <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
                    {result.stats.without_website} sitesiz
                  </span>
                  <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800">
                    {result.stats.outdated_website} eski siteli
                  </span>
                  <span className="rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700">
                    {result.stats.unreachable_website} ulaşılamayan
                  </span>
                  <span className="text-xs text-slate-400">
                    ({result.stats.filtered_modern} modern siteli elendi)
                  </span>
                  {lastScanAt && (
                    <span className="ml-auto text-xs text-slate-400">
                      Son tarama: {lastScanAt.toLocaleTimeString("tr-TR")}
                    </span>
                  )}
                </div>
                {result.warnings.length > 0 && (
                  <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                    {result.warnings.map((w, i) => <div key={i}>{w}</div>)}
                  </div>
                )}
                {result.businesses.length
                  ? <ResultsTable businesses={result.businesses}
                                  onEmail={(b) => setModal({ kind: "email", business: b })}
                                  onSms={(b) => setModal({ kind: "sms", business: b })}
                                  favoriteIds={favBizIds}
                                  onToggleFavorite={toggleBizFavorite} />
                  : <div className="rounded-xl border border-slate-200 bg-white px-4 py-6 text-center text-sm text-slate-500 shadow-sm">
                      Bu bölgede sitesiz/eski siteli işletme bulunamadı.
                    </div>}
              </section>
            )}
          </>
        )}
      </main>

      {modal && (
        <MessageModal kind={modal.kind} business={modal.business} onClose={() => setModal(null)} />
      )}
    </div>
  );
}
