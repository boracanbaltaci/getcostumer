"use client";

import Link from "next/link";
import React from "react";

export function Card({ title, actions, children, className = "" }: {
  title?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode; className?: string;
}) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white shadow-sm ${className}`}>
      {(title || actions) && (
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
          {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Stat({ label, value, hint, href, tone = "default" }: {
  label: string; value: React.ReactNode; hint?: string; href?: string; tone?: "default" | "warn" | "good";
}) {
  const toneCls = tone === "warn" ? "text-amber-700" : tone === "good" ? "text-emerald-700" : "text-slate-900";
  const inner = (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-brand-500">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1 text-2xl font-bold tabular-nums ${toneCls}`}>{value}</div>
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </div>
  );
  return href ? <Link href={href}>{inner}</Link> : inner;
}

export function Button({ variant = "primary", className = "", ...props }:
  React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" | "ghost" }) {
  const v = {
    primary: "bg-brand-600 text-white hover:bg-brand-700 disabled:bg-slate-300",
    secondary: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 disabled:text-slate-400",
    danger: "bg-red-600 text-white hover:bg-red-700 disabled:bg-slate-300",
    ghost: "text-brand-600 hover:bg-brand-50",
  }[variant];
  return <button className={`inline-flex items-center justify-center gap-1 rounded-lg px-3 py-1.5 text-sm font-medium transition ${v} ${className}`} {...props} />;
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 ${props.className || ""}`} />;
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm focus:border-brand-500 focus:outline-none ${props.className || ""}`} />;
}

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={`w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:outline-none ${props.className || ""}`} />;
}

export function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-slate-600">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
    </label>
  );
}

export function Badge({ children, tone = "slate", title }: { children: React.ReactNode; tone?: string; title?: string }) {
  const map: Record<string, string> = {
    slate: "bg-slate-100 text-slate-700", green: "bg-emerald-100 text-emerald-800", amber: "bg-amber-100 text-amber-800",
    red: "bg-red-100 text-red-800", blue: "bg-brand-100 text-brand-700", violet: "bg-violet-100 text-violet-800",
  };
  return <span title={title} className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${map[tone] || map.slate}`}>{children}</span>;
}

export function Score({ value, label }: { value?: number | null; label?: string }) {
  if (value === null || value === undefined) return <span className="text-xs text-slate-400">—</span>;
  const tone = value >= 70 ? "bg-emerald-600" : value >= 50 ? "bg-amber-500" : "bg-slate-400";
  return (
    <span className="inline-flex items-center gap-1.5" title={label}>
      <span className="relative h-1.5 w-12 overflow-hidden rounded-full bg-slate-200">
        <span className={`absolute inset-y-0 left-0 ${tone}`} style={{ width: `${value}%` }} />
      </span>
      <span className="text-xs font-semibold tabular-nums text-slate-700">{value}</span>
    </span>
  );
}

const STAGE_TONE: Record<string, string> = {
  yeni: "slate", arastiriliyor: "blue", iletisime_hazir: "violet", ilk_gorusme: "amber", ilgileniyor: "amber",
  teklif_gonderildi: "blue", kazanildi: "green", olumsuz: "red",
};

export function StageBadge({ stage, label }: { stage: string; label?: string }) {
  return <Badge tone={STAGE_TONE[stage] || "slate"}>{label || stage}</Badge>;
}

export function ConfidenceBadge({ level, score }: { level: string; score: number }) {
  const tone = level === "yuksek" ? "green" : level === "orta" ? "amber" : "red";
  const label = level === "yuksek" ? "Yüksek" : level === "orta" ? "Orta" : "Düşük";
  return <Badge tone={tone} title={`Güven puanı ${score}/100`}>{label} · {score}</Badge>;
}

export function NotFound({ text = "Bulunamadı" }: { text?: string }) {
  return <span className="text-xs italic text-slate-400">{text}</span>;
}

export function Alert({ tone = "amber", children }: { tone?: "amber" | "red" | "blue" | "green"; children: React.ReactNode }) {
  const map = {
    amber: "border-amber-200 bg-amber-50 text-amber-900", red: "border-red-200 bg-red-50 text-red-900",
    blue: "border-brand-100 bg-brand-50 text-brand-900", green: "border-emerald-200 bg-emerald-50 text-emerald-900",
  };
  return <div className={`rounded-lg border px-3 py-2 text-sm ${map[tone]}`}>{children}</div>;
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="py-8 text-center text-sm text-slate-500">{children}</div>;
}

export function Spinner() {
  return <div className="py-8 text-center text-sm text-slate-500">Yükleniyor…</div>;
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-bold text-slate-900">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Table({ head, children }: { head: React.ReactNode[]; children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50">
          <tr>{head.map((h, i) => <th key={i} className="whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-slate-100">{children}</tbody>
      </table>
    </div>
  );
}

export function Td({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return <td className={`px-3 py-2 align-top ${className}`}>{children}</td>;
}

export const HEALTH: Record<string, { label: string; tone: string }> = {
  ok: { label: "Çalışıyor", tone: "green" }, error: { label: "Hata", tone: "red" },
  not_configured: { label: "Yapılandırılmadı", tone: "amber" }, manual: { label: "Manuel", tone: "slate" },
  unknown: { label: "Bilinmiyor", tone: "slate" },
};

export const JOB_STATUS: Record<string, { label: string; tone: string }> = {
  success: { label: "Başarılı", tone: "green" }, partial: { label: "Kısmi", tone: "amber" },
  failed: { label: "Başarısız", tone: "red" }, running: { label: "Çalışıyor", tone: "blue" },
  skipped: { label: "Atlandı", tone: "slate" },
};
