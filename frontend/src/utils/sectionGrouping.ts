/**
 * Section grouping for the results panel accordion.
 *
 * Groups metrics by their registry.metric_family into display sections,
 * with per-metric overrides for ambiguous families (e.g. property_prices
 * contains both "Prices & Value" metrics and "Trends" metrics).
 */
import {
  PoundSterling, TrendingUp, BarChart3, Receipt, Building2,
  Train, Wifi, ShoppingBag, Shield, Wind, Leaf,
  UserCircle, Globe, GraduationCap, Scale, HeartPulse, Landmark,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { Metric } from '../types';

// ─── Section config ──────────────────────────────────────────────────

export interface SectionConfig {
  id: string;
  label: string;
  icon: LucideIcon;
  sortOrder: number;
}

const SECTIONS: Record<string, SectionConfig> = {
  prices_value:        { id: 'prices_value',        label: 'Prices & Value',       icon: PoundSterling, sortOrder: 1 },
  market_activity:     { id: 'market_activity',      label: 'Market Activity',      icon: TrendingUp,    sortOrder: 2 },
  trends:              { id: 'trends',               label: 'Trends',               icon: BarChart3,     sortOrder: 3 },
  costs_income:        { id: 'costs_income',         label: 'Costs & Income',       icon: Receipt,       sortOrder: 4 },
  housing_stock:       { id: 'housing_stock',        label: 'Housing Stock',        icon: Building2,     sortOrder: 5 },
  transport_access:    { id: 'transport_access',     label: 'Transport & Access',   icon: Train,         sortOrder: 6 },
  digital_connectivity:{ id: 'digital_connectivity', label: 'Digital Connectivity', icon: Wifi,          sortOrder: 7 },
  amenities:           { id: 'amenities',            label: 'Amenities',            icon: ShoppingBag,   sortOrder: 8 },
  safety:              { id: 'safety',               label: 'Safety',               icon: Shield,        sortOrder: 9 },
  environment:         { id: 'environment',          label: 'Environment',          icon: Wind,          sortOrder: 10 },
  green_space:         { id: 'green_space',          label: 'Green Space',          icon: Leaf,          sortOrder: 11 },
  people:              { id: 'people',               label: 'People',               icon: UserCircle,    sortOrder: 12 },
  diversity:           { id: 'diversity',            label: 'Diversity',            icon: Globe,         sortOrder: 13 },
  schools:             { id: 'schools',              label: 'Schools',              icon: GraduationCap, sortOrder: 14 },
  deprivation:         { id: 'deprivation',          label: 'Deprivation',          icon: Scale,         sortOrder: 15 },
  health_services:     { id: 'health_services',      label: 'Health Services',      icon: HeartPulse,    sortOrder: 16 },
  governance:          { id: 'governance',           label: 'Governance',           icon: Landmark,      sortOrder: 17 },
};

// ─── Metric family → display section mapping ─────────────────────────

const FAMILY_TO_SECTION: Record<string, string> = {
  property_prices:          'prices_value',
  affordability:            'prices_value',
  market_activity:          'market_activity',
  tenure_mix:               'market_activity',
  housing_supply:           'market_activity',
  rents:                    'costs_income',
  investment:               'costs_income',
  earnings:                 'costs_income',
  energy_efficiency:        'housing_stock',
  housing_mix:              'housing_stock',
  transport_access:         'transport_access',
  transport_infrastructure: 'transport_access',
  active_travel:            'transport_access',
  commuting:                'transport_access',
  connectivity:             'digital_connectivity',
  amenities:                'amenities',
  crime:                    'safety',
  flood_risk:               'environment',
  air_quality:              'environment',
  noise:                    'environment',
  environment_composite:    'environment',
  green_space:              'green_space',
  green_space_access:       'green_space',
  recreation:               'green_space',
  demographics:             'people',
  households:               'people',
  health_profile:           'people',
  employment_profile:       'people',
  education_profile:        'people',
  car_dependence:           'people',
  persona_inference:        'people',
  schools:                  'schools',
  deprivation:              'deprivation',
  health_access:            'health_services',
  local_governance:         'governance',
  utilities:                'governance',
};

// Metric-level overrides for ambiguous families or metrics without registry entries
const METRIC_SECTION_OVERRIDE: Record<string, string> = {
  price_trend_yoy:                'trends',
  official_hpi:                   'trends',
  price_spread:                   'trends',
  ethnicity:                      'diversity',
  religion:                       'diversity',
  commute_distance:               'transport_access',
  // Sub-deprivation metrics (no registry entry, family defaults to "general")
  deprivation_income:             'deprivation',
  deprivation_employment:         'deprivation',
  deprivation_education:          'deprivation',
  deprivation_health:             'deprivation',
  deprivation_crime:              'deprivation',
  deprivation_barriers:           'deprivation',
  deprivation_living_environment: 'deprivation',
};

// ─── Grouping function ───────────────────────────────────────────────

export interface MetricSection {
  config: SectionConfig;
  metrics: Metric[];
}

export function groupMetricsBySection(metrics: Metric[]): MetricSection[] {
  const visible = metrics.filter(m => m.local_value != null);
  const sectionMap = new Map<string, Metric[]>();

  for (const m of visible) {
    // 1. Check metric-level override first
    let sectionId = METRIC_SECTION_OVERRIDE[m.id];
    if (!sectionId) {
      // 2. Fall back to family-level mapping
      const family = m.registry?.metric_family ?? 'general';
      sectionId = FAMILY_TO_SECTION[family] ?? undefined;
    }
    if (!sectionId) sectionId = 'other';

    const arr = sectionMap.get(sectionId) ?? [];
    arr.push(m);
    sectionMap.set(sectionId, arr);
  }

  const sections: MetricSection[] = [];
  for (const [sectionId, sectionMetrics] of sectionMap) {
    const config = SECTIONS[sectionId] ?? {
      id: sectionId, label: 'Other', icon: BarChart3, sortOrder: 99,
    };
    sectionMetrics.sort((a, b) =>
      (a.registry?.display_priority ?? 99) - (b.registry?.display_priority ?? 99)
    );
    sections.push({ config, metrics: sectionMetrics });
  }

  sections.sort((a, b) => a.config.sortOrder - b.config.sortOrder);
  return sections;
}

// ─── Summary pills ───────────────────────────────────────────────────

// Metrics that are redundant with each other — if one is shown, skip the rest
const REDUNDANT_GROUPS: string[][] = [
  ['avg_price', 'median_price'],
  ['primary_schools', 'secondary_schools'],
  ['air_quality_no2', 'air_quality_pm25'],
  ['green_cover', 'nearest_park', 'parks_1km', 'green_spaces'],
  ['housing_tenure', 'housing_type'],
  ['median_rent', 'gross_yield'],
  ['deprivation', 'deprivation_income', 'deprivation_employment', 'deprivation_education', 'deprivation_health', 'deprivation_crime', 'deprivation_barriers', 'deprivation_living'],
  ['household_composition', 'household_size'],
  ['crime_rate', 'crime_trend'],
  ['nearest_station', 'stations_in_area'],
  ['broadband', 'mobile_coverage'],
];

// Priority ordering — lower = more important
const METRIC_PRIORITY: Record<string, number> = {
  avg_price: 1, transaction_volume: 2, price_trend_yoy: 3, crime_rate: 4,
  amenities_15min: 5, primary_schools: 6, deprivation: 7, flood_risk: 8,
  median_rent: 9, council_tax: 10, nearest_station: 11, broadband: 12,
  demographics_overview: 13, ethnicity: 14, epc_energy_score: 15,
  freehold_leasehold: 16, new_build_proportion: 17, official_hpi: 18,
  ptal_score: 19, green_cover: 20, noise: 21, air_quality_no2: 22,
  median_age: 23, household_composition: 24, commute_distance: 25,
  controlling_party: 26, local_authority: 27, water_company: 28,
};

export function pickSummaryPills(metrics: Metric[], max = 3): Metric[] {
  const sorted = [...metrics].sort((a, b) => {
    const pa = METRIC_PRIORITY[a.id] ?? 50;
    const pb = METRIC_PRIORITY[b.id] ?? 50;
    return pa - pb;
  });
  const picked: Metric[] = [];
  const usedGroups = new Set<number>();
  for (const m of sorted) {
    if (picked.length >= max) break;
    const groupIdx = REDUNDANT_GROUPS.findIndex(g => g.includes(m.id));
    if (groupIdx !== -1 && usedGroups.has(groupIdx)) continue;
    picked.push(m);
    if (groupIdx !== -1) usedGroups.add(groupIdx);
  }
  return picked;
}

export function pillColor(flag: Metric['comparison_flag']): string {
  if (flag === 'higher_than_parent') return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (flag === 'lower_than_parent') return 'bg-orange-50 text-orange-700 border-orange-200';
  return 'bg-slate-50 text-slate-600 border-slate-200';
}

// ─── Section badge ───────────────────────────────────────────────────

export function sectionBadgeText(metrics: Metric[]): string | null {
  const above = metrics.filter(m => m.comparison_flag === 'higher_than_parent').length;
  const below = metrics.filter(m => m.comparison_flag === 'lower_than_parent').length;
  const equal = metrics.filter(m => m.comparison_flag === 'equal_to_parent').length;
  if (above + below + equal === 0) return null;
  if (above >= below) return above > equal ? 'Above Average' : 'Average';
  return 'Below Average';
}

export function sectionBadgeColor(text: string | null): string {
  if (text === 'Above Average') return 'text-signal-green bg-signal-green-bg border-signal-green/20';
  if (text === 'Below Average') return 'text-signal-amber bg-signal-amber-bg border-signal-amber/20';
  if (text === 'Average') return 'text-ink-muted bg-surface-warm border-divider';
  return '';
}
