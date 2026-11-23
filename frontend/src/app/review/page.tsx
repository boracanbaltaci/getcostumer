"use client";

import Link from "next/link";
import { useState } from "react";
import { Alert, Badge, Button, Card, Empty, Field, Input, PageHeader, Select, Spinner } from "@/components/ui";
import { api, fmtDateTime } from "@/lib/api";
import { useApi, useMeta } from "@/lib/hooks";

export default function ReviewPage() {
  const [status, setStatus] = useState("needs_review");
  const { data, reload } = useApi<any[]>(`/review?status=${status}`, [status]);
  return (
    <div className="space-y-4">
      <PageHeader title="İnceleme Kuyruğu" subtitle="Otomatik olarak yeni kuruluş veya Ankara kaydı olduğu doğrulanamayan kayıtlar" actions={
        <Select value={status} onChange={(e) => setStatus(e.target.value)} className="max-w-xs">
          <option value="needs_review">İnceleme bekleyenler</option>
          <option value="skipped_not_establishment">Kuruluş dışı ayıklananlar</option>
          <option value="skipped_other_province">Ankara dışı ayıklananlar</option>
          <option value="rejected">Reddedilenler</option>
        </Select>} />
      <Alert tone="blue">Kaydı onaylamadan önce kaynağındaki ilan metnini okuyun. Onaylanan kayıt "manuel doğrulandı" olarak işaretlenir. Emin değilseniz reddedin; sistem tahminle kayıt oluşturmaz.</Alert>
      {!data ? <Spinner /> : data.length === 0 ? <Card><Empty>Bu durumda kayıt yok.</Empty></Card> :
        data.map((r) => <ReviewItem key={r.id} r={r} onDone={reload} editable={status === "needs_review"} />)}
    </div>
  );
}

function ReviewItem({ r, onDone, editable }: { r: any; onDone: () => void; editable: boolean }) {
  const meta = useMeta();
  const p = r.payload || {};
  const [f, setF] = useState({ trade_name: p.trade_name || "", district: p.district || "", registry_no: p.registry_no || "",
    mersis_no: p.mersis_no || "", establishment_date: p.establishment_date || "", address: p.address || "" });
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  if (done) return <Alert tone="green">{done}</Alert>;
  return (
    <Card title={<>{p.trade_name || "Unvan ayrıştırılamadı"} <span className="font-normal text-slate-500">#{r.id}</span></>}
      actions={<><Badge tone="amber">{r.skip_reason}</Badge><span className="text-xs text-slate-500">{fmtDateTime(r.fetched_at)}</span></>}>
      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <div className="mb-1 text-xs font-medium text-slate-500">Kaynak metni / alanlar</div>
          {r.raw_text ? <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs">{r.raw_text}</pre>
            : <pre className="max-h-64 overflow-auto rounded bg-slate-50 p-2 text-xs">{JSON.stringify(p, null, 2)}</pre>}
        </div>
        {editable && (
          <div className="space-y-2">
            <Field label="Ticaret unvanı"><Input value={f.trade_name} onChange={(e) => setF({ ...f, trade_name: e.target.value })} /></Field>
            <div className="grid grid-cols-2 gap-2">
              <Field label="İlçe"><Select value={f.district} onChange={(e) => setF({ ...f, district: e.target.value })}>
                <option value="">—</option>{meta?.districts.map((d) => <option key={d}>{d}</option>)}</Select></Field>
              <Field label="Kuruluş tarihi"><Input type="date" value={f.establishment_date} onChange={(e) => setF({ ...f, establishment_date: e.target.value })} /></Field>
              <Field label="Sicil no"><Input value={f.registry_no} onChange={(e) => setF({ ...f, registry_no: e.target.value })} /></Field>
              <Field label="MERSİS no"><Input value={f.mersis_no} onChange={(e) => setF({ ...f, mersis_no: e.target.value })} /></Field>
            </div>
            <Field label="Adres"><Input value={f.address} onChange={(e) => setF({ ...f, address: e.target.value })} /></Field>
            {err && <p className="text-xs text-red-600">{err}</p>}
            <div className="flex gap-2">
              <Button onClick={() => {
                const fields: any = { ...f, province: "Ankara" };
                Object.keys(fields).forEach((k) => { if (fields[k] === "") delete fields[k]; });
                api(`/review/${r.id}/approve`, { method: "POST", json: { fields } })
                  .then((b) => setDone(`Onaylandı: ${b.trade_name}`)).catch((e) => setErr(e.message));
              }}>Yeni kuruluş olarak onayla</Button>
              <Button variant="secondary" onClick={() => api(`/review/${r.id}/reject`, { method: "POST" }).then(() => { setDone("Reddedildi"); onDone(); })}>Reddet</Button>
            </div>
          </div>
        )}
        {r.business_id && <Link href={`/businesses/${r.business_id}`} className="text-sm text-brand-600 underline">İşletmeye git</Link>}
      </div>
    </Card>
  );
}
