"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Badge, Button, Card, Empty, Field, Input, NotFound, PageHeader, Score, Select, Spinner, StageBadge, Table, Td } from "@/components/ui";
import { api, download, fmtDate, qs } from "@/lib/api";
import { useMeta } from "@/lib/hooks";

type Filters = {
  q: string; district: string[]; date_from: string; date_to: string; sector: string; company_type: string;
  isg_min: string; software_min: string; has_contact: string; sales_status: string[]; stage: string;
  service_line: string; priority: string; detected_from: string; sort: string;
};

const EMPTY: Filters = { q: "", district: [], date_from: "", date_to: "", sector: "", company_type: "", isg_min: "",
  software_min: "", has_contact: "", sales_status: [], stage: "", service_line: "", priority: "", detected_from: "",
  sort: "-total_score" };

function isoDaysAgo(n: number) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

function fromUrl(): Filters {
  if (typeof window === "undefined") return EMPTY;
  const sp = new URLSearchParams(window.location.search);
  const f: Filters = { ...EMPTY };
  (Object.keys(EMPTY) as (keyof Filters)[]).forEach((k) => {
    if (Array.isArray(EMPTY[k])) (f as any)[k] = sp.getAll(k);
    else if (sp.get(k)) (f as any)[k] = sp.get(k);
  });
  if (sp.get("range")) f.date_from = isoDaysAgo(Number(sp.get("range")) - 1);
  if (sp.get("today")) f.detected_from = isoDaysAgo(0);
  return f;
}

export default function BusinessesPage() {
  const meta = useMeta();
  const [filters, setFilters] = useState<Filters>(EMPTY);
  const [ready, setReady] = useState(false);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => { setFilters(fromUrl()); setReady(true); }, []);

  const query = useMemo(() => qs({ ...filters, has_contact: filters.has_contact || undefined }), [filters]);

  useEffect(() => {
    if (!ready) return;
    setError(null);
    api(`/businesses${query}${query ? "&" : "?"}page=${page}&page_size=50`).then(setData).catch((e) => setError(e.message));
    window.history.replaceState(null, "", `/businesses${query}`);
  }, [query, page, ready]);

  const set = (k: keyof Filters, v: any) => { setPage(1); setFilters((f) => ({ ...f, [k]: v })); };
  const toggleDistrict = (d: string) => set("district", filters.district.includes(d) ? filters.district.filter((x) => x !== d) : [...filters.district, d]);

  return (
    <div>
      <PageHeader title="İşletmeler" subtitle={data ? `${data.total} kayıt` : undefined} actions={<>
        <Button variant="secondary" onClick={() => download(`/exports/businesses.xlsx${query}`, "isletmeler.xlsx")}>Excel</Button>
        <Button variant="secondary" onClick={() => download(`/exports/businesses.csv${query}`, "isletmeler.csv")}>CSV</Button>
        <Button variant="secondary" onClick={() => download(`/exports/businesses.pdf${query}`, "isletmeler.pdf")}>PDF</Button>
      </>} />

      <Card className="mb-4">
        <div className="flex flex-wrap gap-2">
          <Input placeholder="Unvan, MERSİS veya sicil no ara…" value={filters.q} onChange={(e) => set("q", e.target.value)} className="max-w-md" />
          <Select value={filters.sort} onChange={(e) => set("sort", e.target.value)} className="max-w-[220px]">
            <option value="-total_score">Toplam potansiyel (yüksek→düşük)</option>
            <option value="-isg_score">İSG puanı</option>
            <option value="-software_score">Yazılım puanı</option>
            <option value="-establishment_date">Kuruluş tarihi (yeni→eski)</option>
            <option value="-first_seen_at">Tespit tarihi (yeni→eski)</option>
            <option value="trade_name">Unvan (A→Z)</option>
          </Select>
          <Button variant="secondary" onClick={() => setShowFilters((s) => !s)}>{showFilters ? "Filtreleri gizle" : "Filtreler"}</Button>
          <Button variant="ghost" onClick={() => { setFilters(EMPTY); setPage(1); }}>Temizle</Button>
        </div>
        {showFilters && meta && (
          <div className="mt-4 space-y-4">
            <div>
              <div className="mb-1 text-xs font-medium text-slate-600">İlçe</div>
              <div className="flex flex-wrap gap-1">
                {meta.districts.map((d) => (
                  <button key={d} onClick={() => toggleDistrict(d)}
                    className={`rounded-full border px-2 py-0.5 text-xs ${filters.district.includes(d) ? "border-brand-600 bg-brand-600 text-white" : "border-slate-300 bg-white text-slate-700"}`}>{d}</button>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
              <Field label="Kuruluş tarihi (başlangıç)"><Input type="date" value={filters.date_from} onChange={(e) => set("date_from", e.target.value)} /></Field>
              <Field label="Kuruluş tarihi (bitiş)"><Input type="date" value={filters.date_to} onChange={(e) => set("date_to", e.target.value)} /></Field>
              <Field label="Sektör"><Select value={filters.sector} onChange={(e) => set("sector", e.target.value)}>
                <option value="">Tümü</option>{meta.sectors.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}</Select></Field>
              <Field label="Şirket türü"><Select value={filters.company_type} onChange={(e) => set("company_type", e.target.value)}>
                <option value="">Tümü</option>{meta.company_types.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}</Select></Field>
              <Field label="Min. İSG puanı"><Input type="number" min={0} max={100} value={filters.isg_min} onChange={(e) => set("isg_min", e.target.value)} /></Field>
              <Field label="Min. yazılım puanı"><Input type="number" min={0} max={100} value={filters.software_min} onChange={(e) => set("software_min", e.target.value)} /></Field>
              <Field label="İletişim bilgisi"><Select value={filters.has_contact} onChange={(e) => set("has_contact", e.target.value)}>
                <option value="">Tümü</option><option value="true">Mevcut</option><option value="false">Bulunamadı</option></Select></Field>
              <Field label="Görüşme durumu (genel)"><Select value={filters.sales_status[0] || ""} onChange={(e) => set("sales_status", e.target.value ? [e.target.value] : [])}>
                <option value="">Tümü</option>{meta.stages.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}</Select></Field>
              <Field label="Hizmet hattı"><Select value={filters.service_line} onChange={(e) => set("service_line", e.target.value)}>
                <option value="">İkisi de</option><option value="isg">İSG</option><option value="yazilim">Yazılım</option></Select></Field>
              <Field label="Hizmet aşaması"><Select value={filters.stage} onChange={(e) => set("stage", e.target.value)}>
                <option value="">Tümü</option>{meta.stages.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}</Select></Field>
              <Field label="Öncelik"><Select value={filters.priority} onChange={(e) => set("priority", e.target.value)}>
                <option value="">Tümü</option><option value="A">A</option><option value="B">B</option><option value="C">C</option></Select></Field>
              <Field label="Tespit tarihi (itibaren)"><Input type="date" value={filters.detected_from} onChange={(e) => set("detected_from", e.target.value)} /></Field>
            </div>
          </div>
        )}
      </Card>

      {error && <p className="mb-2 text-sm text-red-600">{error}</p>}
      <Card>
        {!data ? <Spinner /> : data.items.length === 0 ? <Empty>Filtrelere uyan işletme yok.</Empty> : (
          <Table head={["İşletme", "İlçe", "Kuruluş", "Telefon", "E-posta / Web", "İSG", "Yazılım", "Durum"]}>
            {data.items.map((b: any) => (
              <tr key={b.id} className="hover:bg-slate-50">
                <Td>
                  <Link href={`/businesses/${b.id}`} className="font-medium text-brand-700 hover:underline">{b.trade_name}</Link>
                  <div className="mt-0.5 flex flex-wrap gap-1">
                    {b.company_type_label && <Badge>{b.company_type_label}</Badge>}
                    {b.sector_label && <Badge tone="blue" title={b.sector_basis === "metin_tahmini" ? "Faaliyet metninden tahmini" : "NACE"}>{b.sector_label}{b.sector_basis === "metin_tahmini" ? " (tahmini)" : ""}</Badge>}
                    {b.priority && <Badge tone={b.priority === "A" ? "green" : b.priority === "B" ? "amber" : "slate"}>Öncelik {b.priority}</Badge>}
                    {b.do_not_contact && <Badge tone="red">İletişime geçme</Badge>}
                  </div>
                </Td>
                <Td>{b.district || "—"}</Td>
                <Td className="whitespace-nowrap">{fmtDate(b.establishment_date || b.gazette_date)}</Td>
                <Td className="whitespace-nowrap">{b.phone ? b.phone.value : <NotFound />}</Td>
                <Td>
                  <div>{b.email ? b.email.value : <NotFound />}</div>
                  <div className="text-xs">{b.website ? <a href={b.website.value} target="_blank" rel="noreferrer" className="text-brand-600 hover:underline">{b.website.value.replace(/^https?:\/\//, "")}</a> : <NotFound />}</div>
                </Td>
                <Td><Score value={b.isg_score} /></Td>
                <Td><Score value={b.software_score} /></Td>
                <Td>
                  <div className="space-y-1">
                    {b.opportunities.isg && <div className="text-xs"><span className="text-slate-500">İSG:</span> <StageBadge stage={b.opportunities.isg.stage} label={b.opportunities.isg.stage_label} /></div>}
                    {b.opportunities.yazilim && <div className="text-xs"><span className="text-slate-500">Yaz.:</span> <StageBadge stage={b.opportunities.yazilim.stage} label={b.opportunities.yazilim.stage_label} /></div>}
                  </div>
                </Td>
              </tr>
            ))}
          </Table>
        )}
        {data && data.total > data.page_size && (
          <div className="mt-3 flex items-center justify-end gap-2 text-sm">
            <Button variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Önceki</Button>
            <span>Sayfa {page} / {Math.ceil(data.total / data.page_size)}</span>
            <Button variant="secondary" disabled={page >= Math.ceil(data.total / data.page_size)} onClick={() => setPage(page + 1)}>Sonraki</Button>
          </div>
        )}
      </Card>
    </div>
  );
}
