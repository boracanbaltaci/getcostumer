"use client";

import { useState } from "react";
import { Alert, Button, Card, Field, Input, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function AccountPage() {
  const { user } = useAuth();
  const [cur, setCur] = useState("");
  const [nw, setNw] = useState("");
  const [msg, setMsg] = useState<{ t: "green" | "red"; m: string } | null>(null);
  return (
    <div className="max-w-md space-y-4">
      <PageHeader title="Hesabım" subtitle={`${user?.full_name} · ${user?.email}`} />
      {msg && <Alert tone={msg.t}>{msg.m}</Alert>}
      <Card title="Parola değiştir">
        <form className="space-y-2" onSubmit={(e) => {
          e.preventDefault();
          api("/auth/change-password", { method: "POST", json: { current_password: cur, new_password: nw } })
            .then(() => { setMsg({ t: "green", m: "Parola güncellendi" }); setCur(""); setNw(""); })
            .catch((err) => setMsg({ t: "red", m: err.message }));
        }}>
          <Field label="Mevcut parola"><Input type="password" value={cur} onChange={(e) => setCur(e.target.value)} required /></Field>
          <Field label="Yeni parola" hint="En az 10 karakter, harf ve rakam"><Input type="password" value={nw} onChange={(e) => setNw(e.target.value)} required /></Field>
          <Button type="submit">Güncelle</Button>
        </form>
      </Card>
    </div>
  );
}
