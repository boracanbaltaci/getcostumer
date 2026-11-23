export type WebsiteStatus = "yok" | "eski" | "erisilemedi";

export interface Business {
  place_id: string;
  name: string;
  address: string;
  lat: number | null;
  lng: number | null;
  phone: string;
  website: string | null;
  website_status: WebsiteStatus;
  website_notes: string[];
}

export interface ScanStats {
  found: number;
  shown: number;
  without_website: number;
  outdated_website: number;
  unreachable_website: number;
  filtered_modern: number;
}

export interface ScanResponse {
  businesses: Business[];
  stats: ScanStats;
  warnings: string[];
}

export interface AppConfig {
  google_places_configured: boolean;
}

/** Geçmiş listesi satırı — işletme detayı içermez. */
export interface ScanSummary {
  id: string;
  scanned_at: string;
  lat: number;
  lng: number;
  radius_m: number;
  stats: ScanStats;
}

/** Tek tarama kaydı — işletme listesi dahil. */
export interface ScanRecord extends ScanSummary {
  businesses: Business[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch { /* gövde yok */ }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export function getConfig(): Promise<AppConfig> {
  return request<AppConfig>("/api/config");
}

export function scanArea(lat: number, lng: number, radius_m: number): Promise<ScanResponse> {
  return request<ScanResponse>("/api/scan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lat, lng, radius_m }),
  });
}

export function listScans(): Promise<ScanSummary[]> {
  return request<ScanSummary[]>("/api/scans");
}

export function getScan(id: string): Promise<ScanRecord> {
  return request<ScanRecord>(`/api/scans/${id}`);
}

export async function deleteScanApi(id: string): Promise<void> {
  await request(`/api/scans/${id}`, { method: "DELETE" });
}
