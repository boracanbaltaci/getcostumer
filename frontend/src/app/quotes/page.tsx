"use client";

import Link from "next/link";
import { useState } from "react";
import { Badge, Card, Empty, PageHeader, Select, Spinner, Table, Td } from "@/components/ui";
import { download, fmtDate, fmtMoney } from "@/lib/api";
import { useApi } from "@/lib/hooks";

const ST: Record<string, { l: string; t: string }> = {
  taslak: { l: "Taslak", t: "slate" }, gonderildi: { l: "Gönderildi", t: "blue" }, kabul: { l: "Kabul", t: "green" }, red: { l: "Red", t: "red" },
};

export default function QuotesPage() {
  const [status, setStatus] = useState("");
  const { data } = useApi<any[]>(`/quotes${status ? `?status=${status}` : ""}`, [status]);
  return (
    <div className="space-y-4">
      <PageHeader title="Teklifler" actions={
        <Select value={status} onChange={(e) => setStatus(e.target.value)} className="max-w-[180px]">
          <option value="">Tümü</option>{Object.entries(ST).map(([k, v]) => <option key={k} value={k}>{v.l}</option>)}</Select>} />
      <Card>
        {!data ? <Spinner /> : data.length === 0 ? <Empty>Teklif yok. Teklifler işletme detayındaki fırsat kartlarından oluşturulur.</Empty> : (
          <Table head={["No", "İşletme", "Konu", "Toplam", "Geçerlilik", "Durum", ""]}>
            {data.map((q) => (
              <tr key={q.id}>
                <Td className="whitespace-nowrap font-mono text-xs">{q.number}</Td>
                <Td><Link className="text-brand-700 hover:underline" href={`/businesses/${q.business_id}`}>{q.business}</Link></Td>
                <Td>{q.title}</Td>
                <Td className="whitespace-nowrap">{fmtMoney(q.total, q.currency)}</Td>
                <Td>{fmtDate(q.valid_until)}</Td>
                <Td><Badge tone={ST[q.status]?.t}>{ST[q.status]?.l || q.status}</Badge></Td>
                <Td><button className="text-sm text-brand-600 underline" onClick={() => download(`/quotes/${q.id}/pdf`, `${q.number}.pdf`)}>PDF</button></Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
