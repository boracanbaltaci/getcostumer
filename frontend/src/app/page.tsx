"use client";

import Link from "next/link";
import { Alert, Badge, Card, HEALTH, JOB_STATUS, Score, Spinner, Stat, Table, Td } from "@/components/ui";
import { fmtDate, fmtDateTime } from "@/lib/api";
import { useApi } from "@/lib/hooks";

type Coverage = { date: string; status: string; weekend: boolean; new_businesses: number | null };

const COV: Record<string, { cls: string; label: string }> = {
  covered: { cls: "bg-emerald-500", label: "Tarandı" },
  partial: { cls: "bg-amber-400", label: "Kısmi" },
  failed: { cls: "bg-red-500", label: "Erişim hatası" },
  not_scanned: { cls: "bg-slate-300", label: "Taranmadı" },
};

export default function Dashboard() {
  const { data, error } = useApi<any>("/dashboard");
  if (error) return <Alert tone="red">{error}</Alert>;
  if (!data) return <Spinner />;
  const m = data.metrics;
  const today: Coverage | undefined = data.coverage[data.coverage.length - 1];
  const todayScanned = today?.status === "covered";

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-xl font-bold">Gösterge Paneli</h1>
          <p className="text-sm text-slate-500">Ankara'da yeni kurulan işletmeler · İSG ve yazılım fırsatları</p>
        </div>
        {data.last_job && (
          <div className="text-xs text-slate-500">
            Son günlük tarama: {fmtDateTime(data.last_job.started_at)}{" "}
            <Badge tone={JOB_STATUS[data.last_job.status]?.tone}>{JOB_STATUS[data.last_job.status]?.label || data.last_job.status}</Badge>
          </div>
        )}
      </div>

      {!todayScanned && (
        <Alert>
          <b>Bugün için yetkili kaynaklardan tarama yapılamadı.</b> Aşağıdaki "bugün tespit edilen" sayısı yalnızca
          içe aktarılan kayıtları yansıtır; "sıfır yeni kuruluş" anlamına gelmez. Durumu{" "}
          <Link className="underline" href="/sources">Veri Kaynakları</Link> sayfasından kontrol edin.
        </Alert>
      )}
      {m.needs_review > 0 && (
        <Alert tone="blue"><Link href="/review" className="underline">{m.needs_review} kayıt</Link> manuel inceleme bekliyor (kuruluş ilanı olup olmadığı otomatik doğrulanamadı).</Alert>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        <Stat label="Bugün tespit edilen" value={m.today_detected} href="/businesses?today=1" tone={todayScanned ? "default" : "warn"}
          hint={todayScanned ? "Bugün taranan kaynaklardan" : "Bugün tarama yapılmadı"} />
        <Stat label="Son 7 gün kuruluş" value={m.last7_established} href="/businesses?range=7" />
        <Stat label="Son 30 gün kuruluş" value={m.last30_established} href="/businesses?range=30" />
        <Stat label="İletişim bilgisi bulunan" value={m.with_contact} href="/businesses?has_contact=true" />
        <Stat label="Yüksek İSG potansiyeli" value={m.high_isg} href="/businesses?isg_min=60" hint="Puan ≥ 60" />
        <Stat label="Yüksek yazılım potansiyeli" value={m.high_software} href="/businesses?software_min=60" hint="Puan ≥ 60" />
        <Stat label="Henüz iletişime geçilmemiş" value={m.not_contacted} href="/businesses?sales_status=yeni&sales_status=arastiriliyor&sales_status=iletisime_hazir" />
        <Stat label="Teklif verilen" value={m.quoted} href="/businesses?stage=teklif_gonderildi" />
        <Stat label="Kazanılan müşteri" value={m.won} tone="good" href="/businesses?stage=kazanildi" />
        <Stat label="Toplam aktif kayıt" value={m.total_active} href="/businesses" />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Son 14 gün tarama kapsamı" className="lg:col-span-2">
          <div className="flex flex-wrap gap-1.5">
            {data.coverage.map((c: Coverage) => (
              <div key={c.date} className="flex w-12 flex-col items-center gap-1" title={`${fmtDate(c.date)} – ${COV[c.status].label}`}>
                <div className={`flex h-10 w-10 items-center justify-center rounded-md text-xs font-bold text-white ${COV[c.status].cls} ${c.weekend ? "opacity-60" : ""}`}>
                  {c.new_businesses ?? "–"}
                </div>
                <span className="text-[10px] text-slate-500">{c.date.slice(8, 10)}.{c.date.slice(5, 7)}</span>
              </div>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-600">
            {Object.entries(COV).map(([k, v]) => (
              <span key={k} className="inline-flex items-center gap-1"><span className={`h-2.5 w-2.5 rounded-sm ${v.cls}`} />{v.label}</span>
            ))}
            <span>· Kutudaki sayı: o gün kaynaklardan tespit edilen yeni kuruluş. "–" = tarama yok.</span>
          </div>
        </Card>
        <Card title="Veri kaynakları">
          <ul className="space-y-2 text-sm">
            {data.sources.map((s: any) => (
              <li key={s.key} className="flex items-start justify-between gap-2">
                <span className="text-slate-700">{s.name}</span>
                <Badge tone={s.enabled ? HEALTH[s.health]?.tone : "slate"}>{s.enabled ? HEALTH[s.health]?.label : "Kapalı"}</Badge>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Öncelikli adaylar (henüz görüşülmemiş)" className="lg:col-span-2"
          actions={<Link href="/businesses" className="text-sm text-brand-600">Tümü →</Link>}>
          {data.top_leads.length === 0 ? <p className="text-sm text-slate-500">Kayıt yok.</p> : (
            <Table head={["İşletme", "İlçe", "Tarih", "İSG", "Yazılım", "Öncelik"]}>
              {data.top_leads.map((b: any) => (
                <tr key={b.id} className="hover:bg-slate-50">
                  <Td><Link className="font-medium text-brand-700 hover:underline" href={`/businesses/${b.id}`}>{b.trade_name}</Link></Td>
                  <Td>{b.district || "—"}</Td>
                  <Td>{fmtDate(b.establishment_date)}</Td>
                  <Td><Score value={b.isg_score} /></Td>
                  <Td><Score value={b.software_score} /></Td>
                  <Td><Badge tone={b.priority === "A" ? "green" : b.priority === "B" ? "amber" : "slate"}>{b.priority || "—"}</Badge></Td>
                </tr>
              ))}
            </Table>
          )}
        </Card>
        <Card title="Satış hunisi">
          {data.funnel.map((f: any) => (
            <div key={f.service_line} className="mb-4">
              <div className="mb-1 text-xs font-semibold uppercase text-slate-500">{f.service_line === "isg" ? "İSG" : "Yazılım"}</div>
              {f.stages.map((s: any) => (
                <div key={s.stage} className="flex justify-between border-b border-slate-50 py-0.5 text-sm">
                  <span className="text-slate-600">{s.label}</span><span className="font-semibold tabular-nums">{s.count}</span>
                </div>
              ))}
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}
