/**
 * Prototype 2 — BurbScore-inspired FULL design refresh mockup.
 *
 * Standalone page at /prototype2 with STATIC MOCK DATA covering ALL 82 metrics.
 * - Warm earth-tone palette (cream, burnt orange, sage green)
 * - 3-font system (Fraunces serif display + Plus Jakarta Sans body + JetBrains Mono data)
 * - Generous whitespace and narrower max-width (820px content)
 * - Micro-interactions (staggered reveals, hover elevations, animated underlines)
 * - Full sub-charts: price trend, crime bars, air quality gauge, demographic donut, noise scale
 * - Full tables: transactions with expand rows, schools with filter pills + detail tabs
 * - Real OSM map integration with legend overlay
 * - Homepage with rotating daily UK city map backgrounds
 * - Thematically consistent detail renderers throughout
 *
 * Does NOT touch any existing components or pages.
 */
import { useState, useMemo } from 'react';
import {
  Search, Leaf, TrendingUp, Shield, Users,
  Building2, Home, Coffee, TreePine, Landmark, ArrowRight, ArrowUpRight,
  ArrowDownRight, Minus, ChevronDown, ChevronUp,
  GraduationCap, Train, Wind, Wifi, PoundSterling,
  Scale, FileDown, Bookmark, BarChart3,
  LayoutDashboard, Globe, ShoppingBag,
  UserCircle,
  HeartPulse, MapPin,
} from 'lucide-react';

/* ══════════════════════════════════════════════════════════════════════
   DESIGN TOKENS
   ══════════════════════════════════════════════════════════════════════ */
const T = {
  pageBg:      '#FAF8F5',
  cardBg:      '#FFFFFF',
  warmBg:      '#F5F0EB',
  heroBg:      '#1C1917',
  heroGrad:    'linear-gradient(135deg, #1C1917 0%, #292524 50%, #1C1917 100%)',
  accent:      '#C2410C',
  accentLight: '#FFF7ED',
  accentMid:   '#EA580C',
  accentHover: '#9A3412',
  accentBg:    '#FED7AA',
  sage:        '#15803D',
  sageBg:      '#F0FDF4',
  sageLight:   '#DCFCE7',
  ink:         '#1C1917',
  inkMuted:    '#57534E',
  inkFaint:    '#A8A29E',
  divider:     '#E7E5E4',
  dividerSoft: '#F5F5F4',
  good:        '#059669',
  goodBg:      '#ECFDF5',
  caution:     '#D97706',
  cautionBg:   '#FFFBEB',
  bad:         '#DC2626',
  badBg:       '#FEF2F2',
  serif:       "'Fraunces', 'Playfair Display', Georgia, serif",
  sans:        "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
  mono:        "'JetBrains Mono', 'IBM Plex Mono', ui-monospace, monospace",
} as const;

/* ══════════════════════════════════════════════════════════════════════
   INTERFACES
   ══════════════════════════════════════════════════════════════════════ */
interface MockMetric {
  id: string;
  label: string;
  value: string;
  parent: string;
  unit?: string;
  direction: 'higher_is_better' | 'lower_is_better' | 'higher_is_neutral';
  chartType?: 'bars' | 'gauge' | 'noise' | 'breakdown' | 'trend' | 'stacked' | 'none';
  chartData?: any;
}

interface MockSection {
  id: string;
  title: string;
  icon: React.ElementType;
  iconColor: string;
  metrics: MockMetric[];
}

/* ══════════════════════════════════════════════════════════════════════
   MOCK DATA — AREA
   ══════════════════════════════════════════════════════════════════════ */
const AREA = { name: 'Coulsdon', parent: 'Croydon', county: 'Greater London', type: 'Ward', lsoaCount: 7 };

/* ══════════════════════════════════════════════════════════════════════
   OVERVIEW TAB — 10 headline metrics
   ══════════════════════════════════════════════════════════════════════ */
const HEADLINE_METRICS = [
  { id: 'overview_avg_price', label: 'Avg Price', value: '£485,200', parent: '£412,800', direction: 'higher_is_neutral' as const, icon: PoundSterling, trend: '+3.2%' },
  { id: 'overview_council_tax', label: 'Council Tax', value: '£1,891', parent: '£1,724', direction: 'lower_is_better' as const, icon: Building2, trend: '+4.1%' },
  { id: 'overview_nearest_station', label: 'Nearest Station', value: '0.6 mi', parent: '1.2 mi', direction: 'lower_is_better' as const, icon: Train, trend: null },
  { id: 'overview_broadband', label: 'Broadband', value: '72 Mbps', parent: '64 Mbps', direction: 'higher_is_better' as const, icon: Wifi },
  { id: 'overview_crime_rate', label: 'Crime Rate', value: '62.4', parent: '89.1', direction: 'lower_is_better' as const, icon: Shield, unit: 'per 1k', trend: '-8.3%' },
  { id: 'overview_air_quality', label: 'Air Quality', value: '10.2', parent: '11.8', direction: 'lower_is_better' as const, icon: Wind, unit: 'µg/m³', trend: '-1.1%' },
  { id: 'overview_median_age', label: 'Median Age', value: '38', parent: '35', direction: 'higher_is_neutral' as const, icon: Users },
  { id: 'overview_deprivation', label: 'IMD Decile', value: '7', parent: '5', direction: 'higher_is_better' as const, icon: Scale },
  { id: 'overview_pop_density', label: 'Pop Density', value: '48.2', parent: '72.1', direction: 'higher_is_neutral' as const, icon: UserCircle, unit: 'people/ha' },
  { id: 'overview_degree_educated', label: 'Degree %', value: '42.1%', parent: '38.6%', direction: 'higher_is_better' as const, icon: GraduationCap },
];

const TAB_SCORES = [
  { tab: 'Property & Market', icon: Home, score: 72, colour: '#C2410C' },
  { tab: 'Lifestyle & Connectivity', icon: Coffee, score: 81, colour: '#7C3AED' },
  { tab: 'Environment & Safety', icon: TreePine, score: 68, colour: '#059669' },
  { tab: 'Community & Education', icon: Users, score: 77, colour: '#EA580C' },
  { tab: 'Local Governance', icon: Landmark, score: 54, colour: '#0891B2' },
];

const COMPARABLE_AREAS = [
  { name: 'Purley', parent: 'Croydon', match: 87, avgPrice: '£462,100', crimeRate: '58.2' },
  { name: 'Sanderstead', parent: 'Croydon', match: 83, avgPrice: '£521,400', crimeRate: '41.7' },
  { name: 'Kenley', parent: 'Croydon', match: 79, avgPrice: '£445,800', crimeRate: '52.9' },
];

/* ══════════════════════════════════════════════════════════════════════
   PROPERTY & MARKET TAB — 17 metrics in 5 sections
   ══════════════════════════════════════════════════════════════════════ */
const PROPERTY_SECTIONS: MockSection[] = [
  {
    id: 'prices_value', title: 'Prices & Value', icon: PoundSterling, iconColor: '#C2410C',
    metrics: [
      { id: 'avg_price', label: 'Avg Price', value: '£485,200', parent: '£412,800', direction: 'higher_is_neutral', chartType: 'trend', chartData: { points: [448, 455, 442, 451, 460, 472, 468, 478, 485], labels: ['Apr 23','Jul 23','Oct 23','Jan 24','Apr 24','Jul 24','Oct 24','Jan 25','Apr 25'] } },
      { id: 'median_price', label: 'Median Price', value: '£462,000', parent: '£395,000', direction: 'higher_is_neutral' },
      { id: 'price_per_sqft', label: '£/sqft', value: '£412', parent: '£368', unit: 'GBP/sqft', direction: 'higher_is_neutral' },
      { id: 'price_spread', label: 'Price Spread', value: '£285k–£780k', parent: '£210k–£650k', direction: 'higher_is_neutral' },
      { id: 'affordability', label: 'Affordability', value: '34.2%', parent: '29.8%', unit: '% of income', direction: 'lower_is_better' },
    ],
  },
  {
    id: 'market_activity', title: 'Market Activity', icon: TrendingUp, iconColor: '#7C3AED',
    metrics: [
      { id: 'transaction_volume', label: 'Transactions', value: '142', parent: '118', unit: 'sales / 13mo', direction: 'higher_is_better' },
      { id: 'freehold_leasehold', label: 'Freehold Share', value: '72%', parent: '64%', direction: 'higher_is_neutral', chartType: 'bars', chartData: [{ label: 'Freehold', pct: 72 }, { label: 'Leasehold', pct: 28 }] },
      { id: 'new_build_proportion', label: 'New-build Share', value: '8.2%', parent: '12.4%', direction: 'higher_is_neutral' },
    ],
  },
  {
    id: 'trends', title: 'Trends', icon: BarChart3, iconColor: '#2563EB',
    metrics: [
      { id: 'price_trend_yoy', label: 'Price Trend YoY', value: '+3.2%', parent: '+2.8%', direction: 'higher_is_better' },
      { id: 'official_hpi', label: 'ONS HPI', value: '+4.1%', parent: '+3.5%', direction: 'higher_is_neutral' },
    ],
  },
  {
    id: 'costs_income', title: 'Costs & Income', icon: Building2, iconColor: '#0891B2',
    metrics: [
      { id: 'median_rent', label: 'Median Rent', value: '£1,450', parent: '£1,280', unit: 'GBP/month', direction: 'lower_is_better' },
      { id: 'gross_yield', label: 'Gross Yield', value: '3.6%', parent: '3.9%', direction: 'higher_is_better' },
      { id: 'median_earnings', label: 'Median Earnings', value: '£38,400', parent: '£34,200', unit: 'GBP/year', direction: 'higher_is_better' },
      { id: 'investment_grade', label: 'Investment Grade', value: 'B+', parent: 'B', direction: 'higher_is_better' },
    ],
  },
  {
    id: 'housing_stock', title: 'Housing Stock', icon: Home, iconColor: '#059669',
    metrics: [
      { id: 'epc_energy_score', label: 'EPC Score', value: '62', parent: '58', unit: 'score', direction: 'higher_is_better' },
      { id: 'epc_rating_c_plus', label: 'EPC C+ Share', value: '48%', parent: '41%', direction: 'higher_is_better' },
      { id: 'building_profile', label: 'Carbon Emissions', value: '3.2', parent: '3.8', unit: 'tCO2/yr', direction: 'lower_is_better' },
    ],
  },
];

/* ══════════════════════════════════════════════════════════════════════
   LIFESTYLE & CONNECTIVITY TAB — 12 metrics in 3 sections
   ══════════════════════════════════════════════════════════════════════ */
const LIFESTYLE_SECTIONS: MockSection[] = [
  {
    id: 'transport_access', title: 'Transport & Access', icon: Train, iconColor: '#7C3AED',
    metrics: [
      { id: 'nearest_station', label: 'Nearest Station', value: '540m', parent: '1,180m', unit: 'metres', direction: 'lower_is_better' },
      { id: 'stations_in_area', label: 'Stations', value: '3', parent: '2', unit: 'count', direction: 'higher_is_better' },
      { id: 'ptal_score', label: 'PTAL', value: '4', parent: '3', unit: 'level', direction: 'higher_is_better', chartType: 'gauge', chartData: { value: 4, max: 6 } },
      { id: 'commuter_connectivity', label: 'Connectivity Score', value: '71', parent: '58', unit: 'score /100', direction: 'higher_is_better' },
      { id: 'connectivity_index', label: 'Connectivity Index', value: '68', parent: '54', unit: 'score /100', direction: 'higher_is_better' },
      { id: 'ev_chargers', label: 'EV Chargers', value: '12', parent: '8', unit: 'count', direction: 'higher_is_better' },
    ],
  },
  {
    id: 'digital_connectivity', title: 'Digital Connectivity', icon: Wifi, iconColor: '#2563EB',
    metrics: [
      { id: 'broadband', label: 'Gigabit Broadband', value: '72%', parent: '64%', unit: '% gigabit', direction: 'higher_is_better' },
      { id: 'mobile_coverage', label: 'Mobile Coverage', value: '98%', parent: '95%', unit: '% 4G outdoor', direction: 'higher_is_better' },
    ],
  },
  {
    id: 'amenities', title: 'Amenities & Active Travel', icon: ShoppingBag, iconColor: '#059669',
    metrics: [
      { id: 'fifteen_min_score', label: '15-Min Score', value: '74', parent: '62', unit: 'score /100', direction: 'higher_is_better', chartType: 'gauge', chartData: { value: 74, max: 100 } },
      { id: 'amenities_15min', label: 'Amenities Nearby', value: '47', parent: '38', unit: 'count', direction: 'higher_is_better' },
      { id: 'cycling', label: 'Cycle Commuters', value: '4.2%', parent: '3.1%', direction: 'higher_is_better' },
      { id: 'commute_distance', label: 'WFH Rate', value: '28.4%', parent: '24.1%', direction: 'higher_is_neutral' },
    ],
  },
];

/* ══════════════════════════════════════════════════════════════════════
   ENVIRONMENT & SAFETY TAB — 14 metrics in 3 sections
   ══════════════════════════════════════════════════════════════════════ */
const ENVIRONMENT_SECTIONS: MockSection[] = [
  {
    id: 'safety', title: 'Safety', icon: Shield, iconColor: '#DC2626',
    metrics: [
      { id: 'crime_rate', label: 'Crime Rate', value: '62.4', parent: '89.1', unit: 'per 1,000/yr', direction: 'lower_is_better', chartType: 'breakdown',
        chartData: [
          { type: 'Violence & Sexual', count: 312, pct: 28.1 },
          { type: 'Anti-social Behaviour', count: 224, pct: 20.2 },
          { type: 'Vehicle Crime', count: 187, pct: 16.8 },
          { type: 'Burglary', count: 134, pct: 12.1 },
          { type: 'Shoplifting', count: 98, pct: 8.8 },
          { type: 'Other', count: 155, pct: 14.0 },
        ],
      },
      { id: 'crime_trend', label: 'Crime Trend', value: '-7.9%', parent: '-3.2%', direction: 'lower_is_better', chartType: 'trend', chartData: { points: [74.2, 65.1, 68.9, 71.3, 67.8, 62.4], labels: ['2019','2020','2021','2022','2023','2024'] } },
      { id: 'flood_risk', label: 'Flood Risk', value: 'Low', parent: 'Medium', direction: 'lower_is_better' },
    ],
  },
  {
    id: 'environment', title: 'Environment', icon: Wind, iconColor: '#0891B2',
    metrics: [
      { id: 'air_quality_no2', label: 'NO₂', value: '24.1', parent: '28.4', unit: 'µg/m³', direction: 'lower_is_better', chartType: 'gauge', chartData: { value: 24.1, max: 60, limit: 40, limitLabel: 'UK limit' } },
      { id: 'air_quality_pm25', label: 'PM2.5', value: '10.2', parent: '11.8', unit: 'µg/m³', direction: 'lower_is_better', chartType: 'gauge', chartData: { value: 10.2, max: 30, limit: 15, limitLabel: 'WHO limit' } },
      { id: 'noise', label: 'Noise', value: '52.3 dB', parent: '56.8 dB', direction: 'lower_is_better', chartType: 'noise',
        chartData: [
          { source: 'Road Traffic (Day)', db: 52.3, category: 'Moderate' },
          { source: 'Road Traffic (Night)', db: 44.1, category: 'Quiet' },
          { source: 'Rail (Day)', db: 48.7, category: 'Moderate' },
          { source: 'Rail (Night)', db: 38.2, category: 'Quiet' },
        ],
      },
      { id: 'epc_rating', label: 'EPC Score', value: '62', parent: '58', unit: 'score', direction: 'higher_is_better' },
      { id: 'esg_score', label: 'ESG Score', value: '68', parent: '61', unit: 'score /100', direction: 'higher_is_better' },
      { id: 'land_designations', label: 'Land Designations', value: 'AONB Edge', parent: 'None', direction: 'higher_is_neutral' },
    ],
  },
  {
    id: 'green_space', title: 'Green Space', icon: Leaf, iconColor: '#15803D',
    metrics: [
      { id: 'green_cover', label: 'Park Cover', value: '18.4%', parent: '12.1%', direction: 'higher_is_better' },
      { id: 'green_spaces', label: 'Parks', value: '8', parent: '5', unit: 'count', direction: 'higher_is_better' },
      { id: 'nearest_park', label: 'Nearest Park', value: '280m', parent: '420m', unit: 'metres', direction: 'lower_is_better' },
      { id: 'parks_1km', label: 'Parks within 1km', value: '6', parent: '3', unit: 'count', direction: 'higher_is_better' },
      { id: 'sports_recreation', label: 'Sports Facilities', value: '4', parent: '3', unit: 'count', direction: 'higher_is_better' },
    ],
  },
];

/* ══════════════════════════════════════════════════════════════════════
   COMMUNITY & EDUCATION TAB — 22 metrics in 5 sections
   ══════════════════════════════════════════════════════════════════════ */
const COMMUNITY_SECTIONS: MockSection[] = [
  {
    id: 'people', title: 'People', icon: UserCircle, iconColor: '#7C3AED',
    metrics: [
      { id: 'demographics_overview', label: 'Demographics', value: 'Suburban family', parent: 'Urban mixed', direction: 'higher_is_neutral' },
      { id: 'population_density', label: 'Pop Density', value: '48.2', parent: '72.1', unit: 'people/hectare', direction: 'higher_is_neutral' },
      { id: 'median_age', label: 'Median Age', value: '38', parent: '35', unit: 'years', direction: 'higher_is_neutral' },
      { id: 'good_health', label: 'Good Health', value: '83.2%', parent: '81.4%', direction: 'higher_is_better' },
      { id: 'economically_active', label: 'Econ. Active', value: '72.8%', parent: '68.4%', direction: 'higher_is_better' },
      { id: 'degree_educated', label: 'Degree Educated', value: '42.1%', parent: '38.6%', direction: 'higher_is_better' },
      { id: 'no_car', label: 'No Car', value: '18.2%', parent: '26.4%', direction: 'higher_is_neutral' },
      { id: 'born_abroad', label: 'Born Abroad', value: '22.4%', parent: '32.1%', direction: 'higher_is_neutral' },
      { id: 'wfh', label: 'WFH Rate', value: '28.4%', parent: '24.1%', direction: 'higher_is_neutral' },
      { id: 'household_composition', label: 'Family Households', value: '64.2%', parent: '52.8%', unit: '% families', direction: 'higher_is_neutral' },
      { id: 'area_persona', label: 'Area Persona', value: 'Commuter Belt Family', parent: 'Mixed Urban', direction: 'higher_is_neutral' },
    ],
  },
  {
    id: 'diversity', title: 'Diversity', icon: Globe, iconColor: '#0891B2',
    metrics: [
      { id: 'ethnicity', label: 'Ethnicity', value: '62.4% White British', parent: '44.2%', direction: 'higher_is_neutral', chartType: 'stacked',
        chartData: [
          { label: 'White British', pct: 62.4, color: '#C2410C' },
          { label: 'Asian/Asian British', pct: 14.8, color: '#7C3AED' },
          { label: 'Black/Black British', pct: 11.2, color: '#059669' },
          { label: 'Mixed/Multiple', pct: 5.1, color: '#0891B2' },
          { label: 'White Other', pct: 4.3, color: '#D97706' },
          { label: 'Other', pct: 2.2, color: '#A8A29E' },
        ],
      },
      { id: 'religion', label: 'Religion', value: '48.1% Christian', parent: '40.2%', direction: 'higher_is_neutral', chartType: 'stacked',
        chartData: [
          { label: 'Christian', pct: 48.1, color: '#C2410C' },
          { label: 'No religion', pct: 28.4, color: '#7C3AED' },
          { label: 'Muslim', pct: 8.2, color: '#059669' },
          { label: 'Hindu', pct: 6.1, color: '#0891B2' },
          { label: 'Other', pct: 9.2, color: '#A8A29E' },
        ],
      },
      { id: 'housing_tenure', label: 'Owner Occupied', value: '68.2%', parent: '52.4%', direction: 'higher_is_neutral', chartType: 'stacked',
        chartData: [
          { label: 'Owner occupied', pct: 68.2, color: '#C2410C' },
          { label: 'Private rented', pct: 18.4, color: '#7C3AED' },
          { label: 'Social rented', pct: 10.1, color: '#0891B2' },
          { label: 'Other', pct: 3.3, color: '#A8A29E' },
        ],
      },
      { id: 'housing_type', label: 'Housing Stock', value: '34.1% Detached', parent: '18.2%', direction: 'higher_is_neutral', chartType: 'stacked',
        chartData: [
          { label: 'Detached', pct: 34.1, color: '#C2410C' },
          { label: 'Semi-detached', pct: 28.2, color: '#7C3AED' },
          { label: 'Terraced', pct: 22.4, color: '#059669' },
          { label: 'Flat', pct: 15.3, color: '#0891B2' },
        ],
      },
      { id: 'household_size', label: 'Single-person', value: '24.1%', parent: '32.8%', direction: 'higher_is_neutral' },
    ],
  },
  {
    id: 'schools', title: 'Schools', icon: GraduationCap, iconColor: '#EA580C',
    metrics: [
      { id: 'primary_schools', label: 'Primary Schools', value: '4', parent: '6', unit: 'count', direction: 'higher_is_better' },
      { id: 'secondary_schools', label: 'Secondary Schools', value: '2', parent: '3', unit: 'count', direction: 'higher_is_better' },
      { id: 'outstanding_schools_walk', label: 'Outstanding (walkable)', value: '2', parent: '1', unit: 'schools', direction: 'higher_is_better' },
      { id: 'nurseries', label: 'Nurseries', value: '5', parent: '4', unit: 'count', direction: 'higher_is_better' },
    ],
  },
  {
    id: 'deprivation', title: 'Deprivation', icon: Scale, iconColor: '#6366F1',
    metrics: [
      { id: 'deprivation', label: 'IMD Decile', value: '7', parent: '5', unit: 'score (10=least deprived)', direction: 'higher_is_better', chartType: 'gauge', chartData: { value: 7, max: 10 } },
    ],
  },
  {
    id: 'health_services', title: 'Health Services', icon: HeartPulse, iconColor: '#DC2626',
    metrics: [
      { id: 'nhs_facilities', label: 'NHS Facilities', value: '3', parent: '4', unit: 'count', direction: 'higher_is_better' },
    ],
  },
];

/* ══════════════════════════════════════════════════════════════════════
   GOVERNANCE TAB — 7 metrics in 1 section
   ══════════════════════════════════════════════════════════════════════ */
const GOVERNANCE_SECTIONS: MockSection[] = [
  {
    id: 'governance', title: 'Governance', icon: Landmark, iconColor: '#0891B2',
    metrics: [
      { id: 'council_tax', label: 'Council Tax (Band D)', value: '£1,891', parent: '£1,724', unit: 'GBP/year', direction: 'lower_is_better' },
      { id: 'local_authority', label: 'Local Authority', value: 'London Borough of Croydon', parent: '—', direction: 'higher_is_neutral' },
      { id: 'controlling_party', label: 'Ruling Party', value: 'Labour', parent: '—', direction: 'higher_is_neutral' },
      { id: 'water_company', label: 'Water Company', value: 'Thames Water', parent: '—', direction: 'higher_is_neutral' },
      { id: 'electricity_dno', label: 'Electricity DNO', value: 'UK Power Networks', parent: '—', direction: 'higher_is_neutral' },
      { id: 'gas_gdn', label: 'Gas GDN', value: 'Southern Gas Networks', parent: '—', direction: 'higher_is_neutral' },
      { id: 'financial_health', label: 'S114 Status', value: 'S114 Issued', parent: '—', direction: 'higher_is_neutral' },
    ],
  },
];

/* ══════════════════════════════════════════════════════════════════════
   TRANSACTIONS + SCHOOLS MOCK DATA
   ══════════════════════════════════════════════════════════════════════ */
const TRANSACTIONS = [
  { date: '2025-03-14', address: '42 Marlpit Lane', price: 485000, type: 'S', beds: 3, sqft: 1120, tenure: 'Freehold', epc: 'C', prevPrice: 385000, prevDate: '2018-06-22' },
  { date: '2025-02-28', address: '7 The Grove', price: 612000, type: 'D', beds: 4, sqft: 1540, tenure: 'Freehold', epc: 'B', prevPrice: null as number | null, prevDate: null as string | null },
  { date: '2025-02-15', address: 'Flat 3, Avalon Court', price: 265000, type: 'F', beds: 2, sqft: 680, tenure: 'Leasehold', epc: 'D', prevPrice: 228000, prevDate: '2019-11-08' },
  { date: '2025-01-30', address: '18 Woodcote Grove Rd', price: 725000, type: 'D', beds: 5, sqft: 1920, tenure: 'Freehold', epc: 'C', prevPrice: 615000, prevDate: '2016-03-11' },
  { date: '2025-01-22', address: '91 Brighton Road', price: 348000, type: 'T', beds: 2, sqft: 840, tenure: 'Freehold', epc: 'E', prevPrice: 295000, prevDate: '2017-09-04' },
  { date: '2024-12-18', address: 'Flat 12, Cane Hill Park', price: 310000, type: 'F', beds: 2, sqft: 720, tenure: 'Leasehold', epc: 'B', prevPrice: null, prevDate: null },
];

const SCHOOLS = [
  { name: 'Woodcote Primary', phase: 'Primary' as const, ofsted: 'Outstanding' as const, distance: '0.3 mi', ks2: 72 as number | undefined, fsm: 8.2, pupils: 420, lastInspection: 'Mar 2023', p8: undefined as number | undefined },
  { name: 'Coulsdon C of E Primary', phase: 'Primary' as const, ofsted: 'Good' as const, distance: '0.4 mi', ks2: 65, fsm: 14.1, pupils: 315, lastInspection: 'Nov 2022', p8: undefined as number | undefined },
  { name: 'Smitham Primary', phase: 'Primary' as const, ofsted: 'Good' as const, distance: '0.6 mi', ks2: 68, fsm: 11.3, pupils: 380, lastInspection: 'Jun 2024', p8: undefined as number | undefined },
  { name: 'Oasis Academy Coulsdon', phase: 'Secondary' as const, ofsted: 'Good' as const, distance: '0.5 mi', ks2: undefined as number | undefined, fsm: 22.4, pupils: 1120, lastInspection: 'Feb 2024', p8: 0.21 },
  { name: 'Woodcote High School', phase: 'Secondary' as const, ofsted: 'Requires Improvement' as const, distance: '0.8 mi', ks2: undefined as number | undefined, fsm: 18.7, pupils: 980, lastInspection: 'Sep 2023', p8: -0.15 },
];

/* ══════════════════════════════════════════════════════════════════════
   HOMEPAGE — ROTATING DAILY CITY MAPS
   ══════════════════════════════════════════════════════════════════════ */
const DAILY_MAPS = [
  { name: 'Central London', bbox: '-0.16,51.49,-0.06,51.53' },
  { name: 'Manchester', bbox: '-2.28,53.46,-2.20,53.50' },
  { name: 'Birmingham', bbox: '-1.93,52.47,-1.85,52.50' },
  { name: 'Leeds', bbox: '-1.58,53.78,-1.50,53.82' },
  { name: 'Bristol', bbox: '-2.62,51.44,-2.55,51.47' },
  { name: 'Liverpool', bbox: '-3.01,53.39,-2.93,53.42' },
  { name: 'Sheffield', bbox: '-1.50,53.37,-1.44,53.40' },
  { name: 'Newcastle', bbox: '-1.64,54.96,-1.58,54.99' },
  { name: 'Nottingham', bbox: '-1.17,52.94,-1.11,52.97' },
  { name: 'Brighton', bbox: '-0.16,50.82,-0.10,50.85' },
  { name: 'Cardiff', bbox: '-3.21,51.47,-3.14,51.50' },
  { name: 'Edinburgh', bbox: '-3.22,55.94,-3.15,55.97' },
  { name: 'Bath', bbox: '-2.39,51.37,-2.33,51.40' },
  { name: 'Oxford', bbox: '-1.28,51.74,-1.22,51.77' },
  { name: 'Cambridge', bbox: '0.10,52.19,0.16,52.22' },
  { name: 'York', bbox: '-1.11,53.95,-1.05,53.97' },
  { name: 'Norwich', bbox: '1.27,52.62,1.33,52.65' },
  { name: 'Exeter', bbox: '-3.55,50.71,-3.50,50.74' },
  { name: 'Chester', bbox: '-2.91,53.18,-2.86,53.21' },
  { name: 'Canterbury', bbox: '1.06,51.27,1.10,51.29' },
  { name: 'Winchester', bbox: '-1.33,51.05,-1.28,51.07' },
  { name: 'Reading', bbox: '-1.00,51.44,-0.95,51.47' },
  { name: 'Southampton', bbox: '-1.43,50.90,-1.38,50.92' },
  { name: 'Plymouth', bbox: '-4.17,50.36,-4.12,50.38' },
  { name: 'Coventry', bbox: '-1.54,52.39,-1.49,52.42' },
  { name: 'Leicester', bbox: '-1.15,52.62,-1.10,52.65' },
  { name: 'Swansea', bbox: '-3.96,51.61,-3.91,51.63' },
  { name: 'Aberdeen', bbox: '-2.12,57.13,-2.07,57.16' },
  { name: 'Glasgow', bbox: '-4.28,55.85,-4.22,55.87' },
  { name: 'Belfast', bbox: '-5.95,54.59,-5.89,54.61' },
];

function getTodaysMap() {
  const dayOfYear = Math.floor((Date.now() - new Date(new Date().getFullYear(), 0, 0).getTime()) / 86400000);
  return DAILY_MAPS[dayOfYear % DAILY_MAPS.length];
}

/* ══════════════════════════════════════════════════════════════════════
   UTILITY HELPERS
   ══════════════════════════════════════════════════════════════════════ */
const fmtPrice = (n: number) => '£' + n.toLocaleString('en-GB');
const fmtDate = (d: string) => new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
const typeLabel = (t: string) => ({ D: 'Detached', S: 'Semi', T: 'Terraced', F: 'Flat' }[t] || t);
const epcColour = (r: string) => ({ A: '#008054', B: '#19b459', C: '#8dce46', D: '#ffd500', E: '#fcaa65', F: '#ef8023', G: '#e9153b' }[r] || T.inkFaint);

function ComparisonArrow({ value, parentValue, direction }: { value: string; parentValue: string; direction: string }) {
  const numVal = parseFloat(value.replace(/[^0-9.\-]/g, ''));
  const numParent = parseFloat(parentValue.replace(/[^0-9.\-]/g, ''));
  if (isNaN(numVal) || isNaN(numParent)) return <span style={{ color: T.inkFaint, fontFamily: T.sans, fontSize: 11 }}>—</span>;
  const diff = numVal - numParent;
  const isHigher = diff > 0;
  const isGood = direction === 'higher_is_better' ? isHigher : direction === 'lower_is_better' ? !isHigher : null;
  const color = isGood === true ? T.good : isGood === false ? T.caution : T.inkFaint;
  const Icon = diff > 0 ? ArrowUpRight : diff < 0 ? ArrowDownRight : Minus;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, color, fontSize: 11, fontWeight: 600, fontFamily: T.sans }}>
      <Icon size={12} /> vs {AREA.parent}
    </span>
  );
}

function SimilarityBar({ pct }: { pct: number }) {
  const color = pct >= 75 ? T.good : pct >= 50 ? '#84cc16' : T.caution;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
      <div style={{ flex: 1, height: 6, borderRadius: 3, background: T.divider, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', borderRadius: 3, background: color, transition: 'width 0.6s ease-out' }} />
      </div>
      <span style={{ fontFamily: T.mono, fontSize: 12, fontWeight: 700, color }}>{pct}%</span>
    </div>
  );
}

function Card({ children, style, hover = true }: { children: React.ReactNode; style?: React.CSSProperties; hover?: boolean }) {
  return (
    <div style={{
      background: T.cardBg, borderRadius: 16, border: `1px solid ${T.divider}`, overflow: 'hidden',
      transition: 'box-shadow 0.2s, transform 0.2s', ...style,
    }}
      onMouseEnter={hover ? e => { e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,0.06)'; } : undefined}
      onMouseLeave={hover ? e => { e.currentTarget.style.boxShadow = 'none'; } : undefined}
    >
      {children}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   CHART RENDERERS — UNIVERSAL, DATA-DRIVEN
   ══════════════════════════════════════════════════════════════════════ */

function TrendChart({ data }: { data: { points: number[]; labels: string[] } }) {
  const max = Math.max(...data.points);
  const min = Math.min(...data.points);
  const range = max - min || 1;
  const W = 600, H = 140, padL = 50, padR = 10, padT = 10, padB = 28;
  const chartW = W - padL - padR, chartH = H - padT - padB;
  const pts = data.points.map((v, i) => ({
    x: padL + (i / (data.points.length - 1)) * chartW,
    y: padT + chartH - ((v - min) / range) * chartH,
  }));
  const linePath = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ');
  const areaPath = linePath + ` L${pts[pts.length - 1].x},${padT + chartH} L${pts[0].x},${padT + chartH} Z`;
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ overflow: 'visible', marginTop: 12 }}>
      {[0, 0.5, 1].map(frac => {
        const y = padT + chartH * (1 - frac);
        const val = min + range * frac;
        return (
          <g key={frac}>
            <line x1={padL} x2={W - padR} y1={y} y2={y} stroke={T.divider} strokeDasharray="3,3" />
            <text x={padL - 6} y={y + 3} textAnchor="end" style={{ fontFamily: T.mono, fontSize: 9, fill: T.inkFaint }}>{val >= 1000 ? `£${Math.round(val/1000)}k` : val.toFixed(0)}</text>
          </g>
        );
      })}
      <path d={areaPath} fill={`${T.accent}12`} />
      <path d={linePath} fill="none" stroke={T.accent} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      {pts.map((p, i) => <circle key={i} cx={p.x} cy={p.y} r={3} fill={T.cardBg} stroke={T.accent} strokeWidth={1.5} />)}
      {data.labels.map((l, i) => {
        const x = padL + (i / (data.labels.length - 1)) * chartW;
        return i % 2 === 0 ? <text key={i} x={x} y={H - 4} textAnchor="middle" style={{ fontFamily: T.mono, fontSize: 8, fill: T.inkFaint }}>{l}</text> : null;
      })}
    </svg>
  );
}

function BarsChart({ data }: { data: { label: string; pct: number }[] }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12 }}>
      {data.map(d => (
        <div key={d.label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 100, fontFamily: T.sans, fontSize: 11, color: T.inkMuted, textAlign: 'right', flexShrink: 0 }}>{d.label}</div>
          <div style={{ flex: 1, height: 16, borderRadius: 8, background: T.dividerSoft, overflow: 'hidden' }}>
            <div style={{ width: `${d.pct}%`, height: '100%', borderRadius: 8, background: T.accent, transition: 'width 0.5s ease-out' }} />
          </div>
          <div style={{ width: 36, fontFamily: T.mono, fontSize: 11, fontWeight: 600, color: T.ink, textAlign: 'right' }}>{d.pct}%</div>
        </div>
      ))}
    </div>
  );
}

function GaugeChart({ data }: { data: { value: number; max: number; limit?: number; limitLabel?: string } }) {
  const pctFill = Math.min((data.value / data.max) * 100, 100);
  const pctLimit = data.limit ? (data.limit / data.max) * 100 : undefined;
  const isGood = !data.limit || data.value <= data.limit;
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ position: 'relative', height: 20, borderRadius: 10, background: T.dividerSoft, overflow: 'visible' }}>
        <div style={{
          width: `${pctFill}%`, height: '100%', borderRadius: 10,
          background: isGood ? 'linear-gradient(90deg, #059669, #34d399)' : 'linear-gradient(90deg, #d97706, #dc2626)',
          transition: 'width 0.8s ease-out',
        }} />
        {pctLimit !== undefined && (
          <div style={{ position: 'absolute', top: -3, left: `${pctLimit}%`, transform: 'translateX(-50%)', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <div style={{ width: 2, height: 26, background: T.ink, opacity: 0.3, borderRadius: 1 }} />
            <div style={{ fontFamily: T.mono, fontSize: 8, color: T.inkMuted, marginTop: 1, whiteSpace: 'nowrap' }}>{data.limitLabel}</div>
          </div>
        )}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
        <span style={{ fontFamily: T.mono, fontSize: 10, color: T.inkFaint }}>0</span>
        <span style={{ fontFamily: T.mono, fontSize: 10, color: T.inkFaint }}>{data.max}</span>
      </div>
    </div>
  );
}

function NoiseChart({ data }: { data: { source: string; db: number; category: string }[] }) {
  const dbColor = (db: number) => db <= 40 ? T.good : db <= 55 ? T.caution : db <= 65 ? '#f59e0b' : T.bad;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 12 }}>
      {data.map(n => (
        <div key={n.source}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
            <span style={{ fontFamily: T.sans, fontSize: 11, color: T.inkMuted }}>{n.source}</span>
            <span style={{ fontFamily: T.mono, fontSize: 11, fontWeight: 600, color: T.ink }}>{n.db} dB</span>
          </div>
          <div style={{ height: 8, borderRadius: 4, background: T.dividerSoft, overflow: 'hidden' }}>
            <div style={{ width: `${(n.db / 80) * 100}%`, height: '100%', borderRadius: 4, background: dbColor(n.db), transition: 'width 0.6s ease-out' }} />
          </div>
          <div style={{ fontFamily: T.sans, fontSize: 9, color: T.inkFaint, marginTop: 1 }}>{n.category}</div>
        </div>
      ))}
    </div>
  );
}

function BreakdownChart({ data }: { data: { type: string; count: number; pct: number }[] }) {
  const maxPct = Math.max(...data.map(c => c.pct));
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12 }}>
      {data.map(c => (
        <div key={c.type} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 120, fontFamily: T.sans, fontSize: 11, color: T.inkMuted, textAlign: 'right', flexShrink: 0 }}>{c.type}</div>
          <div style={{ flex: 1, height: 18, borderRadius: 5, background: T.dividerSoft, overflow: 'hidden' }}>
            <div style={{ width: `${(c.pct / maxPct) * 100}%`, height: '100%', borderRadius: 5, background: `linear-gradient(90deg, ${T.bad}90, ${T.bad}60)`, transition: 'width 0.6s ease-out' }} />
          </div>
          <div style={{ width: 36, fontFamily: T.mono, fontSize: 11, fontWeight: 600, color: T.ink, textAlign: 'right' }}>{c.pct}%</div>
          <div style={{ width: 36, fontFamily: T.mono, fontSize: 9, color: T.inkFaint, textAlign: 'right' }}>{c.count}</div>
        </div>
      ))}
    </div>
  );
}

function StackedChart({ data }: { data: { label: string; pct: number; color: string }[] }) {
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ display: 'flex', height: 22, borderRadius: 11, overflow: 'hidden', marginBottom: 10 }}>
        {data.map(d => (
          <div key={d.label} style={{ width: `${d.pct}%`, height: '100%', background: d.color, transition: 'width 0.5s ease-out' }} title={`${d.label}: ${d.pct}%`} />
        ))}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
        {data.map(d => (
          <div key={d.label} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div style={{ width: 8, height: 8, borderRadius: 3, background: d.color }} />
            <span style={{ fontFamily: T.sans, fontSize: 10, color: T.inkMuted }}>{d.label}</span>
            <span style={{ fontFamily: T.mono, fontSize: 10, fontWeight: 600, color: T.ink }}>{d.pct}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function renderChart(m: MockMetric) {
  if (!m.chartType || m.chartType === 'none' || !m.chartData) return null;
  switch (m.chartType) {
    case 'trend': return <TrendChart data={m.chartData} />;
    case 'bars': return <BarsChart data={m.chartData} />;
    case 'gauge': return <GaugeChart data={m.chartData} />;
    case 'noise': return <NoiseChart data={m.chartData} />;
    case 'breakdown': return <BreakdownChart data={m.chartData} />;
    case 'stacked': return <StackedChart data={m.chartData} />;
    default: return null;
  }
}

/* ══════════════════════════════════════════════════════════════════════
   GENERIC METRIC ROW — used for all metrics in all tabs
   ══════════════════════════════════════════════════════════════════════ */

function MetricRow({ m }: { m: MockMetric }) {
  const [expanded, setExpanded] = useState(false);
  const hasChart = m.chartType && m.chartType !== 'none' && m.chartData;
  return (
    <div style={{ borderBottom: `1px solid ${T.dividerSoft}` }}>
      <div
        onClick={hasChart ? () => setExpanded(!expanded) : undefined}
        style={{
          display: 'flex', alignItems: 'center', padding: '14px 0', cursor: hasChart ? 'pointer' : 'default',
          transition: 'background 0.15s',
        }}
        onMouseEnter={hasChart ? e => { e.currentTarget.style.background = T.dividerSoft; } : undefined}
        onMouseLeave={hasChart ? e => { e.currentTarget.style.background = 'transparent'; } : undefined}
      >
        <div style={{ flex: 1, fontFamily: T.sans, fontSize: 13, fontWeight: 500, color: T.ink }}>{m.label}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontFamily: T.mono, fontSize: 15, fontWeight: 700, color: T.ink }}>{m.value}</div>
            {m.unit && <div style={{ fontFamily: T.sans, fontSize: 9, color: T.inkFaint }}>{m.unit}</div>}
          </div>
          <div style={{ width: 80, textAlign: 'right' }}>
            <div style={{ fontFamily: T.mono, fontSize: 11, color: T.inkFaint }}>{m.parent}</div>
            <ComparisonArrow value={m.value} parentValue={m.parent} direction={m.direction} />
          </div>
          {hasChart && (
            <div style={{ width: 20, display: 'flex', justifyContent: 'center' }}>
              {expanded ? <ChevronUp size={14} color={T.inkFaint} /> : <ChevronDown size={14} color={T.inkFaint} />}
            </div>
          )}
        </div>
      </div>
      {expanded && hasChart && (
        <div style={{ padding: '0 0 16px', animation: 'fadeInUp 0.2s ease-out' }}>
          {renderChart(m)}
        </div>
      )}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   SECTION ACCORDION — collapsible section with summary pills
   ══════════════════════════════════════════════════════════════════════ */

function SectionAccordion({ section, defaultOpen = false }: { section: MockSection; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const Icon = section.icon;
  return (
    <Card hover={false} style={{ marginBottom: 14 }}>
      <div
        onClick={() => setOpen(!open)}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '16px 20px', cursor: 'pointer', transition: 'background 0.15s',
        }}
        onMouseEnter={e => { e.currentTarget.style.background = T.dividerSoft; }}
        onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: `${section.iconColor}15`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Icon size={16} color={section.iconColor} />
          </div>
          <div>
            <div style={{ fontFamily: T.serif, fontWeight: 700, fontSize: 16, color: T.ink }}>{section.title}</div>
            <div style={{ fontFamily: T.sans, fontSize: 11, color: T.inkFaint }}>{section.metrics.length} metrics</div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {!open && section.metrics.slice(0, 3).map(m => (
            <span key={m.id} style={{
              fontFamily: T.mono, fontSize: 10, fontWeight: 600,
              background: T.dividerSoft, color: T.ink, padding: '3px 8px', borderRadius: 6,
            }}>
              {m.label}: {m.value}
            </span>
          ))}
          {open ? <ChevronUp size={16} color={T.inkFaint} /> : <ChevronDown size={16} color={T.inkFaint} />}
        </div>
      </div>
      {open && (
        <div style={{ padding: '0 20px 16px' }}>
          {section.metrics.map(m => <MetricRow key={m.id} m={m} />)}
        </div>
      )}
    </Card>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   TRANSACTION TABLE — Expandable rows with detail panel
   ══════════════════════════════════════════════════════════════════════ */

function TransactionTable() {
  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const thStyle: React.CSSProperties = {
    fontFamily: T.sans, fontSize: 10, fontWeight: 700, color: T.inkFaint,
    textTransform: 'uppercase', letterSpacing: '0.06em', padding: '10px 12px',
    textAlign: 'left', borderBottom: `2px solid ${T.divider}`,
    position: 'sticky' as const, top: 0, background: T.cardBg, zIndex: 1,
  };
  const tdStyle: React.CSSProperties = {
    fontFamily: T.sans, fontSize: 13, padding: '10px 12px',
    borderBottom: `1px solid ${T.dividerSoft}`, verticalAlign: 'middle',
  };
  return (
    <Card hover={false} style={{ marginBottom: 14 }}>
      <div style={{ padding: '20px 24px 12px' }}>
        <div style={{ fontFamily: T.serif, fontSize: 16, fontWeight: 700, color: T.ink, marginBottom: 4 }}>Recent Transactions</div>
        <div style={{ fontFamily: T.sans, fontSize: 12, color: T.inkMuted }}>Showing 6 of 142 sales in the last 13 months</div>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 680 }}>
          <thead>
            <tr>
              <th style={thStyle}>Date</th>
              <th style={thStyle}>Address</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>Price</th>
              <th style={thStyle}>Type</th>
              <th style={thStyle}>Beds</th>
              <th style={thStyle}>Tenure</th>
              <th style={thStyle}>EPC</th>
              <th style={{ ...thStyle, width: 28 }} />
            </tr>
          </thead>
          <tbody>
            {TRANSACTIONS.map((tx, i) => (
              <tr key={i} style={{ cursor: 'pointer', background: expandedRow === i ? T.accentLight : 'transparent' }}
                onClick={() => setExpandedRow(expandedRow === i ? null : i)}>
                <td style={{ ...tdStyle, fontFamily: T.mono, fontSize: 11, color: T.inkMuted, whiteSpace: 'nowrap' }}>{fmtDate(tx.date)}</td>
                <td style={{ ...tdStyle, fontWeight: 500, color: T.ink }}>{tx.address}</td>
                <td style={{ ...tdStyle, fontFamily: T.mono, fontWeight: 700, color: T.ink, textAlign: 'right' }}>{fmtPrice(tx.price)}</td>
                <td style={tdStyle}><span style={{ fontFamily: T.sans, fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 6, background: T.dividerSoft, color: T.inkMuted }}>{typeLabel(tx.type)}</span></td>
                <td style={{ ...tdStyle, fontFamily: T.mono, fontSize: 12 }}>{tx.beds}</td>
                <td style={{ ...tdStyle, fontSize: 12, color: T.inkMuted }}>{tx.tenure}</td>
                <td style={tdStyle}><span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 22, height: 22, borderRadius: 5, background: epcColour(tx.epc), color: 'white', fontFamily: T.mono, fontSize: 10, fontWeight: 700 }}>{tx.epc}</span></td>
                <td style={tdStyle}>{expandedRow === i ? <ChevronUp size={14} color={T.inkFaint} /> : <ChevronDown size={14} color={T.inkFaint} />}</td>
              </tr>
            ))}
            {expandedRow !== null && (
              <tr>
                <td colSpan={8} style={{ padding: 0 }}>
                  <div style={{ margin: '0 12px 12px', padding: '14px 18px', borderRadius: 12, background: T.accentLight, borderLeft: `3px solid ${T.accent}` }}>
                    <div style={{ fontFamily: T.sans, fontSize: 10, fontWeight: 700, color: T.accent, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>Transaction Detail</div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                      <div>
                        <div style={{ fontFamily: T.sans, fontSize: 10, color: T.inkFaint }}>Price/sqft</div>
                        <div style={{ fontFamily: T.mono, fontSize: 14, fontWeight: 700, color: T.ink }}>£{Math.round(TRANSACTIONS[expandedRow].price / TRANSACTIONS[expandedRow].sqft)}</div>
                      </div>
                      {TRANSACTIONS[expandedRow].prevPrice ? (
                        <>
                          <div>
                            <div style={{ fontFamily: T.sans, fontSize: 10, color: T.inkFaint }}>Previous Sale</div>
                            <div style={{ fontFamily: T.mono, fontSize: 14, fontWeight: 700, color: T.ink }}>{fmtPrice(TRANSACTIONS[expandedRow].prevPrice!)}</div>
                            <div style={{ fontFamily: T.sans, fontSize: 10, color: T.inkFaint }}>{TRANSACTIONS[expandedRow].prevDate && fmtDate(TRANSACTIONS[expandedRow].prevDate!)}</div>
                          </div>
                          <div>
                            <div style={{ fontFamily: T.sans, fontSize: 10, color: T.inkFaint }}>Price Change</div>
                            <div style={{ fontFamily: T.mono, fontSize: 14, fontWeight: 700, color: TRANSACTIONS[expandedRow].price > TRANSACTIONS[expandedRow].prevPrice! ? T.good : T.bad }}>
                              {((TRANSACTIONS[expandedRow].price - TRANSACTIONS[expandedRow].prevPrice!) / TRANSACTIONS[expandedRow].prevPrice! * 100).toFixed(1)}%
                            </div>
                          </div>
                        </>
                      ) : (
                        <div style={{ gridColumn: 'span 2', fontFamily: T.sans, fontSize: 12, color: T.inkFaint, fontStyle: 'italic' }}>No previous sale on record</div>
                      )}
                    </div>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   SCHOOL TABLE — Expandable rows with detail tabs
   ══════════════════════════════════════════════════════════════════════ */

function SchoolTable() {
  const [phaseFilter, setPhaseFilter] = useState('All');
  const [expandedSchool, setExpandedSchool] = useState<number | null>(null);
  const [detailTab, setDetailTab] = useState('overview');
  const filtered = phaseFilter === 'All' ? SCHOOLS : SCHOOLS.filter(s => s.phase === phaseFilter);

  const ofstedStyle = (rating: string) => {
    const m: Record<string, { bg: string; text: string }> = {
      'Outstanding': { bg: '#DCFCE7', text: '#15803D' },
      'Good': { bg: '#DBEAFE', text: '#1D4ED8' },
      'Requires Improvement': { bg: '#FEF3C7', text: '#92400E' },
      'Inadequate': { bg: '#FEE2E2', text: '#991B1B' },
    };
    return m[rating] || { bg: T.dividerSoft, text: T.inkFaint };
  };

  return (
    <Card hover={false} style={{ marginBottom: 14 }}>
      <div style={{ padding: '20px 24px 0' }}>
        <div style={{ fontFamily: T.serif, fontSize: 16, fontWeight: 700, color: T.ink, marginBottom: 4 }}>Nearby Schools</div>
        <div style={{ fontFamily: T.sans, fontSize: 12, color: T.inkMuted, marginBottom: 14 }}>5 schools within 1 mile · sorted by distance</div>
        <div style={{ display: 'flex', gap: 6, marginBottom: 16 }}>
          {['All', 'Primary', 'Secondary'].map(p => (
            <button key={p} onClick={() => { setPhaseFilter(p); setExpandedSchool(null); }} style={{
              fontFamily: T.sans, fontSize: 12, fontWeight: 600,
              padding: '6px 14px', borderRadius: 8, cursor: 'pointer',
              border: `1px solid ${phaseFilter === p ? T.accent : T.divider}`,
              background: phaseFilter === p ? T.accentLight : T.cardBg,
              color: phaseFilter === p ? T.accent : T.inkMuted, transition: 'all 0.15s',
            }}>{p}</button>
          ))}
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {filtered.map((s, i) => {
          const oc = ofstedStyle(s.ofsted);
          const isExpanded = expandedSchool === i;
          return (
            <div key={s.name}>
              <div onClick={() => { setExpandedSchool(isExpanded ? null : i); setDetailTab('overview'); }}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 24px', cursor: 'pointer',
                  borderTop: `1px solid ${T.dividerSoft}`, background: isExpanded ? T.accentLight : 'transparent', transition: 'background 0.15s',
                }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontFamily: T.sans, fontSize: 13, fontWeight: 600, color: T.ink }}>{s.name}</div>
                  <div style={{ fontFamily: T.sans, fontSize: 11, color: T.inkFaint, marginTop: 2 }}>{s.phase} · {s.distance} · {s.pupils} pupils</div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  {s.ks2 !== undefined && <span style={{ fontFamily: T.mono, fontSize: 12, fontWeight: 600, color: T.ink }}>KS2: {s.ks2}%</span>}
                  {s.p8 !== undefined && <span style={{ fontFamily: T.mono, fontSize: 12, fontWeight: 600, color: s.p8 >= 0 ? T.good : T.bad }}>P8: {s.p8 > 0 ? '+' : ''}{s.p8}</span>}
                  <span style={{ fontFamily: T.sans, fontSize: 10, fontWeight: 700, padding: '3px 10px', borderRadius: 6, background: oc.bg, color: oc.text }}>{s.ofsted}</span>
                  {isExpanded ? <ChevronUp size={14} color={T.inkFaint} /> : <ChevronDown size={14} color={T.inkFaint} />}
                </div>
              </div>
              {isExpanded && (
                <div style={{ padding: '0 24px 16px', background: T.accentLight }}>
                  <div style={{ display: 'flex', gap: 2, marginBottom: 14, paddingTop: 12 }}>
                    {['overview', 'results', 'ofsted', 'demographics'].map(tab => (
                      <button key={tab} onClick={e => { e.stopPropagation(); setDetailTab(tab); }} style={{
                        fontFamily: T.sans, fontSize: 11, fontWeight: detailTab === tab ? 700 : 500,
                        padding: '5px 12px', borderRadius: 6, cursor: 'pointer',
                        background: detailTab === tab ? T.accent : 'transparent',
                        color: detailTab === tab ? 'white' : T.inkMuted,
                        border: 'none', transition: 'all 0.15s', textTransform: 'capitalize',
                      }}>{tab}</button>
                    ))}
                  </div>
                  {detailTab === 'overview' && (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
                      {[{ label: 'Pupils', value: s.pupils.toString() }, { label: 'FSM %', value: `${s.fsm}%` }, { label: 'Last Inspected', value: s.lastInspection }, { label: 'Distance', value: s.distance }, { label: 'Phase', value: s.phase }, { label: 'Ofsted', value: s.ofsted }].map(item => (
                        <div key={item.label} style={{ background: T.cardBg, borderRadius: 10, padding: '10px 14px', border: `1px solid ${T.divider}` }}>
                          <div style={{ fontFamily: T.sans, fontSize: 10, color: T.inkFaint, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{item.label}</div>
                          <div style={{ fontFamily: T.mono, fontSize: 14, fontWeight: 700, color: T.ink, marginTop: 4 }}>{item.value}</div>
                        </div>
                      ))}
                    </div>
                  )}
                  {detailTab === 'results' && (
                    <div style={{ background: T.cardBg, borderRadius: 10, padding: 16, border: `1px solid ${T.divider}` }}>
                      {s.ks2 !== undefined && (
                        <div style={{ marginBottom: 12 }}>
                          <div style={{ fontFamily: T.sans, fontSize: 11, fontWeight: 600, color: T.inkMuted, marginBottom: 6 }}>KS2 — Expected Standard (RWM)</div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                            <div style={{ flex: 1, height: 16, borderRadius: 8, background: T.dividerSoft, overflow: 'hidden' }}>
                              <div style={{ width: `${s.ks2}%`, height: '100%', borderRadius: 8, background: s.ks2 >= 65 ? T.good : T.caution }} />
                            </div>
                            <span style={{ fontFamily: T.mono, fontSize: 14, fontWeight: 700, color: T.ink }}>{s.ks2}%</span>
                          </div>
                        </div>
                      )}
                      {s.p8 !== undefined && (
                        <div>
                          <div style={{ fontFamily: T.sans, fontSize: 11, fontWeight: 600, color: T.inkMuted, marginBottom: 6 }}>Progress 8</div>
                          <div style={{ fontFamily: T.mono, fontSize: 24, fontWeight: 800, color: s.p8 >= 0 ? T.good : T.bad }}>{s.p8 > 0 ? '+' : ''}{s.p8}</div>
                        </div>
                      )}
                    </div>
                  )}
                  {detailTab === 'ofsted' && (
                    <div style={{ background: T.cardBg, borderRadius: 10, padding: 16, border: `1px solid ${T.divider}` }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                        <span style={{ fontFamily: T.sans, fontSize: 13, fontWeight: 700, padding: '4px 14px', borderRadius: 8, background: oc.bg, color: oc.text }}>{s.ofsted}</span>
                        <span style={{ fontFamily: T.sans, fontSize: 12, color: T.inkFaint }}>Last inspected {s.lastInspection}</span>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                        {['Quality of Education', 'Behaviour & Attitudes', 'Personal Development', 'Leadership'].map(area => (
                          <div key={area} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: `1px solid ${T.dividerSoft}` }}>
                            <span style={{ fontFamily: T.sans, fontSize: 11, color: T.inkMuted }}>{area}</span>
                            <span style={{ fontFamily: T.sans, fontSize: 11, fontWeight: 600, color: T.ink }}>{s.ofsted}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {detailTab === 'demographics' && (
                    <div style={{ background: T.cardBg, borderRadius: 10, padding: 16, border: `1px solid ${T.divider}` }}>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                        {[{ label: 'FSM Eligible', value: `${s.fsm}%` }, { label: 'Pupil Count', value: s.pupils.toString() }].map(item => (
                          <div key={item.label}>
                            <div style={{ fontFamily: T.sans, fontSize: 10, color: T.inkFaint, textTransform: 'uppercase' }}>{item.label}</div>
                            <div style={{ fontFamily: T.mono, fontSize: 18, fontWeight: 700, color: T.ink, marginTop: 4 }}>{item.value}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   MAP PANEL — OSM embed with legend
   ══════════════════════════════════════════════════════════════════════ */

function MapPanel() {
  return (
    <div style={{ borderRadius: 16, overflow: 'hidden', border: `1px solid ${T.divider}`, height: 400, position: 'relative', background: T.warmBg, marginBottom: 14 }}>
      <iframe title="Area map" src="https://www.openstreetmap.org/export/embed.html?bbox=-0.15,51.30,-0.10,51.34&layer=mapnik&marker=51.32,-0.125" style={{ width: '100%', height: '100%', border: 'none' }} />
      <div style={{ position: 'absolute', top: 12, right: 12, background: 'rgba(255,255,255,0.92)', backdropFilter: 'blur(8px)', borderRadius: 12, padding: '10px 14px', boxShadow: '0 2px 12px rgba(0,0,0,0.1)', border: `1px solid ${T.divider}` }}>
        <div style={{ fontFamily: T.sans, fontSize: 10, fontWeight: 700, color: T.inkFaint, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Legend</div>
        {[{ color: '#C2410C', label: 'Sold prices' }, { color: '#059669', label: 'Outstanding schools' }, { color: '#2563eb', label: 'Good schools' }, { color: '#7C3AED', label: 'Stations' }].map(l => (
          <div key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <div style={{ width: 8, height: 8, borderRadius: 4, background: l.color }} />
            <span style={{ fontFamily: T.sans, fontSize: 10, color: T.inkMuted }}>{l.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   PAGE VIEWS — NAVBAR, HERO, PERSONA, OVERVIEW, DATA TABS, HOMEPAGE
   ══════════════════════════════════════════════════════════════════════ */

function NavBar({ onHome }: { onHome: () => void }) {
  return (
    <nav style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '16px 32px', borderBottom: `1px solid ${T.divider}`,
      background: T.cardBg, position: 'sticky', top: 0, zIndex: 50,
    }}>
      <div onClick={onHome} style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
        <div style={{ width: 32, height: 32, borderRadius: 8, background: T.accent, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Leaf size={16} color="white" />
        </div>
        <span style={{ fontFamily: T.serif, fontWeight: 700, fontSize: 20, color: T.ink, letterSpacing: '-0.02em' }}>PropertyPulse</span>
      </div>
      <span style={{ fontFamily: T.sans, fontSize: 11, fontWeight: 600, background: T.accentLight, color: T.accent, padding: '4px 12px', borderRadius: 20, border: `1px solid ${T.accentBg}` }}>PROTOTYPE 2</span>
    </nav>
  );
}

function HeroSection() {
  return (
    <div style={{ background: T.heroGrad, padding: '40px 32px' }}>
      <div style={{ maxWidth: 820, margin: '0 auto' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <h1 style={{ fontFamily: T.serif, fontWeight: 800, fontSize: 36, color: 'white', letterSpacing: '-0.03em', lineHeight: 1.1, margin: 0 }}>
              {AREA.name}
              <span style={{ fontWeight: 400, fontSize: 20, color: 'rgba(255,255,255,0.45)', marginLeft: 8 }}>{AREA.parent}</span>
            </h1>
            <p style={{ fontFamily: T.sans, fontSize: 13, color: 'rgba(255,255,255,0.4)', marginTop: 8 }}>{AREA.type} · {AREA.lsoaCount} LSOAs · {AREA.county}</p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {[{ icon: Bookmark, label: 'Save' }, { icon: FileDown, label: 'Report' }].map(b => (
              <button key={b.label} style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 10, fontSize: 13, fontWeight: 600,
                fontFamily: T.sans, background: 'rgba(255,255,255,0.08)', color: 'white',
                border: '1px solid rgba(255,255,255,0.12)', cursor: 'pointer',
              }}><b.icon size={14} /> {b.label}</button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function PersonaFitBanner() {
  const score = 74;
  const verdictColor = score >= 70 ? T.good : score >= 45 ? T.caution : T.bad;
  const verdict = score >= 70 ? 'Strong' : score >= 45 ? 'Mixed' : 'Weak';
  return (
    <div style={{ maxWidth: 820, margin: '0 auto', padding: '0 32px', transform: 'translateY(-28px)', marginBottom: -12 }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: T.cardBg, borderRadius: 16, padding: '16px 24px',
        border: `1px solid ${T.divider}`, boxShadow: '0 4px 16px rgba(0,0,0,0.06)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <svg width={52} height={52} viewBox="0 0 52 52">
            <circle cx={26} cy={26} r={22} fill="none" stroke={T.divider} strokeWidth={5} />
            <circle cx={26} cy={26} r={22} fill="none" stroke={verdictColor} strokeWidth={5}
              strokeDasharray={`${(score / 100) * 138.2} 138.2`} strokeLinecap="round" transform="rotate(-90 26 26)" />
            <text x={26} y={26} textAnchor="middle" dominantBaseline="central" style={{ fontFamily: T.mono, fontSize: 14, fontWeight: 700, fill: T.ink }}>{score}</text>
          </svg>
          <div>
            <div style={{ fontFamily: T.serif, fontWeight: 700, fontSize: 16, color: T.ink }}>Persona Fit: <span style={{ color: verdictColor }}>{verdict}</span></div>
            <div style={{ fontFamily: T.sans, fontSize: 12, color: T.inkMuted, marginTop: 2 }}>Based on 82 metrics · First-Time Buyer</div>
          </div>
        </div>
        <button style={{ fontFamily: T.sans, fontSize: 12, fontWeight: 600, color: T.accent, background: T.accentLight, border: `1px solid ${T.accentBg}`, padding: '6px 14px', borderRadius: 8, cursor: 'pointer' }}>Change persona</button>
      </div>
    </div>
  );
}

function SnapshotGrid() {
  return (
    <section style={{ maxWidth: 820, margin: '0 auto', padding: '0 32px 32px' }}>
      <h2 style={{ fontFamily: T.serif, fontWeight: 700, fontSize: 22, color: T.ink, letterSpacing: '-0.02em', marginBottom: 16 }}>Area Snapshot</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(145px, 1fr))', gap: 12 }}>
        {HEADLINE_METRICS.map((m, i) => (
          <div key={m.id} style={{
            background: T.cardBg, borderRadius: 14, padding: '16px 18px',
            border: `1px solid ${T.divider}`, transition: 'box-shadow 0.2s, transform 0.2s',
            animation: `fadeInUp 0.4s ease-out ${i * 60}ms both`,
          }}
            onMouseEnter={e => { e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.08)'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
            onMouseLeave={e => { e.currentTarget.style.boxShadow = 'none'; e.currentTarget.style.transform = 'translateY(0)'; }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <div style={{ width: 28, height: 28, borderRadius: 7, background: T.accentLight, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <m.icon size={14} color={T.accent} />
              </div>
              <span style={{ fontFamily: T.sans, fontSize: 11, fontWeight: 600, color: T.inkMuted }}>{m.label}</span>
            </div>
            <div style={{ fontFamily: T.mono, fontSize: 20, fontWeight: 700, color: T.ink, lineHeight: 1.1 }}>{m.value}</div>
            {m.unit && <div style={{ fontFamily: T.sans, fontSize: 10, color: T.inkFaint, marginTop: 2 }}>{m.unit}</div>}
            <div style={{ marginTop: 8 }}><ComparisonArrow value={m.value} parentValue={m.parent} direction={m.direction} /></div>
          </div>
        ))}
      </div>
    </section>
  );
}

function TabScoreCards({ onTabClick }: { onTabClick: (tab: string) => void }) {
  return (
    <section style={{ maxWidth: 820, margin: '0 auto', padding: '0 32px 32px' }}>
      <h2 style={{ fontFamily: T.serif, fontWeight: 700, fontSize: 22, color: T.ink, letterSpacing: '-0.02em', marginBottom: 16 }}>Tab Scores</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(145px, 1fr))', gap: 12 }}>
        {TAB_SCORES.map((t, i) => {
          const vColor = t.score >= 70 ? T.good : t.score >= 45 ? T.caution : T.bad;
          const verdict = t.score >= 70 ? 'Strong' : t.score >= 45 ? 'Mixed' : 'Weak';
          return (
            <div key={t.tab} onClick={() => onTabClick(t.tab)} style={{
              background: T.cardBg, borderRadius: 14, padding: '18px 20px', border: `1px solid ${T.divider}`, cursor: 'pointer', transition: 'all 0.2s',
              animation: `fadeInUp 0.4s ease-out ${i * 60}ms both`,
            }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = t.colour; e.currentTarget.style.transform = 'translateY(-2px)'; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = T.divider; e.currentTarget.style.transform = 'translateY(0)'; }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <t.icon size={16} color={t.colour} />
                <span style={{ fontFamily: T.sans, fontSize: 12, fontWeight: 600, color: T.ink }}>{t.tab.split(' & ')[0]}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                <span style={{ fontFamily: T.mono, fontSize: 28, fontWeight: 800, color: T.ink }}>{t.score}</span>
                <span style={{ fontFamily: T.sans, fontSize: 11, fontWeight: 600, color: vColor, background: vColor + '15', padding: '2px 8px', borderRadius: 6 }}>{verdict}</span>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ComparableAreasSection() {
  return (
    <section style={{ maxWidth: 820, margin: '0 auto', padding: '0 32px 32px' }}>
      <h2 style={{ fontFamily: T.serif, fontWeight: 700, fontSize: 22, color: T.ink, letterSpacing: '-0.02em', marginBottom: 6 }}>Comparable Areas</h2>
      <p style={{ fontFamily: T.sans, fontSize: 12, color: T.inkMuted, marginBottom: 16, lineHeight: 1.5 }}>
        Matched across 11 dimensions: price, rent, earnings, air quality, growth, crime, deprivation, demographics, transport, and council tax.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {COMPARABLE_AREAS.map(a => (
          <Card key={a.name}>
            <div style={{ padding: '18px 22px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <div>
                  <span style={{ fontFamily: T.sans, fontSize: 14, fontWeight: 700, color: T.ink }}>{a.name}</span>
                  <span style={{ fontFamily: T.sans, fontSize: 12, color: T.inkFaint, marginLeft: 6 }}>{a.parent}</span>
                </div>
                <button style={{ fontFamily: T.sans, fontSize: 11, fontWeight: 600, color: T.accent, background: T.accentLight, border: `1px solid ${T.accentBg}`, padding: '4px 12px', borderRadius: 8, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
                  View area <ArrowRight size={11} />
                </button>
              </div>
              <SimilarityBar pct={a.match} />
            </div>
          </Card>
        ))}
      </div>
    </section>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   TAB CONTENT VIEWS
   ══════════════════════════════════════════════════════════════════════ */

const TAB_NAMES = ['Overview', 'Property & Market', 'Lifestyle & Connectivity', 'Environment & Safety', 'Community & Education', 'Local Governance'] as const;

type TabName = (typeof TAB_NAMES)[number];

const TAB_CONFIG: Record<string, { sections: MockSection[]; icon: React.ElementType; colour: string }> = {
  'Property & Market': { sections: PROPERTY_SECTIONS, icon: Home, colour: '#C2410C' },
  'Lifestyle & Connectivity': { sections: LIFESTYLE_SECTIONS, icon: Coffee, colour: '#7C3AED' },
  'Environment & Safety': { sections: ENVIRONMENT_SECTIONS, icon: TreePine, colour: '#059669' },
  'Community & Education': { sections: COMMUNITY_SECTIONS, icon: Users, colour: '#EA580C' },
  'Local Governance': { sections: GOVERNANCE_SECTIONS, icon: Landmark, colour: '#0891B2' },
};

function TabContentView({ tab }: { tab: string }) {
  const config = TAB_CONFIG[tab];
  if (!config) return null;
  const totalMetrics = config.sections.reduce((acc, s) => acc + s.metrics.length, 0);
  return (
    <div>
      <div style={{ fontFamily: T.sans, fontSize: 12, color: T.inkMuted, marginBottom: 16 }}>{totalMetrics} metrics across {config.sections.length} sections</div>
      {config.sections.map((s, i) => <SectionAccordion key={s.id} section={s} defaultOpen={i === 0} />)}
      {tab === 'Property & Market' && <TransactionTable />}
      {tab === 'Community & Education' && <SchoolTable />}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   RESULTS VIEW — Tab bar + tab content
   ══════════════════════════════════════════════════════════════════════ */

function ResultsView({ onHome }: { onHome: () => void }) {
  const [activeTab, setActiveTab] = useState<TabName>('Overview');

  const totalMetrics = useMemo(() => {
    return Object.values(TAB_CONFIG).reduce((acc, cfg) => acc + cfg.sections.reduce((a, s) => a + s.metrics.length, 0), 0) + HEADLINE_METRICS.length;
  }, []);

  return (
    <div style={{ background: T.pageBg, minHeight: '100vh' }}>
      <NavBar onHome={onHome} />
      <HeroSection />
      <PersonaFitBanner />

      {/* Tab bar */}
      <div style={{ maxWidth: 820, margin: '0 auto', padding: '0 32px 24px' }}>
        <div style={{ display: 'flex', gap: 4, overflowX: 'auto', paddingBottom: 4 }} className="scrollbar-none">
          {TAB_NAMES.map(tab => {
            const isActive = activeTab === tab;
            const tabCfg = TAB_CONFIG[tab];
            const colour = tabCfg?.colour || '#6366f1';
            const TabIcon = tabCfg?.icon || LayoutDashboard;
            return (
              <button key={tab} onClick={() => setActiveTab(tab)} style={{
                fontFamily: T.sans, fontSize: 12, fontWeight: isActive ? 700 : 500,
                padding: '10px 16px', borderRadius: 10, cursor: 'pointer', whiteSpace: 'nowrap',
                background: isActive ? `${colour}15` : 'transparent',
                color: isActive ? colour : T.inkMuted,
                border: isActive ? `1.5px solid ${colour}40` : '1.5px solid transparent',
                transition: 'all 0.15s', display: 'flex', alignItems: 'center', gap: 6,
              }}>
                <TabIcon size={14} />
                {tab}
              </button>
            );
          })}
        </div>
        <div style={{ fontFamily: T.mono, fontSize: 11, color: T.inkFaint, marginTop: 4, textAlign: 'right' }}>
          {totalMetrics} total metrics
        </div>
      </div>

      {/* Map */}
      <div style={{ maxWidth: 820, margin: '0 auto', padding: '0 32px' }}>
        <MapPanel />
      </div>

      {/* Tab content */}
      <div style={{ maxWidth: 820, margin: '0 auto', padding: '0 32px 64px' }}>
        {activeTab === 'Overview' ? (
          <>
            <SnapshotGrid />
            <TabScoreCards onTabClick={(t) => setActiveTab(t as TabName)} />
            <ComparableAreasSection />
          </>
        ) : (
          <TabContentView tab={activeTab} />
        )}
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   HOMEPAGE — Hero + Search + rotating city map background
   ══════════════════════════════════════════════════════════════════════ */

function HomePage({ onSearch }: { onSearch: () => void }) {
  const todaysMap = getTodaysMap();

  return (
    <div style={{ background: T.pageBg, minHeight: '100vh' }}>
      <NavBar onHome={() => {}} />

      {/* Map hero */}
      <div style={{ position: 'relative', overflow: 'hidden', minHeight: 520 }}>
        {/* OSM iframe as decorative background */}
        <iframe
          title="Background map"
          src={`https://www.openstreetmap.org/export/embed.html?bbox=${todaysMap.bbox}&layer=mapnik`}
          style={{
            position: 'absolute', inset: 0, width: '100%', height: '100%', border: 'none',
            filter: 'grayscale(0.3) brightness(0.9)', pointerEvents: 'none',
          }}
        />
        {/* Warm gradient overlay */}
        <div style={{
          position: 'absolute', inset: 0,
          background: 'linear-gradient(180deg, rgba(250,248,245,0.88) 0%, rgba(250,248,245,0.75) 40%, rgba(250,248,245,0.92) 100%)',
        }} />

        {/* City watermark */}
        <div style={{
          position: 'absolute', bottom: 16, right: 24, fontFamily: T.mono, fontSize: 11,
          color: 'rgba(0,0,0,0.15)', fontWeight: 600, letterSpacing: '0.05em',
        }}>
          {todaysMap.name}
        </div>

        {/* Content */}
        <div style={{ position: 'relative', zIndex: 1, maxWidth: 720, margin: '0 auto', padding: '80px 32px 60px', textAlign: 'center' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, marginBottom: 24 }}>
            <MapPin size={14} color={T.accent} />
            <span style={{ fontFamily: T.sans, fontSize: 12, fontWeight: 600, color: T.accent }}>UK Property Intelligence</span>
          </div>

          <h1 style={{ fontFamily: T.serif, fontWeight: 800, fontSize: 42, color: T.ink, letterSpacing: '-0.03em', lineHeight: 1.1, margin: '0 0 16px' }}>
            Every detail about<br />
            <span style={{ color: T.accent }}>your next neighbourhood</span>
          </h1>

          <p style={{ fontFamily: T.sans, fontSize: 16, color: T.inkMuted, maxWidth: 480, margin: '0 auto 32px', lineHeight: 1.6 }}>
            82 data points. Crime, schools, transport, green space, prices — all in one place.
          </p>

          {/* Glass search bar */}
          <div style={{
            maxWidth: 520, margin: '0 auto', position: 'relative',
          }}>
            <div style={{
              display: 'flex', alignItems: 'center',
              background: 'rgba(255,255,255,0.85)', backdropFilter: 'blur(12px)',
              borderRadius: 16, border: `1.5px solid ${T.divider}`,
              boxShadow: '0 8px 32px rgba(0,0,0,0.08)', overflow: 'hidden',
            }}>
              <Search size={18} style={{ marginLeft: 18, color: T.inkFaint, flexShrink: 0 }} />
              <input
                type="text" placeholder="Search postcode or place..."
                style={{
                  flex: 1, height: 56, border: 'none', background: 'transparent',
                  fontFamily: T.sans, fontSize: 16, color: T.ink, outline: 'none',
                  padding: '0 16px', caretColor: T.accent,
                }}
              />
              <button onClick={onSearch} style={{
                margin: 6, height: 44, padding: '0 24px', borderRadius: 12,
                background: T.accent, color: 'white', border: 'none', cursor: 'pointer',
                fontFamily: T.sans, fontSize: 14, fontWeight: 700,
                display: 'flex', alignItems: 'center', gap: 8, whiteSpace: 'nowrap',
              }}>
                Analyse <ArrowRight size={16} />
              </button>
            </div>
          </div>

          {/* Coverage pills */}
          <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 16 }}>
            <span style={{ fontFamily: T.sans, fontSize: 11, fontWeight: 600, background: T.sageLight, color: T.sage, padding: '4px 12px', borderRadius: 20, border: `1px solid ${T.sage}30` }}>
              Live: England, Wales
            </span>
            <span style={{ fontFamily: T.sans, fontSize: 11, fontWeight: 600, background: T.cautionBg, color: T.caution, padding: '4px 12px', borderRadius: 20, border: `1px solid ${T.caution}30` }}>
              Planned: Scotland, NI
            </span>
          </div>
        </div>
      </div>

      {/* Feature tiles */}
      <section style={{ maxWidth: 820, margin: '0 auto', padding: '48px 32px 64px' }}>
        <h2 style={{ fontFamily: T.serif, fontWeight: 700, fontSize: 26, color: T.ink, letterSpacing: '-0.02em', marginBottom: 8, textAlign: 'center' }}>What you get</h2>
        <p style={{ fontFamily: T.sans, fontSize: 14, color: T.inkMuted, textAlign: 'center', marginBottom: 32 }}>Everything you need to make a confident move</p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 14 }}>
          {[
            { icon: PoundSterling, label: 'Property & Market', desc: '17 metrics on prices, trends, rents' },
            { icon: Train, label: 'Lifestyle', desc: '12 metrics on transport, broadband, amenities' },
            { icon: Shield, label: 'Safety', desc: '14 metrics on crime, air, noise, green space' },
            { icon: Users, label: 'Community', desc: '22 metrics on demographics, schools, health' },
            { icon: Landmark, label: 'Governance', desc: '7 metrics on council tax, utilities, politics' },
          ].map(tile => (
            <Card key={tile.label}>
              <div style={{ padding: '20px 18px' }}>
                <div style={{ width: 36, height: 36, borderRadius: 10, background: T.accentLight, display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 12 }}>
                  <tile.icon size={18} color={T.accent} />
                </div>
                <div style={{ fontFamily: T.serif, fontWeight: 700, fontSize: 15, color: T.ink, marginBottom: 4 }}>{tile.label}</div>
                <div style={{ fontFamily: T.sans, fontSize: 12, color: T.inkMuted, lineHeight: 1.5 }}>{tile.desc}</div>
              </div>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   ANIMATIONS (injected via style tag)
   ══════════════════════════════════════════════════════════════════════ */
function InjectStyles() {
  return (
    <style>{`
      @import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@400;500;600;700;800&display=swap');
      @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(12px); }
        to { opacity: 1; transform: translateY(0); }
      }
    `}</style>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   ROOT COMPONENT — toggles between Homepage and Results
   ══════════════════════════════════════════════════════════════════════ */
export default function Prototype2() {
  const [view, setView] = useState<'home' | 'results'>('home');
  return (
    <>
      <InjectStyles />
      {view === 'home' ? (
        <HomePage onSearch={() => setView('results')} />
      ) : (
        <ResultsView onHome={() => setView('home')} />
      )}
    </>
  );
}
