"use client";

import { useState } from "react";
import { Loader2, ScanSearch } from "lucide-react";
import { login } from "@/lib/api";

const INPUT_CLS = "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500";

export default function LoginScreen({ onLogin }: { onLogin: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await login(username.trim(), password);
      onLogin();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Giriş başarısız");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <form onSubmit={submit}
            className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-5 flex items-center gap-2">
          <ScanSearch className="text-brand-600" size={22} />
          <h1 className="text-base font-bold text-slate-900">İşletme Radarı</h1>
        </div>
        <label className="mb-3 block text-sm text-slate-600">
          Kullanıcı adı
          <input type="text" autoComplete="username" autoFocus required
                 value={username} onChange={(e) => setUsername(e.target.value)}
                 className={INPUT_CLS} />
        </label>
        <label className="mb-3 block text-sm text-slate-600">
          Şifre
          <input type="password" autoComplete="current-password" required
                 value={password} onChange={(e) => setPassword(e.target.value)}
                 className={INPUT_CLS} />
        </label>
        {error && (
          <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {error}
          </div>
        )}
        <button type="submit" disabled={busy || !username || !password}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:bg-slate-300">
          {busy && <Loader2 size={15} className="animate-spin" />}
          Giriş yap
        </button>
      </form>
    </div>
  );
}
