import type { ResolveResponse, AreaResponse, TabName } from '../types';

const BASE = '/api/v1';

export async function resolveSearch(query: string): Promise<ResolveResponse> {
  const res = await fetch(`${BASE}/resolve?q=${encodeURIComponent(query)}`);
  if (!res.ok) throw new Error(`Resolve failed: ${res.status}`);
  return res.json();
}

export async function fetchAreaTab(
  lad: string,
  ward: string,
  lsoa: string,
  tab: TabName,
): Promise<AreaResponse> {
  const url = `${BASE}/area/${lad}/${ward}/${lsoa}?tab=${encodeURIComponent(tab)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Area fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchBoundary(wardCode: string): Promise<GeoJSON.Feature | null> {
  try {
    const res = await fetch(`${BASE}/boundary/${wardCode}`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}
