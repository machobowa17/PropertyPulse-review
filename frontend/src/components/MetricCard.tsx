import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronRight, TrendingUp, TrendingDown, Minus,
  PoundSterling, BarChart3, Activity, Scale, Building2, Home,
  Percent, Building, MapPin, Train, Zap, Wifi, Droplets, Wind,
  Cloud, Volume2, TreePine, Flame, Users, Clock, Heart, Key,
  LayoutGrid, GraduationCap, School, BarChart2, Stethoscope,
  Receipt, Landmark, Ruler, Wallet, Award, Sprout, Timer,
  TrainFront, Bike, Smartphone, Sparkles, Vote, Droplet,
  ShieldCheck, ShieldAlert, Coffee, Banknote, Briefcase, Car, Globe,
} from 'lucide-react';
import type { Metric, PersonaId } from '../types';
import { formatValue, METRIC_ICONS } from '../utils/tabs';
import { getTakeaway } from '../utils/personas';
import AmenityRadarChart from './AmenityRadarChart';
import PriceByTypeChart from './PriceByTypeChart';
import EpcRatingChart from './EpcRatingChart';
import TransportModeChart from './TransportModeChart';
import PtalGauge from './PtalGauge';
import FloodRiskGauge from './FloodRiskGauge';
import DemographicsCards from './DemographicsCards';
import ImdDeprivationBlock from './ImdDeprivationBlock';
import CouncilTaxBandGrid from './CouncilTaxBandGrid';
import RentByBedroomChart from './RentByBedroomChart';
import BroadbandPanel from './BroadbandPanel';

const ICON_MAP: Record<string, React.ElementType> = {
  PoundSterling, BarChart3, Activity, Scale, Building2, Home,
  Percent, Building, MapPin, Train, Zap, Wifi, Droplets, Wind,
  Cloud, Volume2, TreePine, Flame, Users, Clock, Heart, Key,
  LayoutGrid, GraduationCap, School, BarChart2, Stethoscope,
  Receipt, Landmark, TrendingUp, TrendingDown, Ruler, Wallet,
  Award, Sprout, Timer, TrainFront, Bike, Smartphone, Sparkles,
  Vote, Droplet, ShieldCheck, ShieldAlert, Coffee, Banknote, Briefcase, Car, Globe,
};

/** Per-metric data source badge: label + licence */
const METRIC_SOURCES: Record<string, { label: string; licence: string }> = {
  // Property & Market
  avg_price:              { label: 'HM Land Registry PPD', licence: 'OGL v3' },
  median_price:           { label: 'HM Land Registry PPD', licence: 'OGL v3' },
  transaction_volume:     { label: 'HM Land Registry PPD', licence: 'OGL v3' },
  freehold_leasehold:     { label: 'HM Land Registry PPD', licence: 'OGL v3' },
  new_build_proportion:   { label: 'HM Land Registry PPD', licence: 'OGL v3' },
  price_trend_yoy:        { label: 'HM Land Registry PPD', licence: 'OGL v3' },
  price_per_sqft:         { label: 'HM Land Registry PPD', licence: 'OGL v3' },
  median_rent:            { label: 'VOA Private Rental Market', licence: 'OGL v3' },
  gross_yield:            { label: 'VOA / HM Land Registry', licence: 'OGL v3' },
  affordability:          { label: 'ONS ASHE + HM Land Registry', licence: 'OGL v3' },
  median_earnings:        { label: 'ONS ASHE', licence: 'OGL v3' },
  investment_grade:       { label: 'HM Land Registry / ONS', licence: 'OGL v3' },
  epc_rating:             { label: 'MHCLG EPC Register', licence: 'OGL v3' },
  epc_energy_score:       { label: 'MHCLG EPC Register', licence: 'OGL v3' },
  epc_rating_c_plus:      { label: 'MHCLG EPC Register', licence: 'OGL v3' },
  // Lifestyle & Connectivity
  nearest_station:        { label: 'NaPTAN / Network Rail', licence: 'OGL v3' },
  ptal:                   { label: 'TfL / NaPTAN', licence: 'OGL v3' },
  ptal_score:             { label: 'TfL / NaPTAN', licence: 'OGL v3' },
  cycling:                { label: 'Sustrans / OSM', licence: 'OGL v3 / ODbL' },
  broadband:              { label: 'Ofcom Connected Nations', licence: 'OGL v3' },
  mobile_coverage:        { label: 'Ofcom Connected Nations', licence: 'OGL v3' },
  ev_chargers:            { label: 'DfT EVCD Register', licence: 'OGL v3' },
  amenities_15min:        { label: 'OpenStreetMap', licence: 'ODbL' },
  fifteen_min_score:      { label: 'OpenStreetMap', licence: 'ODbL' },
  wfh:                    { label: 'Census 2021 (ONS)', licence: 'OGL v3' },
  commute_distance:       { label: 'Census 2021 (ONS)', licence: 'OGL v3' },
  // Environment & Safety
  flood_risk:             { label: 'EA Flood Map for Planning', licence: 'OGL v3' },
  air_quality_no2:        { label: 'DEFRA AURN', licence: 'OGL v3' },
  air_quality_pm25:       { label: 'DEFRA AURN', licence: 'OGL v3' },
  noise:                  { label: 'DEFRA Strategic Noise Mapping', licence: 'OGL v3' },
  nearest_park:           { label: 'OS Open Greenspace', licence: 'OGL v3' },
  green_cover:            { label: 'OS Open Greenspace', licence: 'OGL v3' },
  parks_1km:              { label: 'OS Open Greenspace', licence: 'OGL v3' },
  crime_rate:             { label: 'Home Office Crime Statistics', licence: 'OGL v3' },
  crime_trend:            { label: 'Home Office Crime Statistics', licence: 'OGL v3' },
  esg_score:              { label: 'Multi-source composite', licence: 'OGL v3' },
  // Community & Education
  demographics_overview:  { label: 'Census 2021 (ONS)', licence: 'OGL v3' },
  population_density:     { label: 'Census 2021 (ONS)', licence: 'OGL v3' },
  median_age:             { label: 'Census 2021 (ONS)', licence: 'OGL v3' },
  household_composition:  { label: 'Census 2021 (ONS)', licence: 'OGL v3' },
  housing_tenure:         { label: 'Census 2021 (ONS)', licence: 'OGL v3' },
  housing_type:           { label: 'Census 2021 (ONS)', licence: 'OGL v3' },
  good_health:            { label: 'Census 2021 (ONS)', licence: 'OGL v3' },
  economically_active:    { label: 'Census 2021 (ONS)', licence: 'OGL v3' },
  degree_educated:        { label: 'Census 2021 (ONS)', licence: 'OGL v3' },
  no_car:                 { label: 'Census 2021 (ONS)', licence: 'OGL v3' },
  born_abroad:            { label: 'Census 2021 (ONS)', licence: 'OGL v3' },
  primary_schools:        { label: 'Ofsted / Get Information About Schools', licence: 'OGL v3' },
  secondary_schools:      { label: 'Ofsted / Get Information About Schools', licence: 'OGL v3' },
  deprivation:            { label: 'MHCLG English Indices of Deprivation 2025', licence: 'OGL v3' },
  area_persona:           { label: 'Census 2021 / MHCLG IMD', licence: 'OGL v3' },
  nhs_facilities:         { label: 'NHS ODS / CQC', licence: 'OGL v3' },
  // Local Governance
  council_tax:            { label: 'MHCLG Council Tax Levels', licence: 'OGL v3' },
  local_authority:        { label: 'ONS Geographies', licence: 'OGL v3' },
  controlling_party:      { label: 'Electoral Commission', licence: 'OGL v3' },
  water_company:          { label: 'Ofwat / Environment Agency', licence: 'OGL v3' },
  financial_health:       { label: 'MHCLG S114 Notices', licence: 'OGL v3' },
};

export const COLOUR_STYLES = {
  green: { bg: 'bg-signal-green-bg', text: 'text-signal-green', border: 'border-signal-green/20', accent: 'border-l-emerald-500' },
  amber: { bg: 'bg-signal-amber-bg', text: 'text-signal-amber', border: 'border-signal-amber/20', accent: 'border-l-amber-500' },
  red: { bg: 'bg-signal-red-bg', text: 'text-signal-red', border: 'border-signal-red/20', accent: 'border-l-red-500' },
  neutral: { bg: 'bg-surface', text: 'text-ink-muted', border: 'border-divider', accent: 'border-l-zinc-300' },
};

interface Props {
  metric: Metric;
  persona: PersonaId;
  parentName: string;
}

export default function MetricCard({ metric, persona, parentName }: Props) {
  const [expanded, setExpanded] = useState(false);
  const takeaway = getTakeaway(metric, persona);
  const colours = COLOUR_STYLES[takeaway.colour];
  const iconName = METRIC_ICONS[metric.id] || 'BarChart3';
  const Icon = ICON_MAP[iconName] || BarChart3;
  const hasDetails = metric.details && Object.keys(metric.details).length > 0;

  const ComparisonIcon = metric.comparison_flag === 'higher_than_parent'
    ? TrendingUp
    : metric.comparison_flag === 'lower_than_parent'
    ? TrendingDown
    : Minus;

  return (
    <div
      className={`
        rounded-2xl bg-white border-l-[3px] transition-all duration-200
        ${colours.accent}
        ${expanded ? 'shadow-md ring-1 ring-brand-200/50' : 'shadow-sm hover:shadow-md hover:-translate-y-px'}
      `}
    >
      {/* ═══ DESKTOP: Table Row (Bible 6.2.1: Metric | Local | Parent | So What | Watch Out) ═══ */}
      <button
        onClick={() => hasDetails && setExpanded(!expanded)}
        aria-expanded={hasDetails ? expanded : undefined}
        aria-label={hasDetails ? `${metric.name} — ${expanded ? 'collapse' : 'expand'} details` : metric.name}
        className={`w-full text-left group hidden lg:grid lg:grid-cols-[2fr_1fr_1fr_1fr_1fr_28px] lg:items-center lg:gap-4 lg:px-5 lg:py-3.5 ${hasDetails ? 'cursor-pointer' : 'cursor-default'}`}
      >
        {/* Metric */}
        <div className="flex items-center gap-3 min-w-0">
          <div className={`shrink-0 w-9 h-9 rounded-lg flex items-center justify-center ${colours.bg}`}>
            <Icon className={`w-[18px] h-[18px] ${colours.text}`} />
          </div>
          <span className="text-sm font-semibold text-ink truncate">{metric.name}</span>
        </div>

        {/* Local */}
        <div className="text-lg font-bold font-mono text-ink tracking-tight">
          {formatValue(metric.local_value, metric.unit)}
        </div>

        {/* Parent */}
        <div className="flex items-center gap-1.5 text-sm text-ink-faint">
          {metric.parent_value !== null ? (
            <>
              <ComparisonIcon className="w-3.5 h-3.5 shrink-0" />
              {formatValue(metric.parent_value, metric.unit)}
            </>
          ) : (
            <span className="text-ink-faint/50">&mdash;</span>
          )}
        </div>

        {/* So What */}
        <div>
          {takeaway.soWhat ? (
            <span className={`inline-block px-2.5 py-1 rounded-lg text-xs font-medium ${colours.bg} ${colours.text} border ${colours.border}`}>
              {takeaway.soWhat}
            </span>
          ) : (
            <span className="text-ink-faint/50">&mdash;</span>
          )}
        </div>

        {/* Watch Out */}
        <div>
          {takeaway.watchOut && takeaway.watchOut !== 'None' ? (
            <span className="inline-block px-2.5 py-1 rounded-lg text-xs font-medium bg-surface text-ink-muted border border-divider">
              {takeaway.watchOut}
            </span>
          ) : (
            <span className="text-xs text-ink-faint/50">&mdash;</span>
          )}
        </div>

        {/* Chevron */}
        {hasDetails ? (
          <ChevronRight
            className={`w-4 h-4 text-ink-faint shrink-0 transition-transform duration-200
                        ${expanded ? 'rotate-90' : 'group-hover:translate-x-0.5'}`}
          />
        ) : <div className="w-4" />}
      </button>

      {/* ═══ MOBILE: Card Layout ═══ */}
      <button
        onClick={() => hasDetails && setExpanded(!expanded)}
        aria-expanded={hasDetails ? expanded : undefined}
        aria-label={hasDetails ? `${metric.name} — ${expanded ? 'collapse' : 'expand'} details` : metric.name}
        className={`w-full flex items-center gap-3 p-4 text-left group lg:hidden ${hasDetails ? 'cursor-pointer' : 'cursor-default'}`}
      >
        <div className={`shrink-0 w-10 h-10 rounded-xl flex items-center justify-center ${colours.bg}`}>
          <Icon className={`w-5 h-5 ${colours.text}`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-ink truncate">{metric.name}</div>
          <div className="flex items-baseline gap-2 mt-0.5">
            <span className="text-xl font-bold font-mono text-ink tracking-tight">
              {formatValue(metric.local_value, metric.unit)}
            </span>
            {metric.parent_value !== null && (
              <span className="flex items-center gap-1 text-xs text-ink-faint">
                <ComparisonIcon className="w-3 h-3" />
                {formatValue(metric.parent_value, metric.unit)}
                <span className="hidden sm:inline opacity-60">({parentName})</span>
              </span>
            )}
          </div>
        </div>
        {hasDetails && (
          <ChevronRight
            className={`w-4 h-4 text-ink-faint shrink-0 transition-transform duration-200
                        ${expanded ? 'rotate-90' : 'group-hover:translate-x-0.5'}`}
          />
        )}
      </button>

      {/* Mobile takeaway pills */}
      {takeaway.soWhat && (
        <div className="lg:hidden flex flex-wrap gap-2 px-4 pb-3 -mt-1">
          <div className={`px-3 py-1 rounded-lg text-xs font-medium ${colours.bg} ${colours.text} border ${colours.border}`}>
            {takeaway.soWhat}
          </div>
          {takeaway.watchOut && takeaway.watchOut !== 'None' && (
            <div className="px-3 py-1 rounded-lg text-xs font-medium bg-surface text-ink-muted border border-divider">
              {takeaway.watchOut}
            </div>
          )}
        </div>
      )}

      {/* ═══ Expanded details (shared) ═══ */}
      <AnimatePresence>
        {expanded && metric.details && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-4 lg:px-5 pb-4 pt-3 border-t border-divider/50 bg-surface-warm/30">
              <DetailsRenderer details={metric.details} unit={metric.unit} />
              {METRIC_SOURCES[metric.id] && (
                <div className="mt-3 flex items-center gap-1.5">
                  <span className="text-[10px] text-ink-faint">Source:</span>
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface border border-divider text-[10px] text-ink-faint font-medium">
                    {METRIC_SOURCES[metric.id].label}
                    <span className="text-ink-faint/50">·</span>
                    <span className="text-brand-600">{METRIC_SOURCES[metric.id].licence}</span>
                  </span>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/** Render details object as sub-rows or list */
function DetailsRenderer({ details, unit }: { details: Record<string, unknown>; unit: string }) {
  if (Array.isArray(details.schools)) {
    return (
      <div className="space-y-2 mt-2">
        {(details.schools as Record<string, unknown>[]).map((s, i) => (
          <div key={i} className="flex items-center gap-3 p-2.5 rounded-xl bg-surface">
            <div className="w-7 h-7 rounded-lg bg-brand-50 flex items-center justify-center text-xs font-bold text-brand-600">
              {i + 1}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-ink truncate">{String(s.name)}</div>
              <div className="flex flex-wrap gap-2 mt-0.5">
                {s.ofsted ? <span className="text-xs px-1.5 py-0.5 rounded bg-brand-50 text-brand-700">{String(s.ofsted)}</span> : null}
                {s.distance_m != null && <span className="text-xs text-ink-faint">{Number(s.distance_m).toLocaleString()}m</span>}
                {s.ks2_reading != null && <span className="text-xs text-ink-muted">Reading: {Number(s.ks2_reading).toFixed(1)}</span>}
                {s.ks2_maths != null && <span className="text-xs text-ink-muted">Maths: {Number(s.ks2_maths).toFixed(1)}</span>}
                {s.progress_8 != null && <span className="text-xs text-ink-muted">P8: {Number(s.progress_8).toFixed(2)}</span>}
                {s.attainment_8 != null && <span className="text-xs text-ink-muted">A8: {Number(s.attainment_8).toFixed(1)}</span>}
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (Array.isArray(details.stations)) {
    const modeCounts = details.mode_counts_1km as Record<string, number> | null | undefined;
    return (
      <div className="space-y-2 mt-2">
        {modeCounts && Object.keys(modeCounts).length > 0 && (
          <TransportModeChart modeCounts={modeCounts} />
        )}
        {(details.stations as Record<string, unknown>[]).map((s, i) => (
          <div key={i} className="flex items-center gap-3 p-2.5 rounded-xl bg-surface">
            <Train className="w-4 h-4 text-ink-faint shrink-0" />
            <span className="text-sm text-ink flex-1 truncate">{String(s.name)}</span>
            <span className="text-xs text-ink-muted shrink-0">{Number(s.distance_m).toLocaleString()}m</span>
          </div>
        ))}
        {details.bus_stops_500m != null && (
          <div className="text-xs text-ink-muted mt-1">Bus stops within 500m: {String(details.bus_stops_500m)}</div>
        )}
      </div>
    );
  }

  // Parks list: details has { parks: [...] }
  if (Array.isArray(details.parks)) {
    return (
      <div className="space-y-2 mt-2">
        {(details.parks as Record<string, unknown>[]).map((p, i) => (
          <div key={i} className="flex items-center gap-3 p-2.5 rounded-xl bg-surface">
            <TreePine className="w-4 h-4 text-signal-green shrink-0" />
            <div className="flex-1 min-w-0">
              <span className="text-sm text-ink truncate block">{String(p.name)}</span>
              {p.type != null && <span className="text-xs text-ink-faint">{String(p.type)}</span>}
            </div>
            {p.area_ha != null && <span className="text-xs text-ink-muted shrink-0">{Number(p.area_ha).toFixed(1)} ha</span>}
            <span className="text-xs text-ink-muted shrink-0">{Number(p.distance_m).toLocaleString()}m</span>
          </div>
        ))}
      </div>
    );
  }

  // NHS facilities: type_summary + list
  if (Array.isArray(details.facilities)) {
    const typeSummary = details.type_summary as Record<string, { count: number; nearest_m: number | null }> | null | undefined;
    const TYPE_ORDER = ['GP', 'Hospital', 'Pharmacy', 'Dentist', 'Optician', 'Care Home'];
    const summaryEntries = typeSummary
      ? [...TYPE_ORDER.filter((t) => t in typeSummary), ...Object.keys(typeSummary).filter((t) => !TYPE_ORDER.includes(t))]
          .map((t) => ({ type: t, ...typeSummary[t] }))
      : [];

    return (
      <div className="space-y-3 mt-2">
        {/* Per-type summary grid */}
        {summaryEntries.length > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {summaryEntries.map(({ type, count, nearest_m }) => (
              <div key={type} className="bg-white rounded-xl border border-divider p-2.5 flex items-start gap-2">
                <Stethoscope className="w-3.5 h-3.5 text-brand-500 mt-0.5 shrink-0" />
                <div className="min-w-0">
                  <div className="text-[10px] text-ink-faint truncate">{type}</div>
                  <div className="text-sm font-bold text-ink">{count}</div>
                  {nearest_m != null && (
                    <div className="text-[10px] text-ink-faint">nearest {nearest_m.toLocaleString()}m</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
        {/* Individual facility list */}
        {(details.facilities as Record<string, unknown>[]).map((f, i) => (
          <div key={i} className="flex items-center gap-3 p-2.5 rounded-xl bg-surface">
            <Stethoscope className="w-4 h-4 text-brand-600 shrink-0" />
            <div className="flex-1 min-w-0">
              <span className="text-sm text-ink truncate block">{String(f.name)}</span>
              {f.type != null && <span className="text-xs text-ink-faint">{String(f.type)}</span>}
            </div>
            <span className="text-xs text-ink-muted shrink-0">{Number(f.distance_m).toLocaleString()}m</span>
          </div>
        ))}
      </div>
    );
  }

  // Demographics overview cards
  if (details.cards && typeof details.cards === 'object' && !Array.isArray(details.cards)) {
    return <DemographicsCards cards={details.cards as Record<string, { label: string; value: number | null; unit: string; parent?: number | null }>} />;
  }

  // IMD deprivation block
  if (details.decile != null) {
    return (
      <ImdDeprivationBlock
        decile={details.decile as number}
        rank={details.rank as number | null}
        parentAvgDecile={details.parent_avg_decile as number | null}
        income={details.income as number | null}
        employment={details.employment as number | null}
        education={details.education as number | null}
        health={details.health as number | null}
        crime={details.crime as number | null}
        barriers={details.barriers as number | null}
        livingEnvironment={details.living_environment as number | null}
      />
    );
  }

  // Flood risk gauge
  if (details.flood_level != null) {
    return (
      <FloodRiskGauge
        floodLevel={details.flood_level as string}
        riskScore={details.risk_score as number ?? 5}
        zone3Pct={details.zone_3_pct as number | null}
        zone2Pct={details.zone_2_pct as number | null}
        highRiskLsoaCount={details.high_risk_lsoa_count as number | null}
        mediumRiskLsoaCount={details.medium_risk_lsoa_count as number | null}
        totalLsoas={details.total_lsoas as number | null}
        parentZone3Pct={details.parent_zone_3_pct as number | null}
      />
    );
  }

  // PTAL gauge
  if (details.band != null) {
    return (
      <PtalGauge
        band={details.band as string}
        ptaiScore={details.ptai_score as number | null}
        parentAvgPtai={details.parent_avg_ptai as number | null}
        busStops640m={details.bus_stops_640m as number | null}
        heavyStops960m={details.heavy_stops_960m as number | null}
        tflData={details.tfl_data as boolean | undefined}
      />
    );
  }

  // Price by property type chart
  if (details.detached != null || details.semi != null || details.terraced != null || details.flat != null) {
    return (
      <PriceByTypeChart
        detached={details.detached as number | null}
        semi={details.semi as number | null}
        terraced={details.terraced as number | null}
        flat={details.flat as number | null}
        ukMedian={details.uk_median as number | null}
        parentMedian={details.parent_median as number | null}
      />
    );
  }

  // EPC rating chart
  if (details.pct_a != null || details.pct_b != null || details.pct_c != null) {
    return (
      <EpcRatingChart
        pctA={details.pct_a as number | null}
        pctB={details.pct_b as number | null}
        pctC={details.pct_c as number | null}
        pctD={details.pct_d as number | null}
        pctE={details.pct_e as number | null}
        pctF={details.pct_f as number | null}
        pctG={details.pct_g as number | null}
        avgScore={details.avg_energy_score as number | null}
        parentAvgScore={details.parent_avg_score as number | null}
        parentRatings={details.parent_ratings as Record<string, number | null> | null}
        heatGasPct={details.heat_gas_pct as number | null}
        heatElectricPct={details.heat_electric_pct as number | null}
        heatOilPct={details.heat_oil_pct as number | null}
        heatDistrictPct={details.heat_district_pct as number | null}
        heatOtherPct={details.heat_other_pct as number | null}
        heatNonePct={details.heat_none_pct as number | null}
        cPlusPct={details.c_plus_pct as number | null}
        parentCPlusPct={details.parent_c_plus_pct as number | null}
      />
    );
  }

  // Rent by bedroom + yield badges
  // median_rent details: { 1bed: £rent, yield_1bed: %, ... }
  // gross_yield details: { 1bed: %, rent_1bed: £rent, ... }
  if (details['1bed'] != null || details['rent_1bed'] != null) {
    const isRentCard = details['yield_1bed'] != null || details['rent_1bed'] == null;
    const n = (k: string) => details[k] as number | null | undefined;
    return (
      <RentByBedroomChart
        rent1bed={isRentCard ? n('1bed')      : n('rent_1bed')}
        rent2bed={isRentCard ? n('2bed')      : n('rent_2bed')}
        rent3bed={isRentCard ? n('3bed')      : n('rent_3bed')}
        rent4bed={isRentCard ? n('4bed')      : n('rent_4bed')}
        yield1bed={isRentCard ? n('yield_1bed') : n('1bed')}
        yield2bed={isRentCard ? n('yield_2bed') : n('2bed')}
        yield3bed={isRentCard ? n('yield_3bed') : n('3bed')}
        yield4bed={isRentCard ? n('yield_4bed') : n('4bed')}
      />
    );
  }

  // Council tax band grid
  if (details.band_a != null || details.band_d != null) {
    const bands = {
      band_a: details.band_a as number | null,
      band_b: details.band_b as number | null,
      band_c: details.band_c as number | null,
      band_d: details.band_d as number | null,
      band_e: details.band_e as number | null,
      band_f: details.band_f as number | null,
      band_g: details.band_g as number | null,
      band_h: details.band_h as number | null,
    };
    const parents = {
      parent_a: details.parent_a as number | null,
      parent_b: details.parent_b as number | null,
      parent_c: details.parent_c as number | null,
      parent_d: details.parent_d as number | null,
      parent_e: details.parent_e as number | null,
      parent_f: details.parent_f as number | null,
      parent_g: details.parent_g as number | null,
      parent_h: details.parent_h as number | null,
    };
    return <CouncilTaxBandGrid bands={bands} parents={parents} />;
  }

  // Broadband panel: coverage bars (Ofcom Connected Nations data)
  if (details.full_fibre_pct != null || details.superfast_pct != null || details.gigabit_pct != null) {
    const n = (k: string) => details[k] as number | null | undefined ?? null;
    return (
      <BroadbandPanel
        fullFibrePct={n('full_fibre_pct')}
        superfastPct={n('superfast_pct')}
        gigabitPct={n('gigabit_pct')}
        parentFullFibrePct={n('parent_full_fibre_pct')}
        parentSuperfastPct={n('parent_superfast_pct')}
        parentGigabitPct={n('parent_gigabit_pct')}
      />
    );
  }

  // Amenity radar chart: details has { counts: {...}, nearest: [...] }
  if (details.counts && typeof details.counts === 'object' && !Array.isArray(details.counts)) {
    return (
      <AmenityRadarChart
        counts={details.counts as Record<string, number>}
        nearest={details.nearest as Array<{ type: string; name: string; distance_m: number }> | undefined}
      />
    );
  }

  const notes = Object.entries(details).filter(([k, v]) => k.endsWith('_note') && typeof v === 'string');
  const entries = Object.entries(details).filter(([k, v]) => v !== null && v !== undefined && !k.endsWith('_note'));
  if (entries.length === 0 && notes.length === 0) return null;

  return (
    <div className="space-y-2 mt-2">
      {entries.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          {entries.map(([key, value]) => {
            if (typeof value === 'object') return null;
            const label = key.replace(/_/g, ' ').replace(/pct /g, '% ').replace(/^(.)/, (c) => c.toUpperCase());
            const isGbp = unit === 'GBP' || unit === 'GBP/year' || unit === 'GBP/month';
            const display = typeof value === 'number'
              ? isGbp
                ? '£' + value.toLocaleString('en-GB', { maximumFractionDigits: 0 })
                : typeof value === 'number' && String(key).includes('pct')
                ? value.toFixed(1) + '%'
                : value.toLocaleString('en-GB', { maximumFractionDigits: 1 })
              : typeof value === 'boolean'
              ? value ? 'Yes' : 'No'
              : String(value);

            return (
              <div key={key} className="p-2.5 rounded-xl bg-surface">
                <div className="text-[11px] text-ink-faint uppercase tracking-wide font-medium">{label}</div>
                <div className="text-sm font-semibold text-ink mt-0.5">{display}</div>
              </div>
            );
          })}
        </div>
      )}
      {notes.map(([key, value]) => (
        <p key={key} className="text-[11px] text-ink-muted italic px-1">{String(value)}</p>
      ))}
    </div>
  );
}
