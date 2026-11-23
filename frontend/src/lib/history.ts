import type { Business, ScanStats } from "./api";

/** Tarayıcıda tutulan tarama geçmişi kaydı (sunucu stateless'tır). */
export interface ScanRecord {
  id: string;
  scanned_at: string; // ISO
  lat: number;
  lng: number;
  radius_m: number;
  stats: ScanStats;
  businesses: Business[];
}

const KEY = "isletme-radari:taramalar";
const MAX_RECORDS = 30;

export function loadScans(): ScanRecord[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as ScanRecord[]) : [];
  } catch {
    return [];
  }
}

export function saveScan(rec: Omit<ScanRecord, "id">): ScanRecord {
  const record: ScanRecord = { ...rec, id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}` };
  const all = [record, ...loadScans()].slice(0, MAX_RECORDS);
  localStorage.setItem(KEY, JSON.stringify(all));
  return record;
}

export function deleteScan(id: string): ScanRecord[] {
  const all = loadScans().filter((s) => s.id !== id);
  localStorage.setItem(KEY, JSON.stringify(all));
  return all;
}
