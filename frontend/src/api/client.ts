import type { ResolveResponse, AreaResponse, TabName, CoverageMetadata } from '../types';
import { AreaResponseSchema } from '../schemas/area';

const BASE = '/api/v1';

/** Fetch with automatic retry on 429 (rate-limited). Retries up to 2 times with exponential backoff. */
async function fetchWithRetry(input: RequestInfo | URL, init?: RequestInit, retries = 2): Promise<Response> {
  let res = await fetch(input, init);
  for (let i = 0; i < retries && res.status === 429; i++) {
    const retryAfter = res.headers.get('Retry-After');
    const delay = retryAfter ? Math.min(Number(retryAfter) * 1000, 10000) : (i + 1) * 1500;
    await new Promise((r) => setTimeout(r, delay));
    res = await fetch(input, init);
  }
  return res;
}

export async function resolveSearch(query: string): Promise<ResolveResponse> {
  const res = await fetchWithRetry(`${BASE}/resolve?q=${encodeURIComponent(query)}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Resolve failed: ${res.status}`);
  return res.json();
}

export class SessionExpiredError extends Error {
  constructor() {
    super('SESSION_EXPIRED');
    this.name = 'SessionExpiredError';
  }
}

export async function fetchAreaTab(
  sessionKey: string,
  tab: TabName,
): Promise<AreaResponse> {
  const url = `${BASE}/area?session_key=${encodeURIComponent(sessionKey)}&tab=${encodeURIComponent(tab)}`;
  const res = await fetchWithRetry(url, { cache: 'no-store' });
  if (res.status === 410) throw new SessionExpiredError();
  if (!res.ok) throw new Error(`Area fetch failed: ${res.status}`);
  const json = await res.json();
  // R8: validate response shape — surface parse errors early rather than blank MetricCard panels
  const parsed = AreaResponseSchema.safeParse(json);
  if (!parsed.success) {
    console.warn('[client] /area response failed schema validation:', parsed.error.flatten());
    // Fall back to raw JSON — passthrough schemas may lag behind new backend fields
    return json as AreaResponse;
  }
  return parsed.data as unknown as AreaResponse;
}

export type { CoverageMetadata };

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
    const res = await fetchWithRetry(`${BASE}/search/suggest?q=${encodeURIComponent(query)}`);
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
  median_price?: number;
  avg_ppsf?: number;
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
    const res = await fetchWithRetry(`${BASE}/price-history?session_key=${encodeURIComponent(sessionKey)}`, { cache: 'no-store' });
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
    const res = await fetchWithRetry(`${BASE}/aq-history?session_key=${encodeURIComponent(sessionKey)}`, { cache: 'no-store' });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export interface WikiImage {
  url: string;
  width: number;
  height: number;
  original_url?: string;
}

export interface WikiSummary {
  title: string;
  extract: string;
  url: string;
  image: WikiImage | null;
}

export interface WikiSummaryResponse {
  summary: WikiSummary | null;
  search_term?: string;
}

export async function fetchWikiSummary(sessionKey: string): Promise<WikiSummaryResponse | null> {
  try {
    const res = await fetchWithRetry(`${BASE}/wiki-summary?session_key=${encodeURIComponent(sessionKey)}`, { cache: 'no-store' });
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
    const res = await fetchWithRetry(`${BASE}/comparable?session_key=${encodeURIComponent(sessionKey)}`, { cache: 'no-store' });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export type MapPoisResponse = GeoJSON.FeatureCollection & { sold_prices_since?: string };

export async function fetchMapPois(
  sessionKey: string,
  tab: string,
): Promise<MapPoisResponse | null> {
  try {
    const url = `${BASE}/map-pois?session_key=${encodeURIComponent(sessionKey)}&tab=${encodeURIComponent(tab)}`;
    const res = await fetchWithRetry(url, { cache: 'no-store' });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchBoundary(
  sessionKey: string,
): Promise<GeoJSON.FeatureCollection | GeoJSON.Feature | null> {
  try {
    const res = await fetchWithRetry(`${BASE}/boundary?session_key=${encodeURIComponent(sessionKey)}`, { cache: 'no-store' });
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

export function buildChoroplethUrl(sessionKey: string, layer: string): string {
  return `${BASE}/map-choropleth?session_key=${encodeURIComponent(sessionKey)}&layer=${encodeURIComponent(layer)}`;
}

export async function fetchChoropleth(
  sessionKey: string,
  layer: string,
): Promise<ChoroplethResponse | null> {
  try {
    const url = buildChoroplethUrl(sessionKey, layer);
    const res = await fetchWithRetry(url, { cache: 'no-store' });
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
    const res = await fetchWithRetry(`${BASE}/price-by-type?session_key=${encodeURIComponent(sessionKey)}`, { cache: 'no-store' });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Per-transaction EPC certificate details (lazy-loaded from Hetzner)
// ---------------------------------------------------------------------------

export interface TransactionEpc {
  construction_age_band: string | null;
  built_form: string | null;
  mainheat_description: string | null;
  main_fuel: string | null;
  energy_consumption_current: number | null;
  co2_emissions_current: number | null;
  heating_cost_current: number | null;
  hot_water_cost_current: number | null;
  lighting_cost_current: number | null;
  windows_description: string | null;
  walls_description: string | null;
  roof_description: string | null;
  floor_description: string | null;
  solar_water_heating_flag: string | null;
  photo_supply: number | null;
  mains_gas_flag: string | null;
  number_heated_rooms: number | null;
  floor_level: string | null;
  tenure: string | null;
  inspection_date: string | null;
  potential_energy_rating: string | null;
  current_energy_rating: string | null;
  low_energy_lighting: number | null;
  extension_count: number | null;
}

export async function fetchTransactionEpc(
  sessionKey: string,
  transactionId: string,
): Promise<TransactionEpc | null> {
  try {
    const res = await fetchWithRetry(
      `${BASE}/transactions/${encodeURIComponent(transactionId)}/epc?session_key=${encodeURIComponent(sessionKey)}`,
      { cache: 'no-store' },
    );
    if (!res.ok) return null;
    const data = await res.json();
    return data.epc ?? null;
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
  transaction_id: string;
  postcode: string;
  paon: string;
  saon: string;
  street: string;
  price: number;
  property_type: string;
  property_type_label: string;
  beds: number | null;
  beds_label: string | null;
  size_sqm: number | null;
  tenure: string;
  tenure_label: string;
  epc: string | null;
  lat: number | null;
  lon: number | null;
  new_build?: boolean;
  price_per_sqft?: number | null;
  ppd_category?: string | null;
  locality?: string | null;
  habitable_rooms?: number | null;
  epc_match_score?: number | null;
  area_avg_price?: number | null;
  area_median_price?: number | null;
  area_sales_count?: number | null;
}

export interface PropertyHistoryEntry {
  date: string;
  price: number;
  property_type: string;
  property_type_label: string;
  beds: number | null;
  size_sqm: number | null;
  tenure: string;
  tenure_label: string;
  epc: string | null;
}

export interface PropertyHistoryResponse {
  history: PropertyHistoryEntry[];
  count: number;
}

export interface TransactionsResponse {
  transactions: Transaction[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  available_years?: number[];
}

export async function fetchTransactions(
  sessionKey: string,
  params: {
    page?: number;
    pageSize?: number;
    sortBy?: string;
    sortDir?: string;
    propertyType?: string;
    year?: number;
  } = {},
  _searchQuery?: string,
): Promise<TransactionsResponse> {
  const qs = new URLSearchParams({ session_key: sessionKey });
  if (params.page) qs.set('page', String(params.page));
  if (params.pageSize) qs.set('page_size', String(params.pageSize));
  if (params.sortBy) qs.set('sort_by', params.sortBy);
  if (params.sortDir) qs.set('sort_dir', params.sortDir);
  if (params.propertyType) qs.set('property_type', params.propertyType);
  if (params.year) qs.set('year', String(params.year));
  let url = `${BASE}/transactions?${qs}`;
  let res = await fetchWithRetry(url, { cache: 'no-store' });
  if (res.status === 410 && _searchQuery) {
    // Session expired — re-resolve to get a fresh session_key, then retry once
    const resolveRes = await fetchWithRetry(
      `${BASE}/resolve?q=${encodeURIComponent(_searchQuery)}`,
      { cache: 'no-store' },
    );
    if (resolveRes.ok) {
      const resolved = await resolveRes.json();
      if (resolved.session_key) {
        qs.set('session_key', resolved.session_key);
        url = `${BASE}/transactions?${qs}`;
      }
      res = await fetchWithRetry(url, { cache: 'no-store' });
    }
  }
  if (res.status === 410) throw new SessionExpiredError();
  if (!res.ok) throw new Error(`Transactions fetch failed: ${res.status}`);
  return res.json();
}

// ── Property-specific data (P53) ─────────────────────────────────────────────

/** Transaction record from Hetzner Property API */
export interface PropertyTransaction {
  transaction_id?: string;
  price?: number;
  date_of_transfer?: string;
  property_type?: string;
  old_new?: string;
  duration?: string;
  paon?: string;
  saon?: string;
  street?: string;
  postcode?: string;
  lsoa_code?: string;
  [key: string]: unknown;
}

/** EPC record — full 93-column domestic EPC from Hetzner */
export interface PropertyEpc {
  lodgement_date?: string;
  current_energy_rating?: string;
  potential_energy_rating?: string;
  current_energy_efficiency?: number;
  potential_energy_efficiency?: number;
  property_type?: string;
  built_form?: string;
  construction_age_band?: string;
  tenure?: string;
  total_floor_area?: number;
  number_habitable_rooms?: number;
  main_heating_description?: string;
  main_fuel?: string;
  hotwater_description?: string;
  floor_description?: string;
  walls_description?: string;
  roof_description?: string;
  windows_description?: string;
  lighting_description?: string;
  solar_water_heating_flag?: string;
  photo_supply?: number;
  energy_consumption_current?: number;
  co2_emissions_current?: number;
  co2_emissions_potential?: number;
  lighting_cost_current?: number;
  lighting_cost_potential?: number;
  heating_cost_current?: number;
  heating_cost_potential?: number;
  hot_water_cost_current?: number;
  hot_water_cost_potential?: number;
  environment_impact_current?: number;
  environment_impact_potential?: number;
  uprn?: number;
  [key: string]: unknown;
}

export interface PropertyDataResponse {
  coordinates: { lat: number; lon: number };
  address: {
    paon: string | null;
    saon: string | null;
    street: string | null;
    postcode: string | null;
    uprn: number | null;
  };
  transactions: PropertyTransaction[];
  epc: PropertyEpc | null;
  epc_history: PropertyEpc[];
  parcel: {
    inspire_id: string;
    authority: string;
    geojson: GeoJSON.Geometry;
  } | null;
  flood_zone: string | null;
  llc_charges: Array<{ charge_type: string; authority?: string; valid_from?: string | null }>;
  noise: { road_db: number | null; rail_db: number | null } | null;
  broadband: {
    avg_download: number | null;
    avg_upload: number | null;
    superfast_pct: number | null;
    ultrafast_pct: number | null;
    gigabit_pct: number | null;
    fttp_pct: number | null;
  } | null;
  crime: {
    total_12m: number;
    categories: Array<{ category: string; count: number }>;
  } | null;
}

export async function fetchPropertyData(
  sessionKey: string,
  lat: number,
  lon: number,
  postcode?: string | null,
  paon?: string | null,
  saon?: string | null,
  street?: string | null,
  uprn?: number | null,
  lsoa?: string | null,
): Promise<PropertyDataResponse> {
  const qs = new URLSearchParams({
    session_key: sessionKey,
    lat: lat.toString(),
    lon: lon.toString(),
  });
  if (postcode) qs.set('postcode', postcode);
  if (paon) qs.set('paon', paon);
  if (saon) qs.set('saon', saon);
  if (street) qs.set('street', street);
  if (uprn) qs.set('uprn', uprn.toString());
  if (lsoa) qs.set('lsoa', lsoa);
  const res = await fetchWithRetry(`${BASE}/area/property?${qs}`, { cache: 'no-store' });
  if (res.status === 410) throw new SessionExpiredError();
  if (!res.ok) throw new Error(`Property data fetch failed: ${res.status}`);
  return res.json();
}

export interface ReverseGeocodeResponse {
  type: 'property' | 'area';
  property?: {
    paon: string;
    saon: string | null;
    street: string;
    postcode: string;
    lat: number;
    lon: number;
    lsoa_code: string;
    uprn: number | null;
  };
  lsoa_code?: string | null;
  coordinates?: { lat: number; lon: number };
  distance_m?: number;
}

export async function fetchReverseGeocode(lat: number, lon: number): Promise<ReverseGeocodeResponse> {
  const res = await fetchWithRetry(
    `${BASE}/reverse-geocode?lat=${lat}&lon=${lon}`,
    { cache: 'no-store' },
  );
  if (!res.ok) throw new Error(`Reverse geocode failed: ${res.status}`);
  return res.json();
}

export async function fetchPropertyHistory(
  sessionKey: string,
  postcode: string,
  paon: string,
  saon: string,
  street: string,
  excludeId: string,
  _searchQuery?: string,
): Promise<PropertyHistoryResponse> {
  const qs = new URLSearchParams({
    session_key: sessionKey,
    postcode,
    paon,
    saon: saon || '',
    street,
    exclude_id: excludeId,
  });
  let url = `${BASE}/transactions/history?${qs}`;
  let res = await fetchWithRetry(url, { cache: 'no-store' });
  if (res.status === 410 && _searchQuery) {
    const resolveRes = await fetchWithRetry(
      `${BASE}/resolve?q=${encodeURIComponent(_searchQuery)}`,
      { cache: 'no-store' },
    );
    if (resolveRes.ok) {
      const resolved = await resolveRes.json();
      if (resolved.session_key) {
        qs.set('session_key', resolved.session_key);
        url = `${BASE}/transactions/history?${qs}`;
      }
      res = await fetchWithRetry(url, { cache: 'no-store' });
    }
  }
  if (res.status === 410) throw new SessionExpiredError();
  if (!res.ok) throw new Error(`Property history fetch failed: ${res.status}`);
  return res.json();
}
