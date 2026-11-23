"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "./api";

export function useApi<T = any>(path: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const reload = useCallback(async () => {
    if (!path) return;
    setLoading(true);
    setError(null);
    try {
      setData(await api<T>(path));
    } catch (e: any) {
      setError(e.message || "Hata");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, ...deps]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { data, error, loading, reload, setData };
}

export type Meta = {
  districts: string[];
  stages: { key: string; label: string }[];
  company_types: { key: string; label: string }[];
  sectors: { key: string; label: string }[];
  service_lines: { key: string; label: string }[];
  contact_types: Record<string, string>;
  activity_types: Record<string, string>;
  iys_statuses: Record<string, string>;
  roles: Record<string, string>;
};

let metaCache: Meta | null = null;

export function useMeta() {
  const [meta, setMeta] = useState<Meta | null>(metaCache);
  useEffect(() => {
    if (metaCache) return;
    api<Meta>("/meta").then((m) => {
      metaCache = m;
      setMeta(m);
    }).catch(() => undefined);
  }, []);
  return meta;
}
