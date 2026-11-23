"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import {
  Alert, Badge, Button, Card, ConfidenceBadge, Field, Input, NotFound, Score, Select, Spinner, StageBadge, Textarea,
} from "@/components/ui";
import { api, download, fmtDate, fmtDateTime, fmtMoney } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi, useMeta } from "@/lib/hooks";

const BASIS: Record<string, { label: string; tone: string }> = {
  dogrulanmis: { label: "Doğrulanmış", tone: "green" }, tahmini: { label: "Tahmini", tone: "amber" },
};
const VERIF: Record<string, string> = {
  kaynaktan_otomatik: "Kaynaktan otomatik", manuel_dogrulandi: "Manuel doğrulandı", dogrulanmadi: "Doğrulanmadı", hatali: "Hatalı",
};

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="grid grid-cols-3 gap-2 border-b border-slate-50 py-1.5 text-sm">
      <dt className="text-slate-500">{k}</dt>
      <dd className="col-span-2 break-words text-slate-800">{v === null || v === undefined || v === "" ? <NotFound text="—" /> : v}</dd>
    </div>
  );
}

export default function BusinessDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: b, error, reload, setData } = useApi<any>(`/businesses/${id}`);
  const { can } = useAuth();
  const meta = useMeta();
  const users = useApi<any[]>("/users");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ tone: "green" | "red" | "amber"; text: string } | null>(null);
  const [editing, setEditing] = useState(false);

  async function act(name: string, fn: () => Promise<any>, ok?: string) {
    setBusy(name);
    setMsg(null);
    try {
      const r = await fn();
      if (r && r.id && r.trade_name) setData((prev: any) => ({ ...prev, ...r }));
      else await reload();
      if (ok) setMsg({ tone: "green", text: ok });
    } catch (e: any) {
      setMsg({ tone: "red", text: e.message });
    } finally {
      setBusy(null);
    }
  }

  if (error) return <Alert tone="red">{error}</Alert>;
  if (!b) return <Spinner />;
  const a = b.analysis || {};
  const canEdit = can("sales");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link href="/businesses" className="text-xs text-brand-600">← İşletmeler</Link>
          <h1 className="mt-1 text-xl font-bold">{b.trade_name}</h1>
          <div className="mt-1 flex flex-wrap gap-1">
            {b.company_type_label && <Badge>{b.company_type_label}</Badge>}
            {b.district && <Badge tone="blue">{b.district}</Badge>}
            {b.priority && <Badge tone={b.priority === "A" ? "green" : b.priority === "B" ? "amber" : "slate"}>Öncelik {b.priority}</Badge>}
            <Badge tone={b.verification_status === "manuel_dogrulandi" ? "green" : "slate"}>{VERIF[b.verification_status] || b.verification_status}</Badge>
            {b.do_not_contact && <Badge tone="red">İletişime geçme</Badge>}
            {b.merged_into_id && <Badge tone="red">Birleştirildi → #{b.merged_into_id}</Badge>}
          </div>
        </div>
        {canEdit && (
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" disabled={!!busy} onClick={() => act("enrich", () => api(`/businesses/${id}/enrich`, { method: "POST" }).then((r) => r.business), "İletişim araştırması tamamlandı")}>
              {busy === "enrich" ? "Araştırılıyor…" : "İletişim bilgisi araştır"}</Button>
            <Button variant="secondary" disabled={!!busy} onClick={() => act("analyze", () => api(`/businesses/${id}/analyze`, { method: "POST" }), "Analiz güncellendi")}>
              {busy === "analyze" ? "Analiz ediliyor…" : "Yeniden analiz et"}</Button>
            <Button variant="secondary" onClick={() => setEditing((e) => !e)}>{editing ? "Düzenlemeyi kapat" : "Bilgileri düzenle"}</Button>
          </div>
        )}
      </div>
      {msg && <Alert tone={msg.tone}>{msg.text}</Alert>}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <AnalysisCard b={b} a={a} />
          <Opportunities b={b} users={users.data || []} meta={meta} canEdit={canEdit} onChange={reload} />
          <Activities b={b} meta={meta} canEdit={canEdit} onChange={reload} />
        </div>
        <div className="space-y-4">
          <Contacts b={b} canEdit={canEdit} act={act} busy={busy} />
          {editing ? <EditCard b={b} meta={meta} onSaved={(r: any) => { setData((p: any) => ({ ...p, ...r })); setEditing(false); }} /> : (
            <Card title="Kayıt ve kaynak bilgileri">
              <dl>
                <Row k="Kuruluş / tescil" v={fmtDate(b.establishment_date)} />
                <Row k="İlan tarihi / sayı" v={b.gazette_date ? `${fmtDate(b.gazette_date)}${b.gazette_no ? ` · Sayı ${b.gazette_no}` : ""}${b.gazette_page ? ` · s.${b.gazette_page}` : ""}` : null} />
                <Row k="Sicil müdürlüğü" v={b.registry_office} />
                <Row k="Ticaret sicil no" v={b.registry_no} />
                <Row k="MERSİS no" v={b.mersis_no} />
                <Row k="İl / ilçe" v={[b.province, b.district].filter(Boolean).join(" / ")} />
                <Row k="Adres" v={b.address} />
                <Row k="NACE" v={b.nace_code ? <>{b.nace_code} <Badge tone={b.nace_verified ? "green" : "amber"}>{b.nace_verified ? "doğrulanmış" : "doğrulanmadı"}</Badge></> : null} />
                <Row k="Sermaye" v={b.capital ? fmtMoney(b.capital) : null} />
                <Row k="Faaliyet konusu" v={b.activity_text ? <span className="whitespace-pre-line text-xs">{b.activity_text.slice(0, 1200)}</span> : null} />
                <Row k="Kuruluş ilanı" v={b.announcement_url ? <a className="text-brand-600 underline" href={b.announcement_url} target="_blank" rel="noreferrer">Bağlantı</a> : b.source_reference} />
                <Row k="Veri kaynağı" v={b.source?.name} />
                <Row k="Doğrulama tarihi" v={fmtDateTime(b.verified_at)} />
                <Row k="İlk tespit" v={fmtDateTime(b.first_seen_at)} />
              </dl>
              {b.raw_records?.length > 0 && (
                <details className="mt-3 text-xs">
                  <summary className="cursor-pointer text-brand-600">Kaynak kayıtları ({b.raw_records.length})</summary>
                  {b.raw_records.map((r: any) => (
                    <div key={r.id} className="mt-2 rounded border border-slate-200 p-2">
                      <div className="text-slate-500">#{r.id} · {r.announcement_type || "tür yok"} · {fmtDateTime(r.fetched_at)} · {r.skip_reason}</div>
                      {r.raw_text && <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap text-[11px]">{r.raw_text}</pre>}
                    </div>
                  ))}
                </details>
              )}
            </Card>
          )}
          <Compliance b={b} meta={meta} act={act} can={can} />
        </div>
      </div>
    </div>
  );
}

function AnalysisCard({ b, a }: { b: any; a: any }) {
  if (!a.isg) return <Card title="Fırsat analizi"><p className="text-sm text-slate-500">Henüz analiz edilmedi.</p></Card>;
  const cls = a.classification || {};
  return (
    <Card title="Fırsat analizi" actions={<span className="text-xs text-slate-500">{b.analysis_method === "kural+llm" ? "Kural motoru + yapay zekâ" : "Kural motoru"} · {fmtDateTime(b.analyzed_at)}</span>}>
      <div className="mb-3 flex flex-wrap gap-2 text-sm">
        <span>Sektör: <b>{cls.sector_label}</b></span>
        <Badge tone={cls.sector_basis === "nace_dogrulanmis" ? "green" : "amber"}>{cls.sector_basis === "nace_dogrulanmis" ? "NACE (doğrulanmış)" : cls.sector_basis === "nace_tahmini" ? "NACE (doğrulanmamış)" : "Metinden tahmini"}</Badge>
        {b.hazard_label && <span>· Tehlike sınıfı: <b>{b.hazard_label}</b></span>}
      </div>
      {cls.hazard_note && <p className="mb-3 text-xs text-slate-500">{cls.hazard_note}</p>}
      <div className="grid gap-4 md:grid-cols-2">
        {[["İSG fırsatı", a.isg], ["Yazılım fırsatı", a.software]].map(([title, s]: any) => (
          <div key={title} className="rounded-lg border border-slate-200 p-3">
            <div className="flex items-center justify-between"><h3 className="text-sm font-semibold">{title}</h3><Score value={s.score} /></div>
            <ul className="mt-2 space-y-1">
              {s.factors.map((f: any, i: number) => (
                <li key={i} className="flex items-start justify-between gap-2 text-xs">
                  <span><span className="font-medium text-slate-700">{f.label}</span>{f.detail && <span className="block text-slate-500">{f.detail}</span>}</span>
                  <span className="flex shrink-0 items-center gap-1">
                    <Badge tone={BASIS[f.basis]?.tone}>{BASIS[f.basis]?.label}</Badge>
                    <span className={`w-8 text-right font-semibold tabular-nums ${f.points < 0 ? "text-red-600" : "text-slate-700"}`}>{f.points > 0 ? "+" : ""}{f.points}</span>
                  </span>
                </li>
              ))}
            </ul>
            <div className="mt-2 text-xs"><span className="font-medium">Önerilen hizmetler:</span> {s.recommended_services.join(", ")}</div>
            <p className="mt-2 rounded bg-amber-50 p-2 text-[11px] text-amber-900">{s.caveat}</p>
          </div>
        ))}
      </div>
      {a.llm && (
        <div className="mt-4 rounded-lg border border-violet-200 bg-violet-50 p-3 text-sm">
          <div className="mb-1 text-xs font-semibold uppercase text-violet-700">Yapay zekâ özeti (tahmini)</div>
          <p>{a.llm.summary}</p>
          {a.llm.talking_points?.length > 0 && <ul className="mt-2 list-disc pl-5 text-xs">{a.llm.talking_points.map((t: string, i: number) => <li key={i}>{t}</li>)}</ul>}
          {a.llm.open_questions?.length > 0 && <div className="mt-2 text-xs"><b>Görüşmede doğrulanacaklar:</b> {a.llm.open_questions.join(" · ")}</div>}
        </div>
      )}
      <p className="mt-3 text-[11px] text-slate-400">{a.total_formula}</p>
    </Card>
  );
}

function Contacts({ b, canEdit, act, busy }: any) {
  const [form, setForm] = useState({ type: "phone", value: "", source_url: "" });
  const [live, setLive] = useState<any>(null);
  const hasPlace = b.contacts.some((c: any) => c.type === "map_profile" && c.value.includes("place_id:"));
  const label: Record<string, string> = { phone: "Telefon", email: "E-posta", website: "Web sitesi", map_profile: "Harita / profil" };
  return (
    <Card title="Kurumsal iletişim bilgileri" actions={<Badge>{b.enrichment_status}</Badge>}>
      {b.do_not_contact && <Alert tone="red">Bu işletme 'iletişime geçme' olarak işaretli; telefon/e-posta gösterilmez.</Alert>}
      {["phone", "email", "website", "map_profile"].map((t) => {
        const items = b.contacts.filter((c: any) => c.type === t);
        return (
          <div key={t} className="border-b border-slate-50 py-2">
            <div className="text-xs font-medium text-slate-500">{label[t]}</div>
            {items.length === 0 ? <NotFound /> : items.map((c: any) => (
              <div key={c.id} className={`mt-1 rounded-lg p-2 text-sm ${c.status === "reddedildi" ? "bg-slate-50 line-through opacity-60" : "bg-slate-50"}`}>
                <div className="flex flex-wrap items-center justify-between gap-1">
                  <span className="break-all font-medium">{t === "website" || t === "map_profile" ? <a href={c.value} target="_blank" rel="noreferrer" className="text-brand-600 hover:underline">{c.value.replace(/^https?:\/\//, "")}</a> : c.value}</span>
                  <ConfidenceBadge level={c.confidence_level} score={c.confidence} />
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  Kaynak: {c.source_url ? <a href={c.source_url} target="_blank" rel="noreferrer" className="underline">{c.source_name}</a> : c.source_name}
                  {c.status === "dogrulandi" && <Badge tone="green">doğrulandı</Badge>}
                  {c.personal_data_risk && <Badge tone="red">kişisel veri olabilir</Badge>}
                </div>
                {c.evidence && <div className="mt-1 text-[11px] text-slate-500">{c.evidence}</div>}
                {canEdit && (
                  <div className="mt-1 flex gap-2 text-xs">
                    {c.status !== "dogrulandi" && <button className="text-emerald-700 underline" onClick={() => act("c", () => api(`/contacts/${c.id}`, { method: "PATCH", json: { status: "dogrulandi" } }))}>Doğrula</button>}
                    {c.status !== "reddedildi" && <button className="text-red-700 underline" onClick={() => act("c", () => api(`/contacts/${c.id}`, { method: "PATCH", json: { status: "reddedildi" } }))}>Yanlış eşleşme</button>}
                    <button className="text-slate-500 underline" onClick={() => act("c", () => api(`/contacts/${c.id}`, { method: "DELETE" }))}>Sil</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        );
      })}
      {hasPlace && (
        <div className="mt-2">
          <Button variant="secondary" onClick={() => api(`/businesses/${b.id}/places-live`).then(setLive).catch((e) => setLive({ error: e.message }))}>Google'dan canlı göster</Button>
          {live && <div className="mt-2 rounded bg-slate-50 p-2 text-xs">{live.error ? live.error : <>
            <div>{live.name} · {live.address}</div><div>Tel: {live.phone || "—"} · Web: {live.website || "—"}</div>
            <div className="text-slate-400">{live.attribution}</div></>}</div>}
        </div>
      )}
      {b.enrichment_log?.length > 0 && (
        <details className="mt-2 text-xs"><summary className="cursor-pointer text-brand-600">Araştırma günlüğü</summary>
          <ul className="mt-1 list-disc pl-4 text-slate-600">{b.enrichment_log.map((l: string, i: number) => <li key={i}>{l}</li>)}</ul></details>
      )}
      {canEdit && !b.do_not_contact && (
        <form className="mt-3 space-y-2 border-t border-slate-100 pt-3" onSubmit={(e) => { e.preventDefault(); act("add", () => api(`/businesses/${b.id}/contacts`, { method: "POST", json: { ...form, source_url: form.source_url || null } }), "Eklendi"); setForm({ ...form, value: "", source_url: "" }); }}>
          <div className="text-xs font-medium text-slate-600">Manuel kurumsal iletişim ekle</div>
          <div className="flex gap-2">
            <Select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} className="max-w-[120px]">
              <option value="phone">Telefon</option><option value="email">E-posta</option><option value="website">Web</option><option value="map_profile">Profil</option>
            </Select>
            <Input required placeholder="Değer" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} />
          </div>
          <Input placeholder="Kaynak bağlantısı (önerilir)" value={form.source_url} onChange={(e) => setForm({ ...form, source_url: e.target.value })} />
          <Button type="submit" disabled={busy === "add"}>Ekle</Button>
          <p className="text-[11px] text-slate-500">Yalnızca kurumsal ve kamuya açık bilgileri girin. Kişisel cep telefonu / kişisel e-posta kaydetmeyin.</p>
        </form>
      )}
    </Card>
  );
}

function Opportunities({ b, users, meta, canEdit, onChange }: any) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {b.opportunity_list.map((o: any) => <OppCard key={o.id} o={o} users={users} meta={meta} canEdit={canEdit} onChange={onChange} b={b} />)}
    </div>
  );
}

function OppCard({ o, b, users, meta, canEdit, onChange }: any) {
  const [f, setF] = useState({ stage: o.stage, owner_id: o.owner_id || "", estimated_value: o.estimated_value ?? "", next_action: o.next_action || "", next_action_date: o.next_action_date || "", lost_reason: o.lost_reason || "" });
  const [err, setErr] = useState<string | null>(null);
  const [showQuote, setShowQuote] = useState(false);
  const quotes = (b.quotes || []).filter((q: any) => q.opportunity_id === o.id);
  async function save() {
    setErr(null);
    try {
      await api(`/opportunities/${o.id}`, { method: "PATCH", json: {
        stage: f.stage, owner_id: f.owner_id ? Number(f.owner_id) : null,
        estimated_value: f.estimated_value === "" ? null : Number(f.estimated_value),
        next_action: f.next_action || null, next_action_date: f.next_action_date || null, lost_reason: f.lost_reason || null } });
      onChange();
    } catch (e: any) { setErr(e.message); }
  }
  return (
    <Card title={o.service_line === "isg" ? "İSG fırsatı" : "Yazılım fırsatı"} actions={<StageBadge stage={o.stage} label={o.stage_label} />}>
      <div className="space-y-2">
        <Field label="Aşama"><Select disabled={!canEdit} value={f.stage} onChange={(e) => setF({ ...f, stage: e.target.value })}>
          {meta?.stages.map((s: any) => <option key={s.key} value={s.key}>{s.label}</option>)}</Select></Field>
        {f.stage === "olumsuz" && <Field label="Olumsuz nedeni"><Input value={f.lost_reason} onChange={(e) => setF({ ...f, lost_reason: e.target.value })} /></Field>}
        <div className="grid grid-cols-2 gap-2">
          <Field label="Sorumlu"><Select disabled={!canEdit} value={f.owner_id} onChange={(e) => setF({ ...f, owner_id: e.target.value })}>
            <option value="">—</option>{users.map((u: any) => <option key={u.id} value={u.id}>{u.full_name}</option>)}</Select></Field>
          <Field label="Teklif tutarı (TL)"><Input disabled={!canEdit} type="number" step="0.01" value={f.estimated_value} onChange={(e) => setF({ ...f, estimated_value: e.target.value })} /></Field>
        </div>
        <Field label="Sonraki aksiyon"><Input disabled={!canEdit} value={f.next_action} onChange={(e) => setF({ ...f, next_action: e.target.value })} /></Field>
        <Field label="Takip tarihi"><Input disabled={!canEdit} type="date" value={f.next_action_date} onChange={(e) => setF({ ...f, next_action_date: e.target.value })} /></Field>
        {err && <p className="text-xs text-red-600">{err}</p>}
        {canEdit && <div className="flex gap-2"><Button onClick={save}>Kaydet</Button><Button variant="secondary" onClick={() => setShowQuote((s) => !s)}>Teklif oluştur</Button></div>}
        {showQuote && <QuoteForm oppId={o.id} line={o.service_line} onDone={() => { setShowQuote(false); onChange(); }} />}
        {quotes.length > 0 && (
          <div className="mt-2 border-t border-slate-100 pt-2">
            <div className="text-xs font-medium text-slate-500">Teklifler</div>
            {quotes.map((q: any) => (
              <div key={q.id} className="mt-1 flex flex-wrap items-center justify-between gap-1 text-sm">
                <span>{q.number} · {fmtMoney(q.total, q.currency)} <Badge>{q.status}</Badge></span>
                <span className="flex gap-2 text-xs">
                  <button className="text-brand-600 underline" onClick={() => download(`/quotes/${q.id}/pdf`, `${q.number}.pdf`)}>PDF</button>
                  {canEdit && q.status === "taslak" && <button className="text-brand-600 underline" onClick={() => api(`/quotes/${q.id}`, { method: "PATCH", json: { status: "gonderildi" } }).then(onChange)}>Gönderildi</button>}
                  {canEdit && q.status === "gonderildi" && <>
                    <button className="text-emerald-700 underline" onClick={() => api(`/quotes/${q.id}`, { method: "PATCH", json: { status: "kabul" } }).then(onChange)}>Kabul</button>
                    <button className="text-red-700 underline" onClick={() => api(`/quotes/${q.id}`, { method: "PATCH", json: { status: "red" } }).then(onChange)}>Red</button></>}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

const QUOTE_TEMPLATES: Record<string, { title: string; items: { description: string; quantity: number; unit: string; unit_price: number; vat_rate: number }[] }> = {
  isg: { title: "İş Sağlığı ve Güvenliği Hizmet Teklifi", items: [
    { description: "İş güvenliği uzmanlığı hizmeti", quantity: 12, unit: "Ay", unit_price: 0, vat_rate: 20 },
    { description: "İşyeri hekimliği hizmeti", quantity: 12, unit: "Ay", unit_price: 0, vat_rate: 20 },
    { description: "Risk değerlendirmesi ve acil durum planı", quantity: 1, unit: "Adet", unit_price: 0, vat_rate: 20 }] },
  yazilim: { title: "Yazılım ve Dijital Çözümler Teklifi", items: [
    { description: "Kurumsal web sitesi tasarım ve geliştirme", quantity: 1, unit: "Proje", unit_price: 0, vat_rate: 20 },
    { description: "Barındırma ve bakım (yıllık)", quantity: 1, unit: "Yıl", unit_price: 0, vat_rate: 20 }] },
};

function QuoteForm({ oppId, line, onDone }: { oppId: number; line: string; onDone: () => void }) {
  const [t, setT] = useState(QUOTE_TEMPLATES[line] || QUOTE_TEMPLATES.yazilim);
  const [notes, setNotes] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const setItem = (i: number, k: string, v: any) => setT({ ...t, items: t.items.map((it, j) => (j === i ? { ...it, [k]: v } : it)) });
  const total = t.items.reduce((s, it) => s + it.quantity * it.unit_price * (1 + it.vat_rate / 100), 0);
  return (
    <div className="space-y-2 rounded-lg border border-brand-100 bg-brand-50 p-2">
      <Input value={t.title} onChange={(e) => setT({ ...t, title: e.target.value })} />
      {t.items.map((it, i) => (
        <div key={i} className="grid grid-cols-12 gap-1">
          <Input className="col-span-6" value={it.description} onChange={(e) => setItem(i, "description", e.target.value)} />
          <Input className="col-span-2" type="number" value={it.quantity} onChange={(e) => setItem(i, "quantity", Number(e.target.value))} />
          <Input className="col-span-3" type="number" placeholder="Birim fiyat" value={it.unit_price} onChange={(e) => setItem(i, "unit_price", Number(e.target.value))} />
          <button className="col-span-1 text-red-600" onClick={() => setT({ ...t, items: t.items.filter((_, j) => j !== i) })}>✕</button>
        </div>
      ))}
      <Button variant="ghost" onClick={() => setT({ ...t, items: [...t.items, { description: "", quantity: 1, unit: "Adet", unit_price: 0, vat_rate: 20 }] })}>+ Kalem</Button>
      <Textarea rows={2} placeholder="Notlar / koşullar" value={notes} onChange={(e) => setNotes(e.target.value)} />
      <div className="text-sm">KDV dahil toplam: <b>{fmtMoney(total)}</b></div>
      {err && <p className="text-xs text-red-600">{err}</p>}
      <Button onClick={() => api(`/opportunities/${oppId}/quotes`, { method: "POST", json: { ...t, notes } }).then(onDone).catch((e) => setErr(e.message))}>Teklifi kaydet</Button>
    </div>
  );
}

function Activities({ b, meta, canEdit, onChange }: any) {
  const [f, setF] = useState({ type: "call", content: "", opportunity_id: "", follow_up_date: "" });
  const [err, setErr] = useState<string | null>(null);
  return (
    <Card title="Görüşme geçmişi">
      {canEdit && (
        <form className="mb-4 space-y-2" onSubmit={async (e) => {
          e.preventDefault(); setErr(null);
          try {
            await api(`/businesses/${b.id}/activities`, { method: "POST", json: { type: f.type, content: f.content,
              opportunity_id: f.opportunity_id ? Number(f.opportunity_id) : null, follow_up_date: f.follow_up_date || null } });
            setF({ ...f, content: "", follow_up_date: "" }); onChange();
          } catch (e: any) { setErr(e.message); }
        }}>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <Select value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}>
              {meta && Object.entries(meta.activity_types).map(([k, v]: any) => <option key={k} value={k}>{v}</option>)}</Select>
            <Select value={f.opportunity_id} onChange={(e) => setF({ ...f, opportunity_id: e.target.value })}>
              <option value="">Genel</option>{b.opportunity_list.map((o: any) => <option key={o.id} value={o.id}>{o.service_line === "isg" ? "İSG" : "Yazılım"}</option>)}</Select>
            <Input type="date" title="Takip tarihi" value={f.follow_up_date} onChange={(e) => setF({ ...f, follow_up_date: e.target.value })} />
            <Button type="submit">Not ekle</Button>
          </div>
          <Textarea required rows={2} placeholder="Görüşme notu…" value={f.content} onChange={(e) => setF({ ...f, content: e.target.value })} />
          {err && <p className="text-xs text-red-600">{err}</p>}
        </form>
      )}
      {(b.activities || []).length === 0 ? <p className="text-sm text-slate-500">Henüz görüşme kaydı yok.</p> : (
        <ol className="space-y-3">
          {b.activities.map((a: any) => (
            <li key={a.id} className="border-l-2 border-brand-100 pl-3">
              <div className="text-xs text-slate-500">{fmtDateTime(a.occurred_at)} · {meta?.activity_types[a.type] || a.type} · {a.user?.full_name || "—"}
                {a.opportunity_id && <> · {b.opportunity_list.find((o: any) => o.id === a.opportunity_id)?.service_line === "isg" ? "İSG" : "Yazılım"}</>}</div>
              <div className="whitespace-pre-line text-sm">{a.content}</div>
              {a.follow_up_date && (
                <div className="mt-1 text-xs">Takip: {fmtDate(a.follow_up_date)}{" "}
                  {a.follow_up_done ? <Badge tone="green">tamamlandı</Badge> : canEdit &&
                    <button className="text-brand-600 underline" onClick={() => api(`/activities/${a.id}`, { method: "PATCH", json: { follow_up_done: true } }).then(onChange)}>Tamamlandı işaretle</button>}
                </div>
              )}
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

function EditCard({ b, meta, onSaved }: any) {
  const [f, setF] = useState<any>({
    trade_name: b.trade_name, establishment_date: b.establishment_date || "", registry_office: b.registry_office || "",
    registry_no: b.registry_no || "", mersis_no: b.mersis_no || "", district: b.district || "", address: b.address || "",
    activity_text: b.activity_text || "", nace_code: b.nace_code || "", nace_verified: b.nace_verified,
    company_type: b.company_type || "", announcement_url: b.announcement_url || "", verification_status: b.verification_status,
  });
  const [err, setErr] = useState<string | null>(null);
  const inp = (k: string, label: string, type = "text") => (
    <Field label={label}><Input type={type} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} /></Field>);
  return (
    <Card title="Bilgileri düzenle / doğrula">
      <div className="space-y-2">
        {inp("trade_name", "Ticaret unvanı")}
        {inp("establishment_date", "Kuruluş tarihi", "date")}
        <div className="grid grid-cols-2 gap-2">{inp("registry_office", "Sicil müdürlüğü")}{inp("registry_no", "Sicil no")}</div>
        {inp("mersis_no", "MERSİS no")}
        <Field label="İlçe"><Select value={f.district} onChange={(e) => setF({ ...f, district: e.target.value })}>
          <option value="">—</option>{meta?.districts.map((d: string) => <option key={d}>{d}</option>)}</Select></Field>
        <Field label="Adres"><Textarea rows={2} value={f.address} onChange={(e) => setF({ ...f, address: e.target.value })} /></Field>
        <Field label="Faaliyet konusu"><Textarea rows={3} value={f.activity_text} onChange={(e) => setF({ ...f, activity_text: e.target.value })} /></Field>
        <div className="grid grid-cols-2 gap-2">{inp("nace_code", "NACE kodu")}
          <Field label="NACE doğrulandı mı?"><Select value={f.nace_verified ? "1" : "0"} onChange={(e) => setF({ ...f, nace_verified: e.target.value === "1" })}>
            <option value="0">Hayır</option><option value="1">Evet (resmî kaynaktan)</option></Select></Field></div>
        <Field label="Şirket türü"><Select value={f.company_type} onChange={(e) => setF({ ...f, company_type: e.target.value })}>
          {meta?.company_types.map((c: any) => <option key={c.key} value={c.key}>{c.label}</option>)}</Select></Field>
        {inp("announcement_url", "Kuruluş ilanı bağlantısı")}
        <Field label="Doğrulama durumu"><Select value={f.verification_status} onChange={(e) => setF({ ...f, verification_status: e.target.value })}>
          {Object.entries(VERIF).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select></Field>
        {err && <p className="text-xs text-red-600">{err}</p>}
        <Button onClick={() => {
          const body: any = { ...f };
          Object.keys(body).forEach((k) => { if (body[k] === "") body[k] = null; });
          api(`/businesses/${b.id}`, { method: "PATCH", json: body }).then(onSaved).catch((e) => setErr(e.message));
        }}>Kaydet</Button>
      </div>
    </Card>
  );
}

function Compliance({ b, meta, act, can }: any) {
  const [check, setCheck] = useState<any>(null);
  return (
    <Card title="İletişim izni ve KVKK">
      <div className="space-y-2 text-sm">
        <Field label="İYS / ret kontrolü" hint={b.iys_checked_at ? `Son kontrol: ${fmtDateTime(b.iys_checked_at)}` : "Elektronik ticari ileti öncesi kontrol edin"}>
          <Select disabled={!can("sales")} value={b.iys_status} onChange={(e) => act("iys", () => api(`/businesses/${b.id}/compliance`, { method: "POST", json: { iys_status: e.target.value } }))}>
            {meta && Object.entries(meta.iys_statuses).map(([k, v]: any) => <option key={k} value={k}>{v}</option>)}</Select>
        </Field>
        <label className="flex items-center gap-2">
          <input type="checkbox" disabled={!can("sales")} checked={b.do_not_contact} onChange={(e) => act("dnc", () => api(`/businesses/${b.id}/compliance`, { method: "POST", json: { do_not_contact: e.target.checked } }))} />
          İletişime geçme (itiraz / talep)
        </label>
        <div className="flex flex-wrap gap-2">
          {["phone", "email"].map((ch) => (
            <Button key={ch} variant="secondary" onClick={() => api(`/businesses/${b.id}/outreach-check?channel=${ch}`).then(setCheck)}>
              {ch === "phone" ? "Arama öncesi kontrol" : "E-posta öncesi kontrol"}</Button>))}
        </div>
        {check && (
          <div className={`rounded p-2 text-xs ${check.allowed ? "bg-emerald-50 text-emerald-900" : "bg-red-50 text-red-900"}`}>
            <b>{check.allowed ? "Uygun" : "Uygun değil"}</b>
            {check.blockers.map((x: string, i: number) => <div key={i}>✕ {x}</div>)}
            {check.warnings.map((x: string, i: number) => <div key={i} className="text-slate-600">! {x}</div>)}
          </div>
        )}
        {can("manager") && !b.anonymized_at && (
          <Button variant="danger" onClick={() => { if (confirm("İletişim verileri ve notlar silinecek, kayıt anonimleştirilecek. Emin misiniz?")) act("anon", () => api(`/businesses/${b.id}/kvkk/anonymize`, { method: "POST" }), "Kayıt anonimleştirildi"); }}>
            KVKK: verileri sil / anonimleştir</Button>
        )}
        {b.anonymized_at && <Alert tone="red">Kayıt {fmtDateTime(b.anonymized_at)} tarihinde anonimleştirildi.</Alert>}
      </div>
    </Card>
  );
}
