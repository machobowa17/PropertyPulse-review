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
  type: 'postcode' | 'postcode_district' | 'place' | 'ward' | 'lad' | 'county' | 'place_name';
  search_mode?: 'postcode' | 'area';
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
  suggestions?: ResolveSuggestion[];
}

export interface Metric {
  id: string;
  name: string;
  local_value: number | string | null;
  parent_value: number | string | null;
  unit: string;
  comparison_flag: 'lower_than_parent' | 'higher_than_parent' | 'equal_to_parent' | null;
  comparison_status: 'comparable' | 'not_comparable' | 'not_modelled_yet';
  trend_status: 'trended' | 'no_history' | 'not_modelled_yet';
  map_binding: string;
  decision_question?: string | null;
  interpretation_direction?: 'lower_is_better' | 'higher_is_better' | 'neutral';
  quality_notes?: string | null;
  details: Record<string, unknown> | null;
}

export interface AreaResponse {
  tab: string;
  metrics: Metric[];
}

export type TabName =
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
