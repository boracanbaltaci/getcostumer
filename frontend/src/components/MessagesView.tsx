"use client";

import { useEffect, useState } from "react";
import { Loader2, Pencil, Plus, Trash2, X } from "lucide-react";
import { addQuickMessageApi, deleteQuickMessageApi, listQuickMessages,
         updateQuickMessageApi, type QuickMessage } from "@/lib/api";

export default function MessagesView() {
  const [messages, setMessages] = useState<QuickMessage[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    listQuickMessages()
      .then(setMessages)
      .catch((e) => setError(e instanceof Error ? e.message : "Mesajlar yüklenemedi"));
  }, []);

  function openAdd() {
    setEditId(null);
    setDraft("");
    setOpen(true);
  }

  function openEdit(m: QuickMessage) {
    setEditId(m.id);
    setDraft(m.text);
    setOpen(true);
  }

  async function save() {
    const text = draft.trim();
    if (!text || busy) return;
    setBusy(true);
    try {
      if (editId) {
        await updateQuickMessageApi(editId, text);
        setMessages((prev) => (prev ?? []).map((m) => (m.id === editId ? { ...m, text } : m)));
      } else {
        const msg = await addQuickMessageApi(text);
        setMessages((prev) => [msg, ...(prev ?? [])]);
      }
      setOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Mesaj kaydedilemedi");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    try {
      await deleteQuickMessageApi(id);
      setMessages((prev) => (prev ?? []).filter((m) => m.id !== id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Mesaj silinemedi");
    }
  }

  if (error && !messages) {
    return <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>;
  }
  if (!messages) {
    return <div className="flex items-center gap-2 p-6 text-sm text-slate-500"><Loader2 size={16} className="animate-spin" /> Mesajlar yükleniyor…</div>;
  }

  return (
    <>
      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <header className="border-b border-slate-100 px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-800">Hızlı Mesajlar ({messages.length})</h2>
        </header>
        <div className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-3">
          <button type="button" onClick={openAdd} aria-label="Yeni hızlı mesaj"
                  className="flex min-h-28 flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-slate-300 text-slate-400 transition hover:border-brand-500 hover:text-brand-600">
            <Plus size={22} />
            <span className="text-xs font-medium">Yeni mesaj</span>
          </button>
          {messages.map((m) => (
            <div key={m.id} className="group relative rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="whitespace-pre-wrap pr-6 text-sm text-slate-700">{m.text}</p>
              <div className="absolute right-3 top-3 flex gap-0.5">
                <button type="button" onClick={() => openEdit(m)} aria-label="Mesajı düzenle"
                        className="rounded-lg p-1 text-slate-300 transition hover:bg-slate-100 hover:text-slate-600">
                  <Pencil size={15} />
                </button>
                <button type="button" onClick={() => remove(m.id)} aria-label="Mesajı sil"
                        className="rounded-lg p-1 text-slate-300 transition hover:bg-red-50 hover:text-red-500">
                  <Trash2 size={15} />
                </button>
              </div>
            </div>
          ))}
        </div>
        {!messages.length && (
          <p className="px-4 pb-4 text-center text-xs text-slate-400">
            Henüz kayıtlı mesaj yok — ekledikleriniz e-posta/SMS modalında seçilebilir.
          </p>
        )}
      </section>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
             onClick={() => setOpen(false)} role="dialog" aria-modal="true"
             aria-label={editId ? "Hızlı Mesajı Düzenle" : "Hızlı Mesaj Ekle"}>
          <div className="w-full max-w-lg rounded-xl bg-white shadow-xl" onClick={(e) => e.stopPropagation()}>
            <header className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
              <h2 className="text-sm font-semibold text-slate-800">
                {editId ? "Hızlı Mesajı Düzenle" : "Hızlı Mesaj Ekle"}
              </h2>
              <button type="button" onClick={() => setOpen(false)} aria-label="Kapat"
                      className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600">
                <X size={18} />
              </button>
            </header>
            <div className="p-5">
              <textarea
                autoFocus
                rows={6}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Mesaj metnini yazın…"
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
              <div className="mt-4 flex justify-end gap-2">
                <button type="button" onClick={() => setOpen(false)}
                        className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50">
                  Vazgeç
                </button>
                <button type="button" onClick={save} disabled={!draft.trim() || busy}
                        className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:bg-slate-300">
                  {busy && <Loader2 size={14} className="animate-spin" />}
                  Kaydet
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
