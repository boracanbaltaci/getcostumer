export type WebsiteStatus = "yok" | "eski" | "erisilemedi";
export type Priority = "A" | "B" | "C";

export interface ScoreFactor {
  points: number;
  label: string;
  basis: "dogrulanmis" | "tahmini";
}

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
  score: number;
  priority: Priority;
  score_factors: ScoreFactor[];
  recommended_services: string[];
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
  is_favorite: boolean;
}

/** Tek tarama kaydı — işletme listesi dahil. */
export interface ScanRecord extends ScanSummary {
  businesses: Business[];
}

export interface User {
  username: string;
}

/** Favori işletme kaydı — snapshot olarak saklanır. */
export interface BusinessFavorite {
  place_id: string;
  added_at: string;
  business: Business;
}

/** Kayıtlı hızlı mesaj şablonu. */
export interface QuickMessage {
  id: string;
  text: string;
  created_at: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith("/api/auth/") && typeof window !== "undefined") {
      window.dispatchEvent(new Event("auth:expired"));
    }
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

export function login(username: string, password: string): Promise<User> {
  return request<User>("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
}

export async function logout(): Promise<void> {
  await request("/api/auth/logout", { method: "POST" });
}

export function me(): Promise<User> {
  return request<User>("/api/auth/me");
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

export function listFavorites(): Promise<ScanSummary[]> {
  return request<ScanSummary[]>("/api/favorites");
}

export async function addFavoriteApi(scanId: string): Promise<void> {
  await request(`/api/favorites/${scanId}`, { method: "PUT" });
}

export async function removeFavoriteApi(scanId: string): Promise<void> {
  await request(`/api/favorites/${scanId}`, { method: "DELETE" });
}

export function listBusinessFavorites(): Promise<BusinessFavorite[]> {
  return request<BusinessFavorite[]>("/api/business-favorites");
}

export async function addBusinessFavoriteApi(b: Business): Promise<void> {
  await request(`/api/business-favorites/${encodeURIComponent(b.place_id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ business: b }),
  });
}

export async function removeBusinessFavoriteApi(placeId: string): Promise<void> {
  await request(`/api/business-favorites/${encodeURIComponent(placeId)}`, { method: "DELETE" });
}

export function listQuickMessages(): Promise<QuickMessage[]> {
  return request<QuickMessage[]>("/api/quick-messages");
}

export function addQuickMessageApi(text: string): Promise<QuickMessage> {
  return request<QuickMessage>("/api/quick-messages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
}

export async function updateQuickMessageApi(id: string, text: string): Promise<void> {
  await request(`/api/quick-messages/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
}

export async function deleteQuickMessageApi(id: string): Promise<void> {
  await request(`/api/quick-messages/${id}`, { method: "DELETE" });
}
