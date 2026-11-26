"use client";

import { useState } from "react";
import { Heart } from "lucide-react";
import HistoryView from "@/components/HistoryView";
import MessageModal, { type MessageKind } from "@/components/MessageModal";
import ResultsTable from "@/components/ResultsTable";
import type { Business, BusinessFavorite } from "@/lib/api";

export default function FavoritesView({ favorites, favoriteIds, onToggleFavorite }: {
  favorites: BusinessFavorite[];
  favoriteIds: Set<string>;
  onToggleFavorite: (b: Business) => void;
}) {
  const [modal, setModal] = useState<{ kind: MessageKind; businesses: Business[] } | null>(null);
  const businesses = favorites.map((f) => f.business);

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <header className="flex items-center gap-1.5 border-b border-slate-100 px-4 py-3">
          <Heart size={14} className="text-red-500" fill="currentColor" />
          <h2 className="text-sm font-semibold text-slate-800">
            Favori İşletmeler ({businesses.length})
          </h2>
        </header>
        <div className="bg-slate-50/60 p-3">
          {businesses.length ? (
            <ResultsTable businesses={businesses}
                          onEmail={(b) => setModal({ kind: "email", businesses: [b] })}
                          onSms={(b) => setModal({ kind: "sms", businesses: [b] })}
                          onBulkEmail={(bs) => setModal({ kind: "email", businesses: bs })}
                          favoriteIds={favoriteIds}
                          onToggleFavorite={onToggleFavorite} />
          ) : (
            <p className="px-4 py-6 text-center text-sm text-slate-500">
              Henüz favori işletme yok. Tablolardaki kalp ikonuyla ekleyin.
            </p>
          )}
        </div>
      </section>

      <HistoryView favoritesOnly favoriteIds={favoriteIds} onToggleFavorite={onToggleFavorite} />

      {modal && <MessageModal kind={modal.kind} businesses={modal.businesses} onClose={() => setModal(null)} />}
    </div>
  );
}
