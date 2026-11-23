"use client";

import { useState } from "react";
import { Alert, Badge, Button, Card, HEALTH, PageHeader, Spinner } from "@/components/ui";
import { api, fmtDate, fmtDateTime } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/hooks";

const KIND: Record<string, string> = { webservice: "Resmî web servis", inbox: "Klasör (otomatik)", feed: "Lisanslı akış", manual: "Manuel", reference: "Bilgi (otomasyon yok)" };
const COV: Record<string, string> = { covered: "bg-emerald-500", partial: "bg-amber-400", failed: "bg-red-500", not_scanned: "bg-slate-200" };

export default function SourcesPage() {
  const { can } = useAuth();
  const { data, reload, error } = useApi<any[]>("/sources");
  const cov = useApi<any[]>("/coverage");
  const [err, setErr] = useState<string | null>(null);

  return (
    <div className="space-y-4">
      <PageHeader title="Veri Kaynakları" subtitle="Erişim türü, hukuki dayanak ve sağlık durumu" />
      {(error || err) && <Alert tone="red">{error || err}</Alert>}
      <Card title="Son 30 gün tarama kapsamı">
        {!cov.data ? <Spinner /> : (
          <div className="flex flex-wrap gap-1">
            {cov.data.map((c) => (
              <div key={c.date} title={`${fmtDate(c.date)}: ${c.status}${c.sources.map((s: any) => `\n${s.source}: ${s.status} (${s.records}) ${s.notes || ""}`).join("")}`}
                className={`flex h-9 w-9 items-center justify-center rounded text-[10px] font-semibold ${c.status === "not_scanned" ? "text-slate-500" : "text-white"} ${COV[c.status]} ${c.weekend ? "opacity-50" : ""}`}>
                {c.date.slice(8, 10)}
              </div>
            ))}
          </div>
        )}
        <p className="mt-2 text-xs text-slate-500">Gri günler taranmamıştır ve "sıfır kuruluş" anlamına gelmez. Hafta sonları soluk gösterilir (TTSG tatil günlerinde yayımlanmaz).</p>
      </Card>
      {!data ? <Spinner /> : (
        <div className="grid gap-4 md:grid-cols-2">
          {data.map((s) => (
            <Card key={s.id} title={s.name} actions={<>
              <Badge>{KIND[s.kind] || s.kind}</Badge>
              <Badge tone={HEALTH[s.health]?.tone}>{HEALTH[s.health]?.label || s.health}</Badge></>}>
              <div className="space-y-2 text-sm">
                {s.legal_basis && <p><span className="font-medium">Hukuki dayanak:</span> {s.legal_basis}</p>}
                {s.access_notes && <p className="text-slate-600">{s.access_notes}</p>}
                {s.url && <a className="text-xs text-brand-600 underline" href={s.url} target="_blank" rel="noreferrer">{s.url}</a>}
                <div className="grid grid-cols-2 gap-1 text-xs text-slate-600">
                  <span>Son kontrol: {fmtDateTime(s.last_checked_at)}</span>
                  <span>Son başarılı: {fmtDateTime(s.last_success_at)}</span>
                  <span>Son taranan gün: {fmtDate(s.last_covered_date)}</span>
                  <span>Hatalı gün: {s.failed_days}</span>
                  <span>Kayıtlı işletme: {s.businesses}</span>
                </div>
                {s.last_error && s.health !== "manual" && <Alert tone={s.health === "error" ? "red" : "amber"}>{s.last_error}</Alert>}
                {can("admin") && s.kind !== "reference" && s.kind !== "manual" && (
                  <Button variant={s.enabled ? "secondary" : "primary"} onClick={() => api(`/sources/${s.id}`, { method: "PATCH", json: { enabled: !s.enabled } }).then(reload).catch((e) => setErr(e.message))}>
                    {s.enabled ? "Devre dışı bırak" : "Etkinleştir"}</Button>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
