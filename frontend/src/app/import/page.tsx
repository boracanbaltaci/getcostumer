"use client";

import Link from "next/link";
import { useState } from "react";
import { Alert, Badge, Button, Card, Field, Input, PageHeader, Table, Td } from "@/components/ui";
import { api, download, fmtDateTime } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/hooks";

const STAT_LABELS: Record<string, string> = {
  created: "Yeni işletme", updated: "Mevcut kayıt güncellendi", duplicate_business: "Mükerrer (mevcut işletme)",
  duplicate_raw: "Daha önce işlenmiş", skipped_not_establishment: "Kuruluş dışı (şube/değişiklik vb.)",
  skipped_other_province: "Ankara dışı", needs_review: "İnceleme bekliyor", total_rows: "Toplam satır/ilan",
  contacts_added: "Eklenen iletişim bilgisi",
};

export default function ImportPage() {
  const { can } = useAuth();
  const history = useApi<any[]>("/imports");
  const nace = useApi<any>("/nace-hazard/stats");
  const [file, setFile] = useState<File | null>(null);
  const [declared, setDeclared] = useState(true);
  const [fullDay, setFullDay] = useState(false);
  const [gDate, setGDate] = useState("");
  const [gNo, setGNo] = useState("");
  const [preview, setPreview] = useState<any>(null);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function form(extra: Record<string, string> = {}) {
    const fd = new FormData();
    fd.append("file", file as File);
    Object.entries(extra).forEach(([k, v]) => fd.append(k, v));
    return fd;
  }

  async function doPreview() {
    if (!file) return;
    setError(null); setPreview(null);
    try { setPreview(await api("/imports/preview", { method: "POST", body: form() })); } catch (e: any) { setError(e.message); }
  }

  async function doImport() {
    if (!file) return;
    setBusy(true); setError(null); setResult(null);
    try {
      const extra: Record<string, string> = { declared_establishment: String(declared), full_day: String(fullDay) };
      if (gDate) extra.gazette_date = gDate;
      if (gNo) extra.gazette_no = gNo;
      setResult(await api("/imports", { method: "POST", body: form(extra) }));
      history.reload();
    } catch (e: any) { setError(e.message); } finally { setBusy(false); }
  }

  async function uploadNace(f: File) {
    const fd = new FormData(); fd.append("file", f);
    try { const r = await api("/imports/nace-hazard", { method: "POST", body: fd }); alert(`${r.imported} satır yüklendi`); nace.reload(); }
    catch (e: any) { alert(e.message); }
  }

  return (
    <div className="space-y-4">
      <PageHeader title="İçe Aktar" subtitle="CSV, Excel (XLSX) veya PDF" actions={
        <Button variant="secondary" onClick={() => download("/import-template.xlsx", "ice-aktarma-sablonu.xlsx")}>Excel şablonu indir</Button>} />

      <Alert tone="blue">
        Yalnızca hukuka uygun yoldan edindiğiniz dosyaları yükleyin: TOBB'dan satın alınan günlük elektronik gazete / fihrist,
        veri aboneliği dosyaları, TTSG üyeliğiyle görüntüleyip indirdiğiniz ilan PDF'leri veya oda/sicil müdürlüğünden yazılı
        talep ile alınan listeler. Sistem şube, adres/unvan değişikliği ve sermaye artırımı ilanlarını otomatik ayıklar.
      </Alert>

      <Card title="Dosya yükle">
        <div className="space-y-3">
          <input type="file" accept=".csv,.xlsx,.xlsm,.pdf,.txt" onChange={(e) => { setFile(e.target.files?.[0] || null); setPreview(null); setResult(null); }}
            className="block w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-brand-600 file:px-3 file:py-1.5 file:text-white" />
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={declared} onChange={(e) => setDeclared(e.target.checked)} className="mt-1" />
            <span>Dosyada <b>ilan türü sütunu yoksa</b> satırlar yeni kuruluş kaydıdır (beyan ediyorum). İlan türü varsa her zaman ona göre filtrelenir.</span>
          </label>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={fullDay} onChange={(e) => setFullDay(e.target.checked)} className="mt-1" />
            <span>Bu dosya ilgili yayın gününün <b>tam</b> gazetesi/fihristidir (o gün "tarandı" olarak işaretlensin).</span>
          </label>
          <div className="grid max-w-lg grid-cols-2 gap-2">
            <Field label="Gazete tarihi (dosyada yoksa)"><Input type="date" value={gDate} onChange={(e) => setGDate(e.target.value)} /></Field>
            <Field label="Gazete sayısı"><Input value={gNo} onChange={(e) => setGNo(e.target.value)} /></Field>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" disabled={!file} onClick={doPreview}>Önizle</Button>
            <Button disabled={!file || busy} onClick={doImport}>{busy ? "İçe aktarılıyor…" : "İçe aktar"}</Button>
          </div>
          {error && <Alert tone="red">{error}</Alert>}
          {preview && (
            <div className="text-sm">
              {preview.type === "tabular" && (
                <div className="mb-2"><b>Eşlenen sütunlar:</b> {Object.entries(preview.columns).map(([k, v]: any) => <Badge key={k}>{k} → {v}</Badge>)}</div>
              )}
              <pre className="max-h-72 overflow-auto rounded bg-slate-50 p-2 text-xs">{JSON.stringify(preview.sample, null, 2)}</pre>
            </div>
          )}
          {result && (
            <Alert tone={result.status === "completed" ? "green" : "red"}>
              <div className="font-semibold">{result.status === "completed" ? "İçe aktarma tamamlandı" : "İçe aktarma başarısız"}</div>
              <ul className="mt-1 text-xs">{Object.entries(result.stats).map(([k, v]: any) => <li key={k}>{STAT_LABELS[k] || k}: <b>{v}</b></li>)}</ul>
              {result.stats.needs_review > 0 && <Link className="text-xs underline" href="/review">İnceleme kuyruğuna git →</Link>}
              {result.errors?.length > 0 && <details className="mt-1 text-xs"><summary>Uyarılar / hatalar ({result.errors.length})</summary>
                <pre className="whitespace-pre-wrap">{JSON.stringify(result.errors.slice(0, 50), null, 2)}</pre></details>}
            </Alert>
          )}
        </div>
      </Card>

      {can("manager") && (
        <Card title="İşyeri tehlike sınıfları listesi (resmî)">
          <p className="mb-2 text-sm text-slate-600">
            İSG puanlamasının tehlike sınıfını kesinleştirmek için Çalışma ve Sosyal Güvenlik Bakanlığı'nın "İş Sağlığı ve Güvenliğine
            İlişkin İşyeri Tehlike Sınıfları Tebliği" ekindeki NACE listesini (sütunlar: NACE Kodu, Tanım, Tehlike Sınıfı) yükleyin.
            Yüklenmezse tehlike sınıfı NACE bölümüne göre <b>tahmini</b> olarak gösterilir.
          </p>
          <div className="flex items-center gap-3 text-sm">
            <span>Yüklü kod sayısı: <b>{nace.data?.rows ?? "…"}</b></span>
            <input type="file" accept=".xlsx,.csv" onChange={(e) => e.target.files?.[0] && uploadNace(e.target.files[0])} className="text-sm" />
          </div>
        </Card>
      )}

      <Card title="İçe aktarma geçmişi">
        <Table head={["Tarih", "Dosya", "Kaynak", "Durum", "Sonuç"]}>
          {(history.data || []).map((b) => (
            <tr key={b.id}>
              <Td className="whitespace-nowrap">{fmtDateTime(b.created_at)}</Td>
              <Td>{b.filename}</Td><Td>{b.source}</Td>
              <Td><Badge tone={b.status === "completed" ? "green" : b.status === "failed" ? "red" : "amber"}>{b.status}</Badge></Td>
              <Td className="text-xs">{Object.entries(b.stats || {}).filter(([, v]) => v).map(([k, v]) => `${STAT_LABELS[k] || k}: ${v}`).join(" · ")}</Td>
            </tr>
          ))}
        </Table>
      </Card>
    </div>
  );
}
