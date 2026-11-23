"use client";

import Link from "next/link";
import { useState } from "react";
import { Badge, Button, Card, Empty, PageHeader, Select, Spinner, Table, Td } from "@/components/ui";
import { api, fmtDate } from "@/lib/api";
import { useApi } from "@/lib/hooks";

export default function RemindersPage() {
  const [days, setDays] = useState(7);
  const [mine, setMine] = useState(false);
  const { data, reload } = useApi<any[]>(`/reminders?days=${days}&mine=${mine}`, [days, mine]);
  return (
    <div className="space-y-4">
      <PageHeader title="Takipler ve Hatırlatmalar" subtitle="Görüşme takipleri ve fırsatların sonraki aksiyonları" actions={<>
        <Select value={days} onChange={(e) => setDays(Number(e.target.value))} className="max-w-[160px]">
          <option value={0}>Bugün ve gecikmiş</option><option value={7}>7 gün</option><option value={30}>30 gün</option></Select>
        <Select value={mine ? "1" : "0"} onChange={(e) => setMine(e.target.value === "1")} className="max-w-[140px]">
          <option value="0">Tüm ekip</option><option value="1">Benimkiler</option></Select></>} />
      <Card>
        {!data ? <Spinner /> : data.length === 0 ? <Empty>Bu aralıkta takip yok.</Empty> : (
          <Table head={["Tarih", "İşletme", "Tür", "Aksiyon", ""]}>
            {data.map((r) => (
              <tr key={`${r.kind}-${r.id}`} className={r.overdue ? "bg-red-50" : ""}>
                <Td className="whitespace-nowrap">{fmtDate(r.date)} {r.overdue && <Badge tone="red">gecikmiş</Badge>}</Td>
                <Td><Link className="text-brand-700 hover:underline" href={`/businesses/${r.business_id}`}>{r.business}</Link></Td>
                <Td>{r.kind === "activity" ? "Görüşme takibi" : r.service_line === "isg" ? "İSG fırsatı" : "Yazılım fırsatı"}</Td>
                <Td className="text-sm">{r.text}</Td>
                <Td>{r.kind === "activity" && <Button variant="ghost" onClick={() => api(`/activities/${r.id}`, { method: "PATCH", json: { follow_up_done: true } }).then(reload)}>Tamamlandı</Button>}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
