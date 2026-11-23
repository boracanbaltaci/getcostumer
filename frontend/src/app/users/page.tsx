"use client";

import { useState } from "react";
import { Alert, Badge, Button, Card, Field, Input, PageHeader, Select, Spinner, Table, Td } from "@/components/ui";
import { api, fmtDateTime } from "@/lib/api";
import { useApi, useMeta } from "@/lib/hooks";

export default function UsersPage() {
  const meta = useMeta();
  const users = useApi<any[]>("/users");
  const audit = useApi<any[]>("/audit?limit=200");
  const [f, setF] = useState({ email: "", full_name: "", password: "", role: "sales" });
  const [msg, setMsg] = useState<{ t: "green" | "red"; m: string } | null>(null);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    try { await api("/users", { method: "POST", json: f }); setF({ email: "", full_name: "", password: "", role: "sales" }); setMsg({ t: "green", m: "Kullanıcı oluşturuldu" }); users.reload(); }
    catch (err: any) { setMsg({ t: "red", m: err.message }); }
  }
  async function patch(id: number, body: any) {
    try { await api(`/users/${id}`, { method: "PATCH", json: body }); users.reload(); } catch (err: any) { setMsg({ t: "red", m: err.message }); }
  }

  return (
    <div className="space-y-4">
      <PageHeader title="Kullanıcılar ve Denetim Kaydı" />
      {msg && <Alert tone={msg.t}>{msg.m}</Alert>}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Kullanıcılar" className="lg:col-span-2">
          {!users.data ? <Spinner /> : (
            <Table head={["Ad", "E-posta", "Rol", "Durum", "Son giriş"]}>
              {users.data.map((u) => (
                <tr key={u.id}>
                  <Td>{u.full_name}</Td><Td>{u.email}</Td>
                  <Td><Select value={u.role} onChange={(e) => patch(u.id, { role: e.target.value })} className="max-w-[160px]">
                    {meta && Object.entries(meta.roles).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select></Td>
                  <Td><button onClick={() => patch(u.id, { is_active: !u.is_active })}><Badge tone={u.is_active ? "green" : "red"}>{u.is_active ? "Aktif" : "Pasif"}</Badge></button></Td>
                  <Td className="text-xs">{fmtDateTime(u.last_login_at)}</Td>
                </tr>
              ))}
            </Table>
          )}
        </Card>
        <Card title="Yeni kullanıcı">
          <form onSubmit={create} className="space-y-2">
            <Field label="Ad soyad"><Input required value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></Field>
            <Field label="E-posta"><Input required type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
            <Field label="Geçici parola" hint="En az 10 karakter, harf ve rakam"><Input required type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></Field>
            <Field label="Rol"><Select value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}>
              {meta && Object.entries(meta.roles).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select></Field>
            <Button type="submit">Oluştur</Button>
          </form>
          <div className="mt-4 text-xs text-slate-500">
            <b>Roller:</b> Görüntüleyici yalnızca okur · Satış temsilcisi kayıt/görüşme/teklif yönetir · Satış müdürü birleştirme,
            toplu görev ve KVKK silme yapar · Yönetici kullanıcı ve kaynak yönetir.
          </div>
        </Card>
      </div>
      <Card title="Denetim kaydı (son 200)">
        {!audit.data ? <Spinner /> : (
          <Table head={["Zaman", "Kullanıcı", "İşlem", "Kayıt", "Ayrıntı"]}>
            {audit.data.map((a) => (
              <tr key={a.id}>
                <Td className="whitespace-nowrap text-xs">{fmtDateTime(a.created_at)}</Td>
                <Td className="text-xs">{a.user || "sistem"}</Td><Td className="text-xs">{a.action}</Td>
                <Td className="text-xs">{a.entity_type} {a.entity_id}</Td>
                <Td className="max-w-md truncate text-xs" >{JSON.stringify(a.details)}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
