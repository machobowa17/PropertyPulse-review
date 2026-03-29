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

export interface Suggestion {
  label: string;
  type: string;
  area: string | null;
}

export async function fetchSuggestions(query: string): Promise<Suggestion[]> {
  try {
    const res = await fetch(`${BASE}/search/suggest?q=${encodeURIComponent(query)}`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.suggestions || [];
  } catch {
    return [];
  }
}

export interface PriceHistoryPoint {
  year: string;
  avg_price: number;
  median_price: number;
  transactions: number;
}

export interface PriceHistoryResponse {
  local: PriceHistoryPoint[];
  regional: PriceHistoryPoint[];
  regional_name: string;
}

export async function fetchPriceHistory(lad: string, ward: string, lsoa: string): Promise<PriceHistoryResponse | null> {
  try {
    const res = await fetch(`${BASE}/price-history/${lad}/${ward}/${lsoa}`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export interface AqHistoryPoint {
  year: number;
  pm25_ugm3: number | null;
  no2_ugm3: number | null;
  pm10_ugm3: number | null;
}

export interface AqHistoryResponse {
  local: AqHistoryPoint[];
  national: AqHistoryPoint[];
  lad_name: string;
}

export async function fetchAqHistory(lad: string): Promise<AqHistoryResponse | null> {
  try {
    const res = await fetch(`${BASE}/aq-history/${lad}`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export interface ComparableArea {
  lad_code: string;
  lad_name: string;
  avg_price: number;
  median_rent: number;
  earnings: number;
  pm25: number;
  hpi_yoy: number;
  distance: number;
  similarity_pct: number;
}

export interface ComparableResponse {
  target: { lad_name: string; avg_price: number; median_rent: number; earnings: number };
  comparable: ComparableArea[];
}

export async function fetchComparable(lad: string): Promise<ComparableResponse | null> {
  try {
    const res = await fetch(`${BASE}/comparable/${lad}`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchMapPois(lat: number, lon: number, tab: string): Promise<GeoJSON.FeatureCollection | null> {
  try {
    const res = await fetch(`${BASE}/map-pois?lat=${lat}&lon=${lon}&tab=${encodeURIComponent(tab)}`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export interface CommuteMode {
  mode: string;
  route_km: number;
  mins: number;
  label: string;
}

export interface CommuteResult {
  destination: string;
  straight_km: number;
  modes: {
    driving: CommuteMode;
    transit: CommuteMode;
    cycling: CommuteMode;
    walking: CommuteMode;
  };
}

export async function fetchCommute(
  originLat: number,
  originLon: number,
  destination: string,
): Promise<CommuteResult> {
  const res = await fetch(
    `${BASE}/commute?origin_lat=${originLat}&origin_lon=${originLon}&destination=${encodeURIComponent(destination)}`,
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Destination not found');
  }
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

export interface DistrictPricePoint {
  year: string;
  avg_price: number;
  median_price: number;
  transactions: number;
}

export interface DistrictPriceResponse {
  district: string;
  by_type: Record<string, DistrictPricePoint[]>;
}

export async function fetchDistrictPriceHistory(district: string): Promise<DistrictPriceResponse | null> {
  try {
    const res = await fetch(`${BASE}/district-price-history/${encodeURIComponent(district)}`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchLsoaBoundary(lsoaCode: string): Promise<GeoJSON.Feature | null> {
  try {
    const res = await fetch(`${BASE}/boundary/lsoa/${lsoaCode}`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}
