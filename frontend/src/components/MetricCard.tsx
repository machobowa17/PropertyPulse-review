import { useState, useRef, useCallback, useEffect, lazy, Suspense } from 'react';
import {
  TrendingUp, TrendingDown, Minus, ArrowUp, ArrowDown,
  Stethoscope, Coffee, TrainFront, TreePine, Dumbbell, MapPin,
} from 'lucide-react';
import type { Metric, PersonaId } from '../types';
import type { PriceByTypeResponse, PriceHistoryResponse } from '../api/client';
import type { SchoolRow, QualitySummary } from './SchoolTable';
import type { NurseryRow, NurserySummary } from './NurseryTable';
import { formatValue } from '../utils/tabs';
import { getTakeaway } from '../utils/personas';
import { REDESIGNED_METRIC_IDS, renderRedesignedDetail } from './RedesignedDetails';
// R3: lazy-load detail components — only parsed when the metric card is expanded
const NewBuildTrendChart      = lazy(() => import('./NewBuildTrendChart'));
const AmenityRadarChart       = lazy(() => import('./AmenityRadarChart'));
const PriceByTypeChart        = lazy(() => import('./PriceByTypeChart'));
const DistrictPriceHistoryChart = lazy(() => import('./DistrictPriceHistoryChart'));
const EpcRatingChart          = lazy(() => import('./EpcRatingChart'));
const PtalGauge               = lazy(() => import('./PtalGauge'));
const DemographicsCards       = lazy(() => import('./DemographicsCards'));
const ImdDeprivationBlock     = lazy(() => import('./ImdDeprivationBlock'));
const CouncilTaxBandGrid      = lazy(() => import('./CouncilTaxBandGrid'));
const RentByBedroomChart      = lazy(() => import('./RentByBedroomChart'));
const BroadbandPanel          = lazy(() => import('./BroadbandPanel'));
const HpiTrendChart           = lazy(() => import('./HpiTrendChart'));
const StationTable            = lazy(() => import('./StationTable'));
const SchoolTable             = lazy(() => import('./SchoolTable'));
const NurseryTable            = lazy(() => import('./NurseryTable'));
const TransactionTable        = lazy(() => import('./TransactionTable'));
const BuildingProfileChart    = lazy(() => import('./BuildingProfileChart'));

// Runtime-safe accessors for details: Record<string, unknown>
// Replaces 40+ unsafe `as` casts with type-checked reads.
type D = Record<string, unknown>;
const num = (d: D, k: string): number | null =>
  typeof d[k] === 'number' ? d[k] : null;
const str = (d: D, k: string): string | null =>
  typeof d[k] === 'string' ? d[k] : null;
const bool = (d: D, k: string): boolean | undefined =>
  typeof d[k] === 'boolean' ? d[k] : undefined;
const arr = (d: D, k: string): D[] =>
  Array.isArray(d[k]) ? (d[k] as D[]) : [];
const rec = <T,>(d: D, k: string): T | null =>
  d[k] != null && typeof d[k] === 'object' && !Array.isArray(d[k]) ? (d[k] as T) : null;

/** Format transaction_volume: "XX sales (YY/LSOA)" — absolute count + per-LSOA rate */
function fmtTxnVol(absolute: number | null, perLsoa: number | null): string {
  if (absolute == null && perLsoa == null) return '—';
  const abs = absolute != null ? absolute.toLocaleString('en-GB') : '—';
  const rate = perLsoa != null ? perLsoa.toLocaleString('en-GB', { maximumFractionDigits: 1 }) : '—';
  return `${abs} sales (${rate}/LSOA)`;
}


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
  building_profile:       { label: 'MHCLG EPC Register', licence: 'OGL v3' },
  // Lifestyle & Connectivity
  nearest_station:        { label: 'NaPTAN / Network Rail', licence: 'OGL v3' },
  ptal:                   { label: 'TfL / NaPTAN', licence: 'OGL v3' },
  ptal_score:             { label: 'TfL / NaPTAN', licence: 'OGL v3' },
  cycling:                { label: 'Sustrans / OSM', licence: 'OGL v3 / ODbL' },
  broadband:              { label: 'Ofcom Connected Nations', licence: 'OGL v3' },
  mobile_coverage:        { label: 'Ofcom Connected Nations', licence: 'OGL v3' },
  ev_chargers:            { label: 'DfT EVCD Register', licence: 'OGL v3' },
  amenities_15min:        { label: 'OpenStreetMap', licence: 'ODbL' },
  commute_distance:       { label: 'Census 2021 (ONS)', licence: 'OGL v3' },
  // Environment & Safety
  flood_risk:             { label: 'EA Flood Map for Planning', licence: 'OGL v3' },
  air_quality_no2:        { label: 'DEFRA AURN', licence: 'OGL v3' },
  air_quality_pm25:       { label: 'DEFRA AURN', licence: 'OGL v3' },
  noise:                  { label: 'DEFRA Strategic Noise Mapping', licence: 'OGL v3' },
  nearest_park:           { label: 'OS Open Greenspace', licence: 'OGL v3' },
  green_cover:            { label: 'OS Open Greenspace', licence: 'OGL v3' },
  green_spaces:           { label: 'OS Open Greenspace', licence: 'OGL v3' },
  parks_1km:              { label: 'OS Open Greenspace', licence: 'OGL v3' },
  sports_recreation:      { label: 'OS Open Greenspace', licence: 'OGL v3' },
  crime_rate:             { label: 'Home Office Crime Statistics', licence: 'OGL v3' },
  crime_trend:            { label: 'Home Office Crime Statistics', licence: 'OGL v3' },
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
  ethnicity:              { label: 'Census 2021 (ONS)', licence: 'OGL v3' },
  religion:               { label: 'Census 2021 (ONS)', licence: 'OGL v3' },
  primary_schools:        { label: 'Ofsted / Get Information About Schools', licence: 'OGL v3' },
  secondary_schools:      { label: 'Ofsted / Get Information About Schools', licence: 'OGL v3' },
  nurseries:              { label: 'Ofsted Childcare Provider Inspections', licence: 'OGL v3' },
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
  priceByTypeData?: PriceByTypeResponse;
  priceHistoryData?: PriceHistoryResponse;
  areaName?: string;
  sessionKey?: string;
  isMapActive?: boolean;
  modeMultiplier?: number;
}

interface Trend { direction: 'up' | 'down' | 'flat'; pct: number; }

function TrendBadge({ trend, direction }: { trend: Trend; direction?: Metric['interpretation_direction'] }) {
  const pct = typeof trend.pct === 'number' && Number.isFinite(trend.pct) ? trend.pct : 0;
  const label = `${pct > 0 ? '+' : ''}${pct.toFixed(1)}%`;
  // Determine semantic color: "up" is good for higher_is_better, bad for lower_is_better
  let colorClass = 'text-ink-faint'; // flat / neutral
  if (trend.direction === 'up') {
    colorClass = direction === 'lower_is_better' ? 'text-amber-600' : 'text-blue-600';
  } else if (trend.direction === 'down') {
    colorClass = direction === 'lower_is_better' ? 'text-blue-600' : 'text-amber-600';
  }
  const Arrow = trend.direction === 'up' ? ArrowUp : trend.direction === 'down' ? ArrowDown : Minus;
  return (
    <span className={`inline-flex items-center gap-0.5 text-[11px] font-semibold ${colorClass}`}>
      <Arrow className="w-3 h-3" />{trend.direction === 'flat' ? '0%' : label}
    </span>
  );
}

/** Interpretation-aware colour for parent comparison.
 * lower_is_better + lower_than_parent → green (good)
 * higher_is_better + higher_than_parent → green (good)
 * Otherwise uses amber for worse, neutral for equal/unknown */
function comparisonColor(
  flag: Metric['comparison_flag'],
  direction?: Metric['interpretation_direction'],
): 'green' | 'amber' | 'neutral' {
  if (!flag || !direction || direction === 'neutral') return 'neutral';
  const isGood =
    (direction === 'lower_is_better' && flag === 'lower_than_parent') ||
    (direction === 'higher_is_better' && flag === 'higher_than_parent');
  const isBad =
    (direction === 'lower_is_better' && flag === 'higher_than_parent') ||
    (direction === 'higher_is_better' && flag === 'lower_than_parent');
  if (isGood) return 'green';
  if (isBad) return 'amber';
  return 'neutral';
}

export default function MetricCard({ metric, persona, parentName, priceByTypeData, priceHistoryData, areaName, sessionKey, isMapActive, modeMultiplier }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [detailsReady, setDetailsReady] = useState(false);
  const detailsRef = useRef<HTMLDivElement>(null);
  const takeaway = getTakeaway(metric, persona);
  const takeawayText = takeaway?.soWhat
    ? takeaway.watchOut && takeaway.watchOut !== 'None'
      ? `${takeaway.soWhat} — ${takeaway.watchOut.charAt(0).toLowerCase()}${takeaway.watchOut.slice(1)}`
      : takeaway.soWhat
    : '';
  // Prefer nested trend object from contract; fall back to details.trend for backward compat
  const trendNested = metric.trend?.status === 'trended' && metric.trend.direction
    ? { direction: metric.trend.direction, pct: typeof metric.trend.value === 'number' ? metric.trend.value : 0 }
    : null;
  const trend: Trend | undefined = trendNested ?? (metric.details ? rec<Trend>(metric.details, 'trend') ?? undefined : undefined);
  const colours = COLOUR_STYLES[takeaway?.colour ?? 'neutral'];
  const hasDetails = metric.details && Object.keys(metric.details).length > 0;
  const handleToggle = useCallback(() => {
    if (!hasDetails) return;
    const opening = !expanded;
    setExpanded(opening);
    if (opening && detailsRef.current && window.innerWidth < 1024) {
      detailsRef.current.addEventListener('transitionend', function scrollOnce() {
        detailsRef.current?.removeEventListener('transitionend', scrollOnce);
        detailsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      });
    }
  }, [expanded, hasDetails]);

  // Defer chart mount until expand animation settles (prevents Recharts -1 width/height)
  useEffect(() => {
    if (!expanded) { setDetailsReady(false); return; }
    const el = detailsRef.current;
    if (!el) { setDetailsReady(true); return; }
    const onEnd = () => setDetailsReady(true);
    el.addEventListener('transitionend', onEnd, { once: true });
    // Fallback if transitionend doesn't fire (e.g. reduced motion)
    const fallback = setTimeout(onEnd, 250);
    return () => { el.removeEventListener('transitionend', onEnd); clearTimeout(fallback); };
  }, [expanded]);

  const ComparisonIcon = metric.comparison_flag === 'higher_than_parent'
    ? TrendingUp
    : metric.comparison_flag === 'lower_than_parent'
    ? TrendingDown
    : Minus;
  const compColour = comparisonColor(metric.comparison_flag, metric.interpretation_direction);
  const compColourClass = compColour === 'green'
    ? 'text-emerald-600'
    : compColour === 'amber'
    ? 'text-amber-600'
    : 'text-ink-faint';

  return (
    <div
      className={`
        rounded-2xl bg-white transition-all duration-200 overflow-hidden
        ${expanded ? 'shadow-md ring-1 ring-brand-200/50 bg-brand-50/30 border-l-2 border-l-brand-500' : 'shadow-sm hover:shadow-md hover:-translate-y-px'}
      `}
    >
      {/* ═══ Metric Row (prototype inline style) ═══ */}
      <button
        onClick={handleToggle}
        aria-expanded={hasDetails ? expanded : undefined}
        aria-label={hasDetails ? `${metric.name} — ${expanded ? 'collapse' : 'expand'} details` : metric.name}
        className={`w-full flex items-center gap-4 px-5 py-3.5 text-left group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:rounded-xl hover:bg-surface-warm/50 transition-colors ${hasDetails ? 'cursor-pointer' : 'cursor-default'}`}
      >
        {/* Metric name + decision question */}
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-ink truncate flex items-center gap-1.5">
            {metric.name}
            {isMapActive && <MapPin size={13} className="text-brand-500 shrink-0" />}
            {modeMultiplier != null && modeMultiplier > 1 && (
              <span className="text-[9px] font-medium px-1 py-0.5 rounded bg-emerald-50 text-emerald-600 shrink-0">Prioritised</span>
            )}
            {modeMultiplier != null && modeMultiplier < 1 && modeMultiplier > 0 && (
              <span className="text-[9px] font-medium px-1 py-0.5 rounded bg-amber-50 text-amber-600 shrink-0">Lower priority</span>
            )}
          </div>
          {metric.decision_question && <div className="text-[11px] text-ink-faint truncate">{metric.decision_question}</div>}
        </div>

        {/* Local value + trend */}
        <div className="text-right shrink-0">
          <div className="text-lg font-bold font-mono text-ink tabular-nums">
            {metric.id === 'transaction_volume' && metric.details
              ? fmtTxnVol(num(metric.details, 'local_absolute'), metric.local_value as number | null)
              : formatValue(metric.local_value, metric.unit)}
          </div>
          {trend && metric.id !== 'avg_price' && metric.id !== 'transaction_volume' && <TrendBadge trend={trend} direction={metric.interpretation_direction} />}
        </div>

        {/* Parent comparison */}
        <div className="w-28 text-right shrink-0 hidden sm:block">
          {metric.parent_value != null ? (
            <span className={`inline-flex items-center gap-1.5 text-sm ${compColourClass}`}>
              <ComparisonIcon className="w-3.5 h-3.5 shrink-0" />
              {metric.id === 'transaction_volume' && metric.details
                ? fmtTxnVol(num(metric.details, 'parent_absolute'), metric.parent_value as number | null)
                : formatValue(metric.parent_value, metric.unit)}
            </span>
          ) : (
            <span className="text-ink-faint">—</span>
          )}
        </div>

        {/* Takeaway pill (merged So What + Watch Out) */}
        <div className="w-44 shrink-0 hidden lg:block">
          {takeawayText ? (
            <span className={`inline-block px-2.5 py-1 rounded-lg text-xs font-medium ${colours.bg} ${colours.text} border ${colours.border} max-w-full truncate`}>
              {takeawayText}
            </span>
          ) : null}
        </div>

        {/* Chevron */}
        <svg className={`w-4 h-4 text-ink-faint shrink-0 transition-transform ${expanded ? 'rotate-90' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
      </button>

      {/* Mobile-only: parent comparison + takeaway pill below the row */}
      {(metric.parent_value != null || takeawayText) && (
        <div className="sm:hidden flex flex-wrap gap-2 px-5 pb-3 -mt-1">
          {metric.parent_value != null && (
            <span className={`inline-flex items-center gap-1 text-xs ${compColourClass}`}>
              <ComparisonIcon className="w-3 h-3" />
              {formatValue(metric.parent_value, metric.unit)}
              <span className="opacity-60">({parentName})</span>
            </span>
          )}
        </div>
      )}
      {takeawayText && (
        <div className="lg:hidden flex flex-wrap gap-2 px-5 pb-3 -mt-1">
          <div className={`px-2.5 py-1 rounded-lg text-xs font-medium ${colours.bg} ${colours.text} border ${colours.border}`}>
            {takeawayText}
          </div>
        </div>
      )}

      {/* ═══ Expanded details (shared) ═══ */}
      <div
        ref={detailsRef}
        className="grid transition-[grid-template-rows,opacity] duration-200 ease-out"
        style={{ gridTemplateRows: expanded && metric.details ? '1fr' : '0fr', opacity: expanded && metric.details ? 1 : 0, visibility: expanded && metric.details ? 'visible' : 'hidden' }}
      >
        <div className="overflow-hidden">
          {detailsReady && <Suspense fallback={null}>
            <div className="px-4 lg:px-5 pb-4 pt-3 border-t border-divider/50 bg-surface-warm/30">
              {/* Priority 1: Redesigned detail renderers (prototype-approved) */}
              {REDESIGNED_METRIC_IDS.has(metric.id) && renderRedesignedDetail(metric)}
              {/* Priority 2: Price charts for price metrics */}
              {!REDESIGNED_METRIC_IDS.has(metric.id) && priceByTypeData && Object.keys(priceByTypeData.by_type).length > 0 && (
                <DistrictPriceHistoryChart
                  data={priceByTypeData}
                  overallLocal={priceHistoryData?.local}
                  overallRegional={priceHistoryData?.regional}
                  regionalName={priceHistoryData?.regional_name}
                  areaName={areaName}
                  priceField={metric.id === 'median_price' ? 'median_price' : metric.id === 'price_per_sqft' ? 'avg_ppsf' : 'avg_price'}
                  byBedrooms={priceHistoryData?.by_bedrooms}
                />
              )}
              {/* Priority 3: Existing detail renderers (SchoolTable, StationTable, etc.) */}
              {!REDESIGNED_METRIC_IDS.has(metric.id) && !(priceByTypeData && Object.keys(priceByTypeData.by_type).length > 0) && (
                <DetailsRenderer
                  details={metric.details ?? {}}
                  unit={metric.unit}
                  parentName={parentName}
                />
              )}
              {metric.id === 'transaction_volume' && sessionKey && expanded && (
                <Suspense fallback={null}>
                  <TransactionTable sessionKey={sessionKey} />
                </Suspense>
              )}
              {/* Quality flags (deduplicated against data notes) */}
              {(() => {
                // Collect all _note texts from details to avoid showing them twice
                const noteTexts = new Set<string>();
                if (metric.details) {
                  for (const [k, v] of Object.entries(metric.details)) {
                    if (k.endsWith('_note') && typeof v === 'string') noteTexts.add(v);
                  }
                }
                const flags = metric.quality_flags?.filter(f => !noteTexts.has(f)) ?? [];
                const fallback = metric.quality_notes && !noteTexts.has(metric.quality_notes) ? metric.quality_notes : null;
                if (flags.length === 0 && !fallback) return null;
                return (
                  <div className="mt-3 px-3 py-2 rounded-lg bg-amber-50 border border-amber-200/60 text-[11px] text-amber-800">
                    {flags.length > 0
                      ? flags.map((flag, i) => <p key={i}>{flag}</p>)
                      : fallback}
                  </div>
                );
              })()}
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
          </Suspense>}
        </div>
      </div>
    </div>
  );
}

/** Render _note entries from details (deduplicated by text) */
function DataNotes({ details }: { details: Record<string, unknown> }) {
  const seen = new Set<string>();
  const notes = Object.entries(details).filter(([k, v]) => {
    if (!k.endsWith('_note') || typeof v !== 'string') return false;
    if (seen.has(v)) return false;
    seen.add(v);
    return true;
  });
  if (notes.length === 0) return null;
  return (
    <div className="mt-3">
      {notes.map(([key, value]) => (
        <p key={key} className="text-[11px] text-ink-muted italic px-1">{String(value)}</p>
      ))}
    </div>
  );
}

/** Render details object as sub-rows or list, always appending data notes */
function DetailsRenderer({ details, unit, parentName }: { details: Record<string, unknown>; unit: string; parentName: string }) {
  const content = renderDetailsContent(details, unit, parentName);
  const notes = <DataNotes details={details} />;
  // If only notes and no content, still show notes
  if (!content) return notes;
  return <>{content}{notes}</>;
}

/** NHS facilities with type filter toggles and scrollable table */
function NhsFacilitiesDetail({ details }: { details: Record<string, unknown> }) {
  const [activeType, setActiveType] = useState<string | null>(null);
  const typeSummary = rec<Record<string, { count: number; nearest_m: number | null }>>(details, 'type_summary');
  const TYPE_ORDER = ['GP', 'Hospital', 'Pharmacy', 'Dentist', 'Optician', 'Care Home'];
  const summaryEntries = typeSummary
    ? [...TYPE_ORDER.filter((t) => t in typeSummary), ...Object.keys(typeSummary).filter((t) => !TYPE_ORDER.includes(t))]
        .map((t) => ({ type: t, ...typeSummary[t] }))
    : [];

  const allFacilities = arr(details, 'facilities');
  const filtered = activeType
    ? allFacilities.filter((f) => String(f.type) === activeType)
    : allFacilities;

  return (
    <div className="space-y-3 mt-2">
      {summaryEntries.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => setActiveType(null)}
            className={`px-2.5 py-1 rounded-lg text-[11px] font-medium border transition-colors ${
              activeType === null
                ? 'bg-brand-600 text-white border-brand-600'
                : 'bg-surface text-ink-muted border-divider hover:border-brand-300'
            }`}
          >
            All ({allFacilities.length})
          </button>
          {summaryEntries.map(({ type, count }) => (
            <button
              key={type}
              onClick={() => setActiveType(activeType === type ? null : type)}
              className={`px-2.5 py-1 rounded-lg text-[11px] font-medium border transition-colors ${
                activeType === type
                  ? 'bg-brand-600 text-white border-brand-600'
                  : 'bg-surface text-ink-muted border-divider hover:border-brand-300'
              }`}
            >
              {type} ({count})
            </button>
          ))}
        </div>
      )}
      <div className="max-h-[260px] overflow-y-auto space-y-1.5">
        {filtered.map((f, i) => (
          <div key={i} className="flex items-center gap-3 p-2.5 rounded-xl bg-surface">
            <Stethoscope className="w-4 h-4 text-brand-600 shrink-0" />
            <div className="flex-1 min-w-0">
              <span className="text-sm text-ink truncate block">{String(f.name)}</span>
              {f.type != null && <span className="text-xs text-ink-faint">{String(f.type)}</span>}
            </div>
            {f.distance_m != null && <span className="text-xs text-ink-muted shrink-0">{Number(f.distance_m).toLocaleString()}m</span>}
          </div>
        ))}
        {filtered.length === 0 && (
          <div className="text-xs text-ink-faint text-center py-3">No facilities of this type</div>
        )}
      </div>
    </div>
  );
}

function renderDetailsContent(details: Record<string, unknown>, unit: string, parentName: string): React.ReactNode {
  if (Array.isArray(details.schools)) {
    // Use SchoolTable when all_schools array is available (from Hetzner School API)
    const allSchools = arr(details, 'all_schools') as unknown as SchoolRow[];
    const summary = details.summary as QualitySummary | undefined;
    if (allSchools.length > 0) {
      return (
        <Suspense fallback={null}>
          <SchoolTable
            schools={allSchools}
            summary={summary}
          />
        </Suspense>
      );
    }

    // Fallback: simple numbered list (if SchoolTable data unavailable)
    const qualityPct = num(details, 'quality_pct');
    const parentQualityPct = num(details, 'parent_quality_pct');
    const goodCount = num(details, 'good_count');
    const totalInArea = num(details, 'total_in_area');
    return (
      <div className="space-y-2 mt-2">
        {qualityPct != null && (
          <div className="flex flex-wrap items-center gap-3 px-3 py-2 rounded-lg bg-brand-50/50 border border-brand-100/60">
            <span className="text-sm font-semibold text-brand-700">{qualityPct.toFixed(0)}% Outstanding/Good</span>
            {goodCount != null && totalInArea != null && (
              <span className="text-xs text-ink-muted">({goodCount} of {totalInArea})</span>
            )}
            {parentQualityPct != null && (
              <span className="text-xs text-ink-faint">vs {parentQualityPct.toFixed(0)}% area avg</span>
            )}
          </div>
        )}
        <div className="max-h-[260px] overflow-y-auto space-y-1.5">
          {arr(details, 'schools').map((s, i) => (
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
      </div>
    );
  }

  if (Array.isArray(details.nurseries)) {
    const allNurseries = arr(details, 'nurseries') as unknown as NurseryRow[];
    const nurserySummary = details.nursery_summary as NurserySummary | undefined;
    if (allNurseries.length > 0) {
      return (
        <Suspense fallback={null}>
          <NurseryTable
            nurseries={allNurseries}
            summary={nurserySummary}
          />
        </Suspense>
      );
    }
  }

  if (Array.isArray(details.stations)) {
    // Use enriched all_stations when available (includes bus/tram/metro/ferry + NaPTAN columns)
    const allStations = arr(details, 'all_stations');
    const modeCounts = rec<Record<string, number>>(details, 'mode_counts') ?? rec<Record<string, number>>(details, 'mode_counts_1km');
    const isAreaMode = details.bus_stops != null; // area mode sends bus_stops, postcode sends bus_stops_500m

    if (allStations.length > 0) {
      return (
        <Suspense fallback={null}>
          <StationTable
            stations={allStations as unknown as { name: string; type: string; category: string; atco_code: string; street?: string; indicator?: string; locality?: string; parent_locality?: string; suburb?: string; status?: string; distance_m?: number }[]}
            modeCounts={modeCounts}
            isArea={isAreaMode}
          />
        </Suspense>
      );
    }

    // Fallback: old-style station list (before enrichment columns are populated)
    const stations = arr(details, 'stations');
    return (
      <div className="space-y-2 mt-2">
        <div className="max-h-[260px] overflow-y-auto space-y-1.5">
          {stations.map((s, i) => {
            const sType = String(s.type ?? '');
            const isBus = sType.startsWith('B') || sType === 'FBT';
            const StopIcon = isBus ? Coffee : TrainFront;
            return (
              <div key={i} className="flex items-center gap-3 p-2.5 rounded-xl bg-surface">
                <StopIcon className={`w-4 h-4 shrink-0 ${isBus ? 'text-amber-600' : 'text-brand-600'}`} />
                <span className="text-sm text-ink flex-1 truncate">{String(s.name)}</span>
                {s.distance_m != null && <span className="text-xs text-ink-muted shrink-0">{Number(s.distance_m).toLocaleString()}m</span>}
              </div>
            );
          })}
        </div>
        {details.bus_stops_500m != null && (
          <div className="text-xs text-ink-muted mt-1">Bus stops within 500m: {String(details.bus_stops_500m)}</div>
        )}
        {details.bus_stops != null && (
          <div className="text-xs text-ink-muted mt-1">Bus stops in area: {String(details.bus_stops)}</div>
        )}
      </div>
    );
  }

  // Sports & recreation: tabulated list with type counts
  if (Array.isArray(details.facilities) && !details.type_summary) {
    const facilities = arr(details, 'facilities');
    const typeCountEntries = Object.entries(details).filter(
      ([k, v]) => k.endsWith('_count') && typeof v === 'number'
    );
    return (
      <div className="space-y-3 mt-2">
        {typeCountEntries.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {typeCountEntries.map(([k, v]) => (
              <span key={k} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-surface border border-divider text-xs text-ink-muted font-medium">
                {k.replace(/_count$/, '').replace(/_/g, ' ').replace(/^(.)/, c => c.toUpperCase())}: {String(v)}
              </span>
            ))}
          </div>
        )}
        {facilities.length > 0 && (
          <div className="max-h-[260px] overflow-y-auto space-y-1.5">
            {facilities.map((f, i) => (
              <div key={i} className="flex items-center gap-3 p-2.5 rounded-xl bg-surface">
                <Dumbbell className="w-4 h-4 text-brand-500 shrink-0" />
                <span className="text-sm text-ink flex-1 truncate">{String(f.name)}</span>
                {f.type != null && <span className="text-xs text-ink-faint shrink-0">{String(f.type)}</span>}
                {f.distance_m != null && <span className="text-xs text-ink-muted shrink-0">{Number(f.distance_m).toLocaleString()}m</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Parks list: details has { parks: [...] }
  if (Array.isArray(details.parks)) {
    return (
      <div className="mt-2">
        <div className="max-h-[260px] overflow-y-auto space-y-1.5">
          {arr(details, 'parks').map((p, i) => (
            <div key={i} className="flex items-center gap-3 p-2.5 rounded-xl bg-surface">
              <TreePine className="w-4 h-4 text-signal-green shrink-0" />
              <div className="flex-1 min-w-0">
                <span className="text-sm text-ink truncate block">{String(p.name)}</span>
                {p.type != null && <span className="text-xs text-ink-faint">{String(p.type)}</span>}
              </div>
              {p.area_ha != null && <span className="text-xs text-ink-muted shrink-0">{Number(p.area_ha).toFixed(1)} ha</span>}
              {p.distance_m != null && <span className="text-xs text-ink-muted shrink-0">{Number(p.distance_m).toLocaleString()}m</span>}
            </div>
          ))}
        </div>
      </div>
    );
  }

  // NHS facilities: type_summary + filterable list
  if (Array.isArray(details.facilities)) {
    return <NhsFacilitiesDetail details={details} />;
  }

  // Demographics overview cards
  if (details.cards && typeof details.cards === 'object' && !Array.isArray(details.cards)) {
    return <DemographicsCards cards={rec<Record<string, { label: string; value: number | null; unit: string; parent?: number | null }>>(details, 'cards')!} />;
  }

  // IMD deprivation block
  if (details.decile != null) {
    return (
      <ImdDeprivationBlock
        decile={num(details, 'decile')!}
        rank={num(details, 'rank')}
        parentAvgDecile={num(details, 'parent_avg_decile')}
        income={num(details, 'income')}
        employment={num(details, 'employment')}
        education={num(details, 'education')}
        health={num(details, 'health')}
        crime={num(details, 'crime')}
        barriers={num(details, 'barriers')}
        livingEnvironment={num(details, 'living_environment')}
      />
    );
  }

  // Flood risk: simple breakdown (P34: dropped infographic)
  if (details.flood_level != null) {
    const z3 = num(details, 'zone_3_pct');
    const z2 = num(details, 'zone_2_pct');
    const pz3 = num(details, 'parent_zone_3_pct');
    const totalLsoas = num(details, 'total_lsoas');
    return (
      <div className="space-y-2 mt-2">
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          <div className="p-2.5 rounded-xl bg-surface">
            <div className="text-[11px] text-ink-faint uppercase tracking-wide font-medium">Risk Level</div>
            <div className="text-sm font-semibold text-ink mt-0.5">{String(details.flood_level)}</div>
          </div>
          {z3 != null && (
            <div className="p-2.5 rounded-xl bg-surface">
              <div className="text-[11px] text-ink-faint uppercase tracking-wide font-medium">Zone 3 (High)</div>
              <div className="text-sm font-semibold text-ink mt-0.5">{z3.toFixed(1)}% of LSOAs</div>
              {pz3 != null && <div className="text-[10px] text-ink-faint mt-0.5">vs {pz3.toFixed(1)}% region</div>}
            </div>
          )}
          {z2 != null && (
            <div className="p-2.5 rounded-xl bg-surface">
              <div className="text-[11px] text-ink-faint uppercase tracking-wide font-medium">Zone 2 (Medium)</div>
              <div className="text-sm font-semibold text-ink mt-0.5">{z2.toFixed(1)}% of LSOAs</div>
            </div>
          )}
          {totalLsoas != null && (
            <div className="p-2.5 rounded-xl bg-surface">
              <div className="text-[11px] text-ink-faint uppercase tracking-wide font-medium">LSOAs Assessed</div>
              <div className="text-sm font-semibold text-ink mt-0.5">{totalLsoas}</div>
            </div>
          )}
        </div>
      </div>
    );
  }

  // PTAL gauge
  if (details.band != null) {
    return (
      <PtalGauge
        band={str(details, 'band') ?? ''}
        ptaiScore={num(details, 'ptai_score')}
        parentAvgPtai={num(details, 'parent_avg_ptai')}
        busStops640m={num(details, 'bus_stops_640m')}
        heavyStops960m={num(details, 'heavy_stops_960m')}
        tflData={bool(details, 'tfl_data')}
      />
    );
  }

  // HPI trend chart (price_trend_yoy)
  if (Array.isArray(details.hpi_series) && details.hpi_series.length > 0) {
    return <HpiTrendChart series={details.hpi_series as Array<{ year: number; avg_price: number | null; yoy_pct: number | null; detached: number | null; semi: number | null; terraced: number | null; flat: number | null }>} />;
  }

  // Price by property type chart
  if (details.detached != null || details.semi != null || details.terraced != null || details.flat != null) {
    return (
      <PriceByTypeChart
        detached={num(details, 'detached')}
        semi={num(details, 'semi')}
        terraced={num(details, 'terraced')}
        flat={num(details, 'flat')}
        ukMedian={num(details, 'uk_median')}
        parentMedian={num(details, 'parent_median')}
      />
    );
  }

  // EPC rating chart (grouped bands: A-B, C, D, E-G)
  if (details.pct_ab != null || details.pct_c != null || details.avg_energy_score != null) {
    return (
      <EpcRatingChart
        pctAb={num(details, 'pct_ab')}
        pctC={num(details, 'pct_c')}
        pctD={num(details, 'pct_d')}
        pctEg={num(details, 'pct_eg')}
        avgScore={num(details, 'avg_energy_score')}
        parentAvgScore={num(details, 'parent_avg_score')}
        parentRatings={rec<Record<string, number | null>>(details, 'parent_ratings')}
        cPlusPct={num(details, 'c_plus_pct')}
        parentCPlusPct={num(details, 'parent_c_plus_pct')}
      />
    );
  }

  // Building Profile — heating, CO2, costs, construction age, renewables
  if (details.avg_co2 != null || details.avg_energy_kwh != null) {
    return (
      <BuildingProfileChart
        avgCo2={num(details, 'avg_co2')}
        avgEnergyKwh={num(details, 'avg_energy_kwh')}
        avgHeatingCost={num(details, 'avg_heating_cost')}
        avgHotwaterCost={num(details, 'avg_hotwater_cost')}
        avgLightingCost={num(details, 'avg_lighting_cost')}
        heatGasPct={num(details, 'heat_gas_pct')}
        heatElectricPct={num(details, 'heat_electric_pct')}
        heatOilPct={num(details, 'heat_oil_pct')}
        heatDistrictPct={num(details, 'heat_district_pct')}
        heatOtherPct={num(details, 'heat_other_pct')}
        heatNonePct={num(details, 'heat_none_pct')}
        pctMainsGas={num(details, 'pct_mains_gas')}
        pctSolar={num(details, 'pct_solar')}
        agePre1900Pct={num(details, 'age_pre1900_pct')}
        age1900_1929Pct={num(details, 'age_1900_1929_pct')}
        age1930_1949Pct={num(details, 'age_1930_1949_pct')}
        age1950_1966Pct={num(details, 'age_1950_1966_pct')}
        age1967_1982Pct={num(details, 'age_1967_1982_pct')}
        age1983_2002Pct={num(details, 'age_1983_2002_pct')}
        agePost2002Pct={num(details, 'age_post2002_pct')}
        windowsGoodPct={num(details, 'windows_good_pct')}
        windowsVpoorPct={num(details, 'windows_vpoor_pct')}
        windowsPoorPct={num(details, 'windows_poor_pct')}
        windowsAvgPct={num(details, 'windows_avg_pct')}
        wallsGoodPct={num(details, 'walls_good_pct')}
        wallsVpoorPct={num(details, 'walls_vpoor_pct')}
        roofGoodPct={num(details, 'roof_good_pct')}
        roofVpoorPct={num(details, 'roof_vpoor_pct')}
        glazeSinglePct={num(details, 'glaze_single_pct')}
        glazeDoublePct={num(details, 'glaze_double_pct')}
        glazeTriplePct={num(details, 'glaze_triple_pct')}
        avgMultiGlazePct={num(details, 'avg_multi_glaze_pct')}
        formDetachedPct={num(details, 'form_detached_pct')}
        formSemiPct={num(details, 'form_semi_pct')}
        formTerracePct={num(details, 'form_terrace_pct')}
        formEndTerracePct={num(details, 'form_end_terrace_pct')}
      />
    );
  }

  // Rent by bedroom + yield badges
  // median_rent details: { 1bed: £rent, yield_1bed: %, ... }
  // gross_yield details: { 1bed: %, rent_1bed: £rent, ... }
  if (details['1bed'] != null || details['rent_1bed'] != null) {
    const isRentCard = details['yield_1bed'] != null || details['rent_1bed'] == null;
    return (
      <RentByBedroomChart
        rent1bed={isRentCard ? num(details, '1bed')      : num(details, 'rent_1bed')}
        rent2bed={isRentCard ? num(details, '2bed')      : num(details, 'rent_2bed')}
        rent3bed={isRentCard ? num(details, '3bed')      : num(details, 'rent_3bed')}
        rent4bed={isRentCard ? num(details, '4bed')      : num(details, 'rent_4bed')}
        yield1bed={isRentCard ? num(details, 'yield_1bed') : num(details, '1bed')}
        yield2bed={isRentCard ? num(details, 'yield_2bed') : num(details, '2bed')}
        yield3bed={isRentCard ? num(details, 'yield_3bed') : num(details, '3bed')}
        yield4bed={isRentCard ? num(details, 'yield_4bed') : num(details, '4bed')}
      />
    );
  }

  // Council tax band grid
  if (details.band_a != null || details.band_d != null) {
    const bands = {
      band_a: num(details, 'band_a'),
      band_b: num(details, 'band_b'),
      band_c: num(details, 'band_c'),
      band_d: num(details, 'band_d'),
      band_e: num(details, 'band_e'),
      band_f: num(details, 'band_f'),
      band_g: num(details, 'band_g'),
      band_h: num(details, 'band_h'),
    };
    const parents = {
      parent_a: num(details, 'parent_a'),
      parent_b: num(details, 'parent_b'),
      parent_c: num(details, 'parent_c'),
      parent_d: num(details, 'parent_d'),
      parent_e: num(details, 'parent_e'),
      parent_f: num(details, 'parent_f'),
      parent_g: num(details, 'parent_g'),
      parent_h: num(details, 'parent_h'),
    };
    return <CouncilTaxBandGrid bands={bands} parents={parents} />;
  }

  // Broadband panel: coverage bars (Ofcom Connected Nations data)
  if (details.full_fibre_pct != null || details.superfast_pct != null || details.gigabit_pct != null) {
    return (
      <BroadbandPanel
        fullFibrePct={num(details, 'full_fibre_pct')}
        superfastPct={num(details, 'superfast_pct')}
        gigabitPct={num(details, 'gigabit_pct')}
        parentFullFibrePct={num(details, 'parent_full_fibre_pct')}
        parentSuperfastPct={num(details, 'parent_superfast_pct')}
        parentGigabitPct={num(details, 'parent_gigabit_pct')}
      />
    );
  }

  // Amenity radar chart: details has { counts: {...}, nearest: [...] }
  if (details.counts && typeof details.counts === 'object' && !Array.isArray(details.counts)) {
    return (
      <AmenityRadarChart
        counts={rec<Record<string, number>>(details, 'counts')!}
        nearest={Array.isArray(details.nearest) ? details.nearest as Array<{ type: string; name: string; distance_m?: number }> : undefined}
      />
    );
  }

  // New build trend chart
  if (Array.isArray(details.nb_trend)) {
    return (
      <NewBuildTrendChart
        trend={arr(details, 'nb_trend') as Array<{ year: number; new_builds: number; total: number; pct: number }>}
      />
    );
  }



  // Transaction volume YoY summary: single readable sentence
  if (typeof details.yoy_summary === 'string') {
    return (
      <div className="mt-2 text-xs text-ink-muted">
        {details.yoy_summary}
      </div>
    );
  }

  // Breakdown table: freehold/leasehold, housing tenure, housing stock
  if (str(details, 'breakdown_type') === 'tenure_table' && Array.isArray(details.breakdown)) {
    const rows = details.breakdown as { label: string; count: number | null; pct: number | null; parent_pct: number | null; avg_price?: number | null }[];
    const countLabel = str(details, 'count_label') || '#';
    const hasAvgPrice = rows.some((r) => r.avg_price != null);
    const freeholdPremium = typeof details.freehold_premium === 'number' ? details.freehold_premium : null;
    // Stacked bar colours — up to 6 segments
    const BAR_COLOURS = ['#2563eb', '#f59e0b', '#10b981', '#8b5cf6', '#ef4444', '#6b7280'];
    const barSegments = rows.filter((r) => r.pct != null && r.pct > 0);
    return (
      <div className="space-y-3 mt-2">
        {/* Visual stacked bar */}
        {barSegments.length > 0 && (
          <div>
            <div className="flex h-5 rounded-full overflow-hidden">
              {barSegments.map((row, i) => (
                <div
                  key={row.label}
                  style={{ width: `${row.pct}%`, backgroundColor: BAR_COLOURS[i % BAR_COLOURS.length] }}
                  className="flex items-center justify-center text-[10px] font-semibold text-white min-w-[28px] transition-all"
                  title={`${row.label}: ${row.pct?.toFixed(1)}%`}
                >
                  {(row.pct ?? 0) >= 12 ? `${row.pct?.toFixed(0)}%` : ''}
                </div>
              ))}
            </div>
            <div className="flex gap-3 mt-1.5 flex-wrap">
              {barSegments.map((row, i) => (
                <div key={row.label} className="flex items-center gap-1.5 text-[11px] text-ink-muted">
                  <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: BAR_COLOURS[i % BAR_COLOURS.length] }} />
                  {row.label}
                </div>
              ))}
            </div>
          </div>
        )}
        {/* Freehold premium callout */}
        {freeholdPremium != null && freeholdPremium > 0 && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-50 border border-amber-200/60 text-xs">
            <span className="font-semibold text-amber-800">{freeholdPremium.toFixed(1)}×</span>
            <span className="text-amber-700">freehold premium — freehold properties cost {freeholdPremium.toFixed(1)}× more than leasehold on average</span>
          </div>
        )}
        <div className="overflow-x-auto rounded-xl border border-divider">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-surface">
                <th className="text-left px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">Type</th>
                <th className="text-right px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">{countLabel}</th>
                <th className="text-right px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">%</th>
                {hasAvgPrice && (
                  <th className="text-right px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">Avg Price</th>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-divider/50">
              {rows.map((row) => (
                <tr key={row.label} className="hover:bg-brand-50/30 transition-colors">
                  <td className="px-3 py-2 font-medium text-ink">{row.label}</td>
                  <td className="px-3 py-2 text-right text-ink-muted tabular-nums">
                    {row.count != null ? row.count.toLocaleString('en-GB') : '—'}
                  </td>
                  <td className="px-3 py-2 text-right text-ink tabular-nums">
                    {row.pct != null ? (
                      <div>
                        <span className="font-semibold">{row.pct.toFixed(1)}%</span>
                        {row.parent_pct != null && (
                          <div className="text-[10px] text-ink-faint leading-tight">vs {row.parent_pct.toFixed(1)}% for {parentName}</div>
                        )}
                      </div>
                    ) : '—'}
                  </td>
                  {hasAvgPrice && (
                    <td className="px-3 py-2 text-right text-ink tabular-nums font-semibold">
                      {row.avg_price != null ? '£' + row.avg_price.toLocaleString('en-GB', { maximumFractionDigits: 0 }) : '—'}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  // Generic fallback: key-value grid (notes handled by parent DetailsRenderer wrapper)
  const detailUnit = typeof details.detail_unit === 'string' ? details.detail_unit : null;
  const entries = Object.entries(details).filter(([k, v]) => v !== null && v !== undefined && !k.endsWith('_note') && k !== 'trend' && k !== 'detail_unit');
  if (entries.length === 0) return null;

  return (
    <div className="space-y-2 mt-2">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
        {entries.map(([key, value]) => {
          if (typeof value === 'object') return null;
          const label = key.replace(/_/g, ' ').replace(/pct /g, '% ').replace(/^(.)/, (c) => c.toUpperCase());
          const isGbp = unit === 'GBP' || unit === 'GBP/year' || unit === 'GBP/month';
          const isPct = detailUnit === '%' || String(key).includes('pct');
          const display = typeof value === 'number'
            ? isGbp
              ? '£' + value.toLocaleString('en-GB', { maximumFractionDigits: 0 })
              : isPct
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
    </div>
  );
}
