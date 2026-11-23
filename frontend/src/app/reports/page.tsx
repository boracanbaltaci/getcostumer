"use client";

import Link from "next/link";
import { Fragment, useState } from "react";
import { Alert, Badge, Button, Card, Field, Input, PageHeader, Spinner, Table, Td } from "@/components/ui";
import { api, download, fmtDate, fmtDateTime, fmtMoney, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/hooks";

function monthStart() {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), 1).toLocaleDateString("sv-SE");
}

export default function ReportsPage() {
  const { can } = useAuth();
  const [start, setStart] = useState(monthStart());
  const [end, setEnd] = useState(new Date().toLocaleDateString("sv-SE"));
  const sales = useApi<any>(`/reports/sales${qs({ start, end })}`, [start, end]);
  const daily = useApi<any[]>("/reports/daily?limit=30");
  const [open, setOpen] = useState<string | null>(null);

  return (
    <div className="space-y-4">
      <PageHeader title="Raporlar" />
      <Card title="Satış raporu" actions={<Button variant="secondary" onClick={() => download(`/reports/sales.xlsx${qs({ start, end })}`, "satis-raporu.xlsx")}>Excel</Button>}>
        <div className="mb-4 flex flex-wrap gap-2">
          <Field label="Başlangıç"><Input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></Field>
          <Field label="Bitiş"><Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></Field>
        </div>
        {!sales.data ? <Spinner /> : (
          <div className="grid gap-4 md:grid-cols-3">
            <div>
              <div className="text-xs uppercase text-slate-500">Tespit edilen işletme</div>
              <div className="text-2xl font-bold">{sales.data.detected}</div>
              <div className="mt-3 text-xs uppercase text-slate-500">Kazanılan</div>
              {sales.data.won.length === 0 ? <div className="text-sm text-slate-500">—</div> : sales.data.won.map((w: any) => (
                <div key={w.service_line} className="text-sm">{w.service_line === "isg" ? "İSG" : "Yazılım"}: <b>{w.count}</b> · {fmtMoney(w.value)}</div>))}
              <div className="mt-3 text-xs uppercase text-slate-500">Teklifler</div>
              {sales.data.quotes.map((q: any) => <div key={q.status} className="text-sm">{q.status}: {q.count} · {fmtMoney(q.total)}</div>)}
            </div>
            <div>
              <div className="mb-1 text-xs uppercase text-slate-500">İlçelere göre (tespit)</div>
              {sales.data.by_district.slice(0, 12).map((d: any) => <div key={d.district} className="flex justify-between text-sm"><span>{d.district}</span><b>{d.count}</b></div>)}
            </div>
            <div>
              <div className="mb-1 text-xs uppercase text-slate-500">Sektörlere göre (tespit)</div>
              {sales.data.by_sector.slice(0, 12).map((d: any) => <div key={d.sector} className="flex justify-between text-sm"><span>{d.sector}</span><b>{d.count}</b></div>)}
            </div>
          </div>
        )}
      </Card>
      <Card title="Günlük özetler" actions={can("manager") ? <Button variant="secondary" onClick={() => api("/reports/daily/rebuild", { method: "POST" }).then(daily.reload)}>Bugünün özetini yeniden oluştur</Button> : undefined}>
        {!daily.data ? <Spinner /> : (
          <Table head={["Tarih", "Yeni", "İletişimli", "Yüksek İSG", "Yüksek yazılım", "Uyarı", ""]}>
            {daily.data.map((r) => (
              <Fragment key={r.date}>
                <tr>
                  <Td>{fmtDate(r.date)}</Td><Td>{r.content.new_businesses}</Td><Td>{r.content.with_contact}</Td>
                  <Td>{r.content.high_isg}</Td><Td>{r.content.high_software}</Td>
                  <Td>{r.content.warnings?.length ? <Badge tone="amber">{r.content.warnings.length}</Badge> : <Badge tone="green">yok</Badge>}</Td>
                  <Td><Button variant="ghost" onClick={() => setOpen(open === r.date ? null : r.date)}>{open === r.date ? "Kapat" : "Ayrıntı"}</Button></Td>
                </tr>
                {open === r.date && (
                  <tr><td colSpan={7} className="bg-slate-50 p-3">
                    {r.content.warnings?.map((w: string, i: number) => <Alert key={i}>{w}</Alert>)}
                    <div className="mt-2 text-sm">
                      {r.content.top?.map((t: any) => <div key={t.id}><Link className="text-brand-700 underline" href={`/businesses/${t.id}`}>{t.trade_name}</Link> · {t.district || "—"} · İSG {t.isg ?? "-"} / Yazılım {t.software ?? "-"}</div>)}
                    </div>
                    <div className="mt-1 text-xs text-slate-500">Bildirim: {r.sent_at ? fmtDateTime(r.sent_at) : "gönderilmedi"}</div>
                  </td></tr>
                )}
              </Fragment>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
