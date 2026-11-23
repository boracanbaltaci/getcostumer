"use client";

import Link from "next/link";
import { useState } from "react";
import { Alert, Button, Card, Empty, PageHeader, Select, Spinner, Table, Td } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/hooks";

export default function MergePage() {
  const { can } = useAuth();
  const [th, setTh] = useState(90);
  const { data, reload } = useApi<any[]>(`/businesses/merge-candidates?threshold=${th}`, [th]);
  const [msg, setMsg] = useState<string | null>(null);

  async function merge(source: number, target: number) {
    if (!confirm(`#${source} kaydı #${target} içine birleştirilecek. Görüşmeler, teklifler ve iletişim bilgileri taşınır. Devam?`)) return;
    try { await api("/businesses/merge", { method: "POST", json: { source_id: source, target_id: target } }); setMsg("Birleştirildi"); reload(); }
    catch (e: any) { setMsg(e.message); }
  }

  return (
    <div className="space-y-4">
      <PageHeader title="Mükerrer Eşleştirme" subtitle="Benzer unvanlı kayıtlar. Farklı MERSİS/sicil numaralı kayıtlar listelenmez." actions={
        <Select value={th} onChange={(e) => setTh(Number(e.target.value))} className="max-w-[200px]">
          {[95, 90, 85, 80].map((v) => <option key={v} value={v}>Benzerlik ≥ %{v}</option>)}</Select>} />
      {msg && <Alert tone="blue">{msg}</Alert>}
      <Card>
        {!data ? <Spinner /> : data.length === 0 ? <Empty>Eşleştirme adayı yok.</Empty> : (
          <Table head={["Kayıt A", "Kayıt B", "Benzerlik", ""]}>
            {data.map((p, i) => (
              <tr key={i}>
                <Td><Link className="text-brand-700 hover:underline" href={`/businesses/${p.a.id}`}>#{p.a.id} {p.a.trade_name}</Link><div className="text-xs text-slate-500">{p.a.district} · MERSİS {p.a.mersis_no || "—"}</div></Td>
                <Td><Link className="text-brand-700 hover:underline" href={`/businesses/${p.b.id}`}>#{p.b.id} {p.b.trade_name}</Link><div className="text-xs text-slate-500">{p.b.district} · MERSİS {p.b.mersis_no || "—"}</div></Td>
                <Td>%{p.similarity}</Td>
                <Td>{can("manager") && <div className="flex flex-col gap-1">
                  <Button variant="secondary" onClick={() => merge(p.b.id, p.a.id)}>B → A</Button>
                  <Button variant="secondary" onClick={() => merge(p.a.id, p.b.id)}>A → B</Button></div>}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
