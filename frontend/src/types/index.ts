/** Bible Part 6 Section 6.1 — API response types */

export interface CoverageMetadata {
  live_countries: string[];
  partial_countries?: string[];
  planned_countries?: string[];
  parked_countries?: string[];
  coverage_message?: string | null;
}

export interface ResolveSuggestion {
  label: string;
  type: string;
  area: string | null;
  display_label?: string;
  display_context?: string;
  selection_value?: string;
}

export interface ResolveGeoEntity {
  display_name?: string | null;
}

export interface ResolveGeoComparisonScope {
  name?: string | null;
}

export interface ResolveGeo {
  entity?: ResolveGeoEntity | null;
  comparison_scope?: ResolveGeoComparisonScope | null;
}

export interface ResolveResponse {
  query: string;
  type: 'postcode' | 'postcode_district' | 'place' | 'ward' | 'lad' | 'county' | 'place_name' | 'address';
  search_mode?: 'postcode' | 'area' | 'property';
  resolved_codes?: {
    lsoa: string | null;
    msoa?: string | null;
    ward: string | null;
    lad: string | null;
    parent: string | null;
  };
  coordinates?: {
    lat: number | null;
    lon: number | null;
  };
  geo?: ResolveGeo | null;
  lsoa_count?: number;
  lsoa_codes?: string[];
  coverage?: CoverageMetadata | null;
  /** Single canonical token computed at resolve time. Pass to every data endpoint.
   *  Present on all successful resolves; absent on error/not-found responses. */
  session_key?: string;
  error?: string;
  /** Property data returned for address-type resolves */
  property?: {
    paon: string;
    saon: string | null;
    street: string;
    postcode: string;
    lat: number;
    lon: number;
    uprn: number | null;
    address_display?: string;
  };
  /** Alternative addresses for disambiguation (e.g. multiple flats at same address) */
  alternatives?: Array<{
    paon: string;
    saon: string | null;
    street: string;
    postcode: string;
    lat: number | null;
    lon: number | null;
  }>;
  suggestions?: ResolveSuggestion[];
  /** Set when an address search failed but fell back to postcode area results.
   *  Contains the original address query string for the info banner. */
  address_not_found?: string;
}

// ---------------------------------------------------------------------------
// Nested Metric contract sub-types
// ---------------------------------------------------------------------------

export interface MetricRegistryMeta {
  metric_id: string;
  section_id: string;
  metric_family: string;
  headline_label: string;
  short_label: string;
  description: string;
  decision_question: string;
  display_priority: number;
  map_binding_type: string;
  source_refresh_profile: string;
  quality_notes: string[];
  comparison_capability?: string;
  trend_capability?: string;
  interpretation_direction?: string;
  supports_persona_rendering?: boolean;
  value_type?: string;
}

export interface MetricHeadline {
  value: number | string | null;
  unit: string;
  value_type: string;
}

export interface MetricComparison {
  status: string;
  value: number | string | null;
  scope_label: string | null;
  difference_abs: number | null;
  difference_pct: number | null;
  interpretation_direction: string;
  comparison_flag: 'lower_than_parent' | 'higher_than_parent' | 'equal_to_parent' | null;
}

export interface MetricTrend {
  status: string;
  window_label: string | null;
  direction: 'up' | 'down' | 'flat' | null;
  value: number | string | null;
  series: unknown;
  parent_series: unknown;
  trend_summary: string | null;
}

export interface MetricCapsule {
  text?: string | null;
  tone?: 'positive' | 'cautionary' | 'neutral' | 'mixed' | string;
}

export interface MetricMapBinding {
  type: string;
}

// ---------------------------------------------------------------------------
// Metric — the unified contract shape.
// Flat fields preserved for backward compatibility; nested sub-objects added.
// ---------------------------------------------------------------------------

export interface Metric {
  // Flat fields (preserved from original contract)
  id: string;
  name: string;
  local_value: number | string | null;
  parent_value: number | string | null;
  unit: string;
  comparison_flag: 'lower_than_parent' | 'higher_than_parent' | 'equal_to_parent' | null;
  comparison_status: 'comparable' | 'not_comparable' | 'not_modelled_yet';
  trend_status: 'trended' | 'no_history' | 'not_modelled_yet';
  map_binding: string | MetricMapBinding | null;
  decision_question?: string | null;
  interpretation_direction?: 'lower_is_better' | 'higher_is_better' | 'neutral';
  quality_notes?: string | null;
  details: Record<string, unknown> | null;

  // Nested sub-objects (new — from build_metric_contract())
  registry: MetricRegistryMeta;
  headline: MetricHeadline;
  comparison: MetricComparison;
  trend: MetricTrend;
  capsule: MetricCapsule | null;
  quality_flags: string[];
}

export interface AreaResponse {
  tab: string;
  metrics: Metric[];
}

export type TabName =
  | 'Overview'
  | 'Property & Market'
  | 'Lifestyle & Connectivity'
  | 'Environment & Safety'
  | 'Community & Education'
  | 'Local Governance';

export type PersonaId = 'family' | 'young_professional' | 'investor' | 'retired' | 'student' | 'expat';

export interface Persona {
  id: PersonaId;
  label: string;
  icon: string;
  description: string;
}
