/** Bible Part 4 — 5-Tab Information Architecture */
import type { TabName } from '../types';

export interface TabConfig {
  name: TabName;
  icon: string;
  shortName: string;
  colour: string;
  bgColour: string;
}

export const TABS: TabConfig[] = [
  { name: 'Property & Market', icon: 'TrendingUp', shortName: 'Property', colour: '#2563eb', bgColour: '#eff6ff' },
  { name: 'Lifestyle & Connectivity', icon: 'Coffee', shortName: 'Lifestyle', colour: '#7c3aed', bgColour: '#f5f3ff' },
  { name: 'Environment & Safety', icon: 'Leaf', shortName: 'Environment', colour: '#059669', bgColour: '#ecfdf5' },
  { name: 'Community & Education', icon: 'Users', shortName: 'Community', colour: '#ea580c', bgColour: '#fff7ed' },
  { name: 'Local Governance', icon: 'Landmark', shortName: 'Governance', colour: '#0891b2', bgColour: '#ecfeff' },
];

/** Friendly unit formatting */
export function formatValue(value: number | string | null, unit: string): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'string') return value;

  if (unit === 'GBP' || unit === 'GBP/year' || unit === 'GBP/month') {
    return '£' + value.toLocaleString('en-GB', { maximumFractionDigits: 0 });
  }
  if (unit === '%' || unit === '% of workers' || unit === '% commuters' || unit === '% 4G outdoor') {
    return value.toFixed(1) + '%';
  }
  if (unit.startsWith('% ')) {
    return value.toFixed(1) + unit;  // e.g. "100.0% leasehold", "45.2% of income"
  }
  if (unit === 'metres') {
    return value >= 1000 ? (value / 1000).toFixed(1) + ' km' : Math.round(value) + ' m';
  }
  if (unit === 'GBP/sqft') return '£' + Math.round(value).toLocaleString('en-GB') + '/sqft';
  if (unit === 'grade') return String(value);
  if (unit === 'score /100') return Math.round(value) + '/100';
  if (unit === 'party' || unit === 'provider' || unit === 'status' || unit === 'persona' || unit === 'name' || unit === 'level') return String(value);
  if (unit === 'per 1,000') return value.toFixed(1) + ' per 1k';
  if (unit === 'µg/m³') return value.toFixed(1) + ' µg/m³';
  if (unit === 'dB') return value.toFixed(0) + ' dB';
  if (unit === 'people/hectare') return value.toLocaleString('en-GB', { maximumFractionDigits: 0 }) + '/ha';
  if (unit === 'years') return value.toFixed(1) + ' yrs';
  if (unit === 'sales/LSOA') return value.toLocaleString('en-GB', { maximumFractionDigits: 1 }) + ' sales/LSOA';
  if (unit === 'sales') return value.toLocaleString('en-GB', { maximumFractionDigits: 0 }) + ' sales';
  if (unit === 'count/LSOA') return value.toLocaleString('en-GB', { maximumFractionDigits: 1 }) + '/LSOA';
  if (unit === 'count') return value.toLocaleString('en-GB');
  if (unit === 'score' || unit.startsWith('score')) return value.toFixed(1);
  return String(value);
}

/** Metric icons */
export const METRIC_ICONS: Record<string, string> = {
  avg_price: 'PoundSterling',
  median_price: 'BarChart3',
  transaction_volume: 'Activity',
  freehold_leasehold: 'Scale',
  new_build_proportion: 'Building2',
  price_trend_yoy: 'TrendingUp',
  median_rent: 'Home',
  gross_yield: 'Percent',
  price_per_sqft: 'Ruler',
  affordability: 'Wallet',
  investment_grade: 'Award',
  crime_rate: 'ShieldAlert',
  crime_trend: 'TrendingDown',
  religion: 'Globe',
  amenities_15min: 'MapPin',
  nearest_station: 'Train',
  ev_chargers: 'Zap',
  ptal: 'TrainFront',
  ptal_score: 'TrainFront',
  cycling: 'Bike',
  mobile_coverage: 'Smartphone',
  broadband: 'Wifi',
  flood_risk: 'Droplets',
  air_quality_no2: 'Wind',
  air_quality_pm25: 'Cloud',
  noise: 'Volume2',
  nearest_park: 'TreePine',
  green_cover: 'TreePine',
  green_spaces: 'TreePine',
  parks_1km: 'MapPin',
  sports_recreation: 'Dumbbell',
  epc_rating: 'Flame',
  demographics_overview: 'Users',
  population_density: 'Users',
  median_age: 'Clock',
  household_composition: 'Heart',
  housing_tenure: 'Key',
  housing_type: 'LayoutGrid',
  primary_schools: 'GraduationCap',
  secondary_schools: 'School',
  deprivation: 'BarChart2',
  deprivation_income: 'BarChart2',
  deprivation_employment: 'BarChart2',
  deprivation_education: 'BarChart2',
  deprivation_health: 'BarChart2',
  deprivation_crime: 'BarChart2',
  deprivation_barriers: 'BarChart2',
  deprivation_living_environment: 'BarChart2',
  area_persona: 'Sparkles',
  nhs_facilities: 'Stethoscope',
  council_tax: 'Receipt',
  local_authority: 'Landmark',
  controlling_party: 'Vote',
  water_company: 'Droplet',
  financial_health: 'ShieldCheck',
  median_earnings: 'Banknote',
  commute_distance: 'Home',
  good_health: 'Heart',
  economically_active: 'Briefcase',
  degree_educated: 'GraduationCap',
  no_car: 'Car',
  born_abroad: 'Globe',
  epc_energy_score: 'Flame',
  official_hpi: 'TrendingUp',
  price_spread: 'ArrowUpDown',
};
