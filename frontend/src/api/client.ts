import type { ResolveResponse, AreaResponse, TabName } from '../types';

const BASE = '/api/v1';

export async function resolveSearch(query: string): Promise<ResolveResponse> {
  const res = await fetch(`${BASE}/resolve?q=${encodeURIComponent(query)}`);
  if (!res.ok) throw new Error(`Resolve failed: ${res.status}`);
  return res.json();
}

export async function fetchAreaTab(
  sessionKey: string,
  tab: TabName,
): Promise<AreaResponse> {
  const url = `${BASE}/area?session_key=${encodeURIComponent(sessionKey)}&tab=${encodeURIComponent(tab)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Area fetch failed: ${res.status}`);
  return res.json();
}

export interface DataFreshnessItem {
  source_name: string;
  last_success: string | null;
  rows: number | null;
  status: 'running' | 'success' | 'failed' | 'validation_failed' | 'never_run' | string;
}

export interface DataFreshnessResponse {
  sources: DataFreshnessItem[];
}

export async function fetchDataFreshness(): Promise<DataFreshnessResponse | null> {
  try {
    const res = await fetch(`${BASE}/data-freshness`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export interface CoverageMetadata {
  live_countries: string[];
  partial_countries?: string[];
  planned_countries?: string[];
  parked_countries?: string[];
  coverage_message?: string | null;
}

export interface Suggestion {
  label: string;
  type: string;
  area: string | null;
  comparison?: string | null;
  secondary?: string | null;
  display_label?: string;
  display_type?: string;
  display_context?: string;
  selection_value?: string;
}

export interface SuggestionResponse {
  suggestions: Suggestion[];
  coverage?: CoverageMetadata | null;
}

export async function fetchSuggestions(query: string): Promise<SuggestionResponse> {
  try {
    const res = await fetch(`${BASE}/search/suggest?q=${encodeURIComponent(query)}`);
    if (!res.ok) return { suggestions: [] };
    const data = await res.json();
    return {
      suggestions: data.suggestions || [],
      coverage: data.coverage || null,
    };
  } catch {
    return { suggestions: [] };
  }
}

export interface PriceHistoryPoint {
  year: string;
  avg_price: number;
  median_price: number;
  avg_ppsf?: number;
  transactions: number;
}

export interface BedroomBreakdownPoint {
  year: string;
  bedrooms: number;
  avg_price: number;
  transaction_count: number;
}

export interface PriceHistoryResponse {
  local: PriceHistoryPoint[];
  regional: PriceHistoryPoint[];
  regional_name: string;
  by_bedrooms: BedroomBreakdownPoint[];
}

export async function fetchPriceHistory(
  sessionKey: string,
): Promise<PriceHistoryResponse | null> {
  try {
    const res = await fetch(`${BASE}/price-history?session_key=${encodeURIComponent(sessionKey)}`);
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

export async function fetchAqHistory(sessionKey: string): Promise<AqHistoryResponse | null> {
  try {
    const res = await fetch(`${BASE}/aq-history?session_key=${encodeURIComponent(sessionKey)}`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export interface ComparableArea {
  lad_code: string;
  lad_name: string;
  scope_name?: string;
  scope_type?: string;
  component_count?: number;
  component_lads?: string[];
  avg_price: number | null;
  median_rent: number | null;
  earnings: number | null;
  pm25: number | null;
  hpi_yoy: number | null;
  distance: number | null;
  similarity_pct: number;
}

export interface ComparableTarget {
  lad_name?: string;
  scope_name?: string;
  scope_type?: string;
  anchor_lad_code?: string;
  lad_count?: number;
  component_count?: number;
  component_lads?: string[];
  avg_price: number | null;
  median_rent: number | null;
  earnings: number | null;
  pm25?: number | null;
  hpi_yoy?: number | null;
  distance?: number | null;
}

export interface ComparableResponse {
  target: ComparableTarget;
  comparable: ComparableArea[];
  status?: string;
  message?: string;
  comparison_basis?: string;
}

export async function fetchComparable(sessionKey: string): Promise<ComparableResponse | null> {
  try {
    const res = await fetch(`${BASE}/comparable?session_key=${encodeURIComponent(sessionKey)}`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchMapPois(
  sessionKey: string,
  tab: string,
): Promise<GeoJSON.FeatureCollection | null> {
  try {
    const url = `${BASE}/map-pois?session_key=${encodeURIComponent(sessionKey)}&tab=${encodeURIComponent(tab)}`;
    const res = await fetch(url);
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
  sessionKey: string,
  destination: string,
): Promise<CommuteResult> {
  const res = await fetch(
    `${BASE}/commute?session_key=${encodeURIComponent(sessionKey)}&destination=${encodeURIComponent(destination)}`,
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Destination not found');
  }
  return res.json();
}

export async function fetchBoundary(
  sessionKey: string,
): Promise<GeoJSON.FeatureCollection | GeoJSON.Feature | null> {
  try {
    const res = await fetch(`${BASE}/boundary?session_key=${encodeURIComponent(sessionKey)}`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export interface ChoroplethMetadata {
  layer: string;
  unit: string;
  grain?: string | null;
  note?: string | null;
  min_value: number | null;
  max_value: number | null;
  quantiles: number[];
  lsoa_count: number;
}

export interface ChoroplethResponse extends GeoJSON.FeatureCollection {
  metadata: ChoroplethMetadata;
}

export async function fetchChoropleth(
  sessionKey: string,
  layer: string,
): Promise<ChoroplethResponse | null> {
  try {
    const url = `${BASE}/map-choropleth?session_key=${encodeURIComponent(sessionKey)}&layer=${encodeURIComponent(layer)}`;
    const res = await fetch(url);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export interface PriceByTypePoint {
  year: string;
  avg_price: number;
  median_price: number;
  transactions: number;
  avg_ppsf?: number | null;
}

export interface PriceByTypeResponse {
  by_type: Record<string, PriceByTypePoint[]>;
  parent_by_type?: Record<string, PriceByTypePoint[]>;
}

export async function fetchPriceByType(
  sessionKey: string,
): Promise<PriceByTypeResponse | null> {
  try {
    const res = await fetch(`${BASE}/price-by-type?session_key=${encodeURIComponent(sessionKey)}`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Individual transactions (paginated, sortable, filterable)
// ---------------------------------------------------------------------------

export interface Transaction {
  date: string;
  address: string;
  price: number;
  property_type: string;
  property_type_label: string;
  beds: number | null;
  beds_label: string | null;
  size_sqm: number | null;
  tenure: string;
  tenure_label: string;
  epc: string | null;
}

export interface TransactionsResponse {
  transactions: Transaction[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export async function fetchTransactions(
  sessionKey: string,
  params: {
    page?: number;
    pageSize?: number;
    sortBy?: string;
    sortDir?: string;
    propertyType?: string;
  } = {},
): Promise<TransactionsResponse> {
  const qs = new URLSearchParams({ session_key: sessionKey });
  if (params.page) qs.set('page', String(params.page));
  if (params.pageSize) qs.set('page_size', String(params.pageSize));
  if (params.sortBy) qs.set('sort_by', params.sortBy);
  if (params.sortDir) qs.set('sort_dir', params.sortDir);
  if (params.propertyType) qs.set('property_type', params.propertyType);
  const res = await fetch(`${BASE}/transactions?${qs}`);
  if (!res.ok) throw new Error(`Transactions fetch failed: ${res.status}`);
  return res.json();
}
