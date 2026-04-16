/**
 * Persona-weighted metric scoring and section ranking.
 * Adapted from Manus's personalization layer to work with our flat metric response shape.
 */
import type { Metric, PersonaId, TabName } from '../types';
import { getTakeaway, PERSONAS } from './personas';

export type PersonalizationSignal = {
  id: string;
  name: string;
  colour: 'green' | 'amber' | 'red' | 'neutral';
  weight: number;
  score: number;
  capsule: string;
  section: TabName;
  metric: Metric;
};

export type PersonaFitSummary = {
  persona: PersonaId;
  personaLabel: string;
  score: number;
  verdict: string;
  verdictText: string;
  positives: PersonalizationSignal[];
  concerns: PersonalizationSignal[];
  greenCount: number;
  amberCount: number;
  redCount: number;
  metricCount: number;
};

export type RankedSection = {
  section: TabName;
  score: number;
  metricCount: number;
  topMetricIds: string[];
  strengths: PersonalizationSignal[];
  concerns: PersonalizationSignal[];
  rationale: string;
};

/** Per-metric persona weights: 0 = irrelevant, 1 = minor, 2 = moderate, 3 = critical */
export const PERSONA_METRIC_WEIGHTS: Record<string, Partial<Record<PersonaId, number>>> = {
  avg_price: { family: 3, investor: 3, young_professional: 2, retired: 2, student: 1, expat: 2 },
  gross_yield: { investor: 3, family: 0, young_professional: 0, retired: 0, student: 0, expat: 0 },
  affordability: { young_professional: 3, student: 3, family: 2, investor: 1, retired: 1, expat: 2 },
  price_trend_yoy: { investor: 3, family: 2, young_professional: 1, retired: 1, student: 0, expat: 1 },
  nearest_station: { young_professional: 3, student: 3, family: 2, retired: 1, investor: 1, expat: 2 },
  fifteen_min_score: { retired: 3, family: 2, young_professional: 2, student: 2, investor: 1, expat: 2 },
  amenities_15min:   { retired: 2, family: 2, young_professional: 2, student: 2, investor: 1, expat: 1 },
  connectivity_index: { young_professional: 3, student: 2, family: 2, expat: 2, investor: 1, retired: 1 },
  stations_in_area:  { young_professional: 2, student: 2, family: 1, expat: 1, investor: 1, retired: 1 },
  cycling:           { young_professional: 2, student: 1, family: 1, retired: 1, investor: 0, expat: 1 },
  mobile_coverage:   { young_professional: 2, student: 1, family: 1, expat: 1, investor: 1, retired: 1 },
  ev_chargers:       { young_professional: 1, family: 1, investor: 1, student: 0, retired: 1, expat: 1 },
  wfh:               { young_professional: 1, family: 1, retired: 0, investor: 0, student: 0, expat: 1 },
  broadband: { young_professional: 3, student: 2, family: 2, investor: 1, retired: 1, expat: 2 },
  crime_rate: { family: 3, retired: 3, young_professional: 2, student: 2, investor: 2, expat: 3 },
  air_quality_pm25: { family: 3, retired: 3, young_professional: 1, student: 1, investor: 0, expat: 2 },
  flood_risk: { family: 3, investor: 3, retired: 2, young_professional: 1, student: 1, expat: 2 },
  nearest_park: { family: 3, retired: 3, young_professional: 1, student: 1, investor: 0, expat: 2 },
  noise:         { family: 3, retired: 3, young_professional: 2, student: 1, investor: 1, expat: 2 },
  green_cover:   { family: 2, retired: 2, young_professional: 1, student: 1, investor: 0, expat: 1 },
  green_spaces:  { family: 2, retired: 2, young_professional: 1, student: 1, investor: 0, expat: 1 },
  parks_1km:     { family: 2, retired: 2, young_professional: 1, student: 1, investor: 0, expat: 1 },
  sports_recreation: { young_professional: 2, family: 2, student: 1, retired: 1, investor: 0, expat: 1 },
  epc_rating:    { investor: 2, family: 2, young_professional: 1, retired: 1, student: 1, expat: 1 },
  esg_score:     { investor: 2, family: 2, young_professional: 1, retired: 1, student: 1, expat: 1 },
  primary_schools: { family: 3, expat: 3, young_professional: 0, investor: 0, retired: 0, student: 0 },
  secondary_schools: { family: 3, expat: 3, young_professional: 0, investor: 0, retired: 0, student: 0 },
  deprivation: { family: 3, retired: 2, young_professional: 1, investor: 2, student: 1, expat: 2 },
  nhs_facilities: { retired: 3, family: 2, young_professional: 1, student: 1, investor: 0, expat: 1 },
  median_earnings:    { investor: 2, young_professional: 2, family: 2, retired: 1, student: 1, expat: 2 },
  good_health:        { retired: 2, family: 1, young_professional: 1, student: 0, investor: 1, expat: 1 },
  economically_active: { investor: 2, family: 1, young_professional: 1, student: 1, retired: 1, expat: 1 },
  degree_educated:    { young_professional: 2, investor: 1, family: 1, student: 1, retired: 0, expat: 1 },
  no_car:             { young_professional: 1, student: 1, family: 1, retired: 1, investor: 0, expat: 1 },
  born_abroad:        { expat: 2, young_professional: 1, student: 1, family: 1, retired: 1, investor: 0 },
  household_size:     { family: 1, young_professional: 1, retired: 1, investor: 1, student: 1, expat: 1 },
  housing_type:       { family: 2, investor: 2, young_professional: 1, retired: 1, student: 1, expat: 1 },
  household_composition: { family: 2, young_professional: 1, student: 1, retired: 1, investor: 1, expat: 1 },
  council_tax: { investor: 2, family: 2, young_professional: 1, retired: 2, student: 1, expat: 1 },
  financial_health: { family: 2, investor: 2, retired: 2, young_professional: 1, student: 1, expat: 1 },
  epc_energy_score: { investor: 2, family: 2, young_professional: 1, retired: 1, student: 1, expat: 1 },
  epc_rating_c_plus: { investor: 2, family: 2, young_professional: 1, retired: 1, student: 1, expat: 1 },
  median_rent: { student: 3, young_professional: 3, expat: 2, family: 1, investor: 2, retired: 1 },
  median_price: { family: 2, investor: 2, young_professional: 2, retired: 2, student: 0, expat: 2 },
  price_per_sqft: { investor: 2, family: 1, young_professional: 1, retired: 1, student: 0, expat: 1 },
};

/** Static metric → tab mapping. Our backend registry uses 'section' which maps to tab name. */
const METRIC_TAB: Record<string, TabName> = {
  avg_price: 'Property & Market', median_price: 'Property & Market', transaction_volume: 'Property & Market',
  freehold_leasehold: 'Property & Market', new_build_proportion: 'Property & Market', price_trend_yoy: 'Property & Market',
  price_per_sqft: 'Property & Market', median_rent: 'Property & Market', gross_yield: 'Property & Market',
  affordability: 'Property & Market', median_earnings: 'Property & Market', investment_grade: 'Property & Market',
  epc_rating: 'Property & Market', epc_energy_score: 'Property & Market', epc_rating_c_plus: 'Property & Market',
  nearest_station: 'Lifestyle & Connectivity', stations_in_area: 'Lifestyle & Connectivity',
  ptal_score: 'Lifestyle & Connectivity', connectivity_index: 'Lifestyle & Connectivity',
  cycling: 'Lifestyle & Connectivity', broadband: 'Lifestyle & Connectivity', mobile_coverage: 'Lifestyle & Connectivity',
  ev_chargers: 'Lifestyle & Connectivity', amenities_15min: 'Lifestyle & Connectivity',
  fifteen_min_score: 'Lifestyle & Connectivity', commute_distance: 'Lifestyle & Connectivity',
  flood_risk: 'Environment & Safety', air_quality_no2: 'Environment & Safety', air_quality_pm25: 'Environment & Safety',
  noise: 'Environment & Safety', nearest_park: 'Environment & Safety', green_cover: 'Environment & Safety',
  green_spaces: 'Environment & Safety', parks_1km: 'Environment & Safety', sports_recreation: 'Environment & Safety',
  crime_rate: 'Environment & Safety', crime_trend: 'Environment & Safety', esg_score: 'Environment & Safety',
  demographics_overview: 'Community & Education', population_density: 'Community & Education',
  median_age: 'Community & Education', household_composition: 'Community & Education',
  housing_tenure: 'Community & Education', housing_type: 'Community & Education',
  household_size: 'Community & Education', ethnicity: 'Community & Education',
  good_health: 'Community & Education', economically_active: 'Community & Education',
  degree_educated: 'Community & Education', no_car: 'Community & Education', born_abroad: 'Community & Education',
  wfh: 'Community & Education',
  primary_schools: 'Community & Education', secondary_schools: 'Community & Education',
  deprivation: 'Community & Education', area_persona: 'Community & Education', nhs_facilities: 'Community & Education',
  council_tax: 'Local Governance', local_authority: 'Local Governance', controlling_party: 'Local Governance',
  water_company: 'Local Governance', financial_health: 'Local Governance',
};

const COLOUR_SCORE: Record<string, number> = {
  green: 100,
  amber: 55,
  red: 0,
  neutral: 50,
};

const TAB_ORDER: TabName[] = [
  'Property & Market', 'Lifestyle & Connectivity', 'Environment & Safety',
  'Community & Education', 'Local Governance',
];

function getPersonaLabel(persona: PersonaId): string {
  return PERSONAS.find((p) => p.id === persona)?.label || persona;
}

function colourPriority(colour: string): number {
  if (colour === 'red') return 3;
  if (colour === 'amber') return 2;
  if (colour === 'green') return 1;
  return 0;
}

function buildSignal(metric: Metric, persona: PersonaId): PersonalizationSignal | null {
  const weight = PERSONA_METRIC_WEIGHTS[metric.id]?.[persona] ?? 1;
  if (weight === 0) return null;

  const takeaway = getTakeaway(metric, persona);
  const colour = (takeaway.colour || 'neutral') as PersonalizationSignal['colour'];

  return {
    id: metric.id,
    name: metric.name,
    colour,
    weight,
    score: (COLOUR_SCORE[colour] ?? 50) * weight,
    capsule: takeaway.soWhat || 'Needs review',
    section: METRIC_TAB[metric.id] || 'Property & Market',
    metric,
  };
}

export function collectPersonaSignals(metrics: Metric[], persona: PersonaId): PersonalizationSignal[] {
  return metrics
    .map((m) => buildSignal(m, persona))
    .filter((s): s is PersonalizationSignal => s !== null);
}

export function buildPersonaFitSummary(metrics: Metric[], persona: PersonaId): PersonaFitSummary | null {
  const signals = collectPersonaSignals(metrics, persona);
  if (signals.length === 0) return null;

  const totalWeight = signals.reduce((sum, s) => sum + s.weight, 0);
  const totalScore = signals.reduce((sum, s) => sum + s.score, 0);
  const score = totalWeight > 0 ? Math.round(totalScore / totalWeight) : 50;

  const positives = signals
    .filter((s) => s.colour === 'green')
    .sort((a, b) => b.weight - a.weight || a.name.localeCompare(b.name))
    .slice(0, 3);

  const concerns = signals
    .filter((s) => s.colour === 'red' || s.colour === 'amber')
    .sort((a, b) => colourPriority(b.colour) - colourPriority(a.colour) || b.weight - a.weight)
    .slice(0, 3);

  const greenCount = signals.filter((s) => s.colour === 'green').length;
  const amberCount = signals.filter((s) => s.colour === 'amber').length;
  const redCount = signals.filter((s) => s.colour === 'red').length;

  const verdict = score >= 70 ? 'Strong fit' : score >= 45 ? 'Mixed signals' : 'Proceed carefully';
  const verdictText = score >= 70
    ? 'The balance of evidence looks favourable for this persona.'
    : score >= 45
      ? 'There are useful positives here, but the trade-offs still need checking.'
      : 'Important risks or compromises stand out for this persona.';

  return {
    persona,
    personaLabel: getPersonaLabel(persona),
    score,
    verdict,
    verdictText,
    positives,
    concerns,
    greenCount,
    amberCount,
    redCount,
    metricCount: signals.length,
  };
}

export function rankSectionsForPersona(metrics: Metric[], persona: PersonaId): RankedSection[] {
  const grouped = new Map<TabName, PersonalizationSignal[]>();

  for (const signal of collectPersonaSignals(metrics, persona)) {
    const existing = grouped.get(signal.section) ?? [];
    existing.push(signal);
    grouped.set(signal.section, existing);
  }

  const ranked = Array.from(grouped.entries()).map(([section, signals]) => {
    const totalWeight = signals.reduce((sum, s) => sum + s.weight, 0);
    const totalScore = signals.reduce((sum, s) => sum + s.score, 0);
    const score = totalWeight > 0 ? Math.round(totalScore / totalWeight) : 50;

    const strengths = signals.filter((s) => s.colour === 'green')
      .sort((a, b) => b.weight - a.weight).slice(0, 2);
    const concerns = signals.filter((s) => s.colour === 'red' || s.colour === 'amber')
      .sort((a, b) => colourPriority(b.colour) - colourPriority(a.colour) || b.weight - a.weight).slice(0, 2);
    const topMetricIds = signals.slice()
      .sort((a, b) => b.weight - a.weight || colourPriority(b.colour) - colourPriority(a.colour))
      .slice(0, 3).map((s) => s.id);

    const rationale = strengths.length > 0
      ? `${strengths[0].name} currently looks strongest for this persona.`
      : concerns.length > 0
        ? `${concerns[0].name} is the main trade-off to check for this persona.`
        : 'This section has more neutral evidence than standout signals right now.';

    return { section, score, metricCount: signals.length, topMetricIds, strengths, concerns, rationale };
  });

  return ranked.sort((a, b) => {
    const orderA = TAB_ORDER.indexOf(a.section);
    const orderB = TAB_ORDER.indexOf(b.section);
    return b.score - a.score || a.metricCount - b.metricCount || orderA - orderB;
  });
}
