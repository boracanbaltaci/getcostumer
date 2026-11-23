"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert, Button, Field, Input } from "@/components/ui";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      router.replace("/");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-brand-900 p-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-2xl bg-white p-6 shadow-xl">
        <div>
          <h1 className="text-lg font-bold text-brand-900">Ankara Business Radar</h1>
          <p className="text-sm text-slate-500">Yeni işletme keşfi ve müşteri yönetimi</p>
        </div>
        {error && <Alert tone="red">{error}</Alert>}
        <Field label="E-posta"><Input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required /></Field>
        <Field label="Parola"><Input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></Field>
        <Button type="submit" disabled={busy} className="w-full">{busy ? "Giriş yapılıyor…" : "Giriş yap"}</Button>
        <p className="text-xs text-slate-500">Bu sistem kişisel veri içerebilir. Erişimler kayıt altına alınır (KVKK).</p>
      </form>
    </div>
  );
}
