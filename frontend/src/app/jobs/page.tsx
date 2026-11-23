"use client";

import { useState } from "react";
import { Alert, Badge, Button, Card, JOB_STATUS, PageHeader, Spinner, Table, Td } from "@/components/ui";
import { api, fmtDateTime } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/hooks";

const TYPES: Record<string, string> = { daily_pipeline: "Günlük tarama", enrich_and_score: "Araştırma + analiz", inbox_check: "Klasör kontrolü" };

export default function JobsPage() {
  const { can } = useAuth();
  const { data, reload } = useApi<any[]>("/jobs");
  const [detail, setDetail] = useState<any>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function run(kind: string) {
    setMsg(null);
    try {
      const r = await api(`/jobs/${kind}${kind === "retention" ? "?dry_run=true" : ""}`, { method: "POST" });
      setMsg(kind === "retention" ? `Saklama süresi dolan: ${r.uncontacted} (iletişimsiz), ${r.lost} (olumsuz) – deneme çalıştırması, silme yapılmadı`
        : `Görev başlatıldı (${r.mode === "queued" ? "kuyruk" : "süreç içi"}). Birkaç saniye sonra listeyi yenileyin.`);
      setTimeout(reload, 2500);
    } catch (e: any) { setMsg(e.message); }
  }

  return (
    <div className="space-y-4">
      <PageHeader title="Zamanlanmış Görevler" subtitle="Günlük tarama her gün 08:30'da (Türkiye saati) çalışır" actions={can("manager") ? <>
        <Button onClick={() => run("daily")}>Günlük taramayı şimdi çalıştır</Button>
        <Button variant="secondary" onClick={() => run("enrich_and_score")}>Araştırma + analiz</Button>
        {can("admin") && <Button variant="secondary" onClick={() => run("retention")}>KVKK saklama (deneme)</Button>}
        <Button variant="ghost" onClick={reload}>Yenile</Button></> : undefined} />
      {msg && <Alert tone="blue">{msg}</Alert>}
      <Card>
        {!data ? <Spinner /> : (
          <Table head={["Başlangıç", "Görev", "Tetikleyen", "Durum", "Özet", ""]}>
            {data.map((j) => (
              <tr key={j.id}>
                <Td className="whitespace-nowrap">{fmtDateTime(j.started_at)}</Td>
                <Td>{TYPES[j.job_type] || j.job_type}</Td>
                <Td className="text-xs">{j.triggered_by}</Td>
                <Td><Badge tone={JOB_STATUS[j.status]?.tone}>{JOB_STATUS[j.status]?.label || j.status}</Badge></Td>
                <Td className="text-xs">
                  {j.stats?.created !== undefined && <>Yeni: <b>{j.stats.created}</b> · </>}
                  {j.stats?.sources && Object.entries(j.stats.sources).map(([k, v]: any) => `${k}: ${v.status}`).join(" · ")}
                  {j.error && <div className="text-red-600">{j.error.slice(0, 160)}</div>}
                </Td>
                <Td><Button variant="ghost" onClick={() => api(`/jobs/${j.id}`).then(setDetail)}>Günlük</Button></Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
      {detail && (
        <Card title={`Görev #${detail.id} günlüğü`} actions={<Button variant="ghost" onClick={() => setDetail(null)}>Kapat</Button>}>
          <pre className="max-h-[480px] overflow-auto whitespace-pre-wrap text-xs">{(detail.log || []).join("\n") || "Günlük yok"}</pre>
          <details className="mt-2 text-xs"><summary>İstatistikler (JSON)</summary><pre className="whitespace-pre-wrap">{JSON.stringify(detail.stats, null, 2)}</pre></details>
        </Card>
      )}
    </div>
  );
}
