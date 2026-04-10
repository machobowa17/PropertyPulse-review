import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import { MapPin, ArrowLeft, ChevronDown, SearchX, FileDown, Leaf, Map, Heart, BellRing } from 'lucide-react';

/** True when viewport is >= 1024px (Tailwind `lg` breakpoint) */
function useIsDesktop() {
  const [isDesktop, setIsDesktop] = useState(
    typeof window !== 'undefined' ? window.matchMedia('(min-width: 1024px)').matches : true,
  );
  useEffect(() => {
    const mql = window.matchMedia('(min-width: 1024px)');
    const handler = (e: MediaQueryListEvent) => setIsDesktop(e.matches);
    mql.addEventListener('change', handler);
    return () => mql.removeEventListener('change', handler);
  }, []);
  return isDesktop;
}
import { resolveSearch, fetchAreaTab, fetchBoundary, fetchPriceHistory, fetchAqHistory, fetchComparable, fetchMapPois, fetchPriceByType, fetchChoropleth } from '../api/client';
import type { TabName, PersonaId } from '../types';
import PersonaSelector from '../components/PersonaSelector';
import DecisionModeSelector, { type DecisionMode } from '../components/DecisionModeSelector';
import SearchBox from '../components/SearchBox';
import TabBar from '../components/TabBar';
import MetricCard from '../components/MetricCard';
import MortgageCalculator from '../components/MortgageCalculator';
import RentalYieldCalculator from '../components/RentalYieldCalculator';
import AirQualityChart from '../components/AirQualityChart';
import ComparableAreas from '../components/ComparableAreas';
import CommuteEstimator from '../components/CommuteEstimator';
import PersonaScoreCard from '../components/PersonaScoreCard';
import MapView from '../components/MapView';
import MapLayerControl from '../components/MapLayerControl';
import UsefulResourcesPanel from '../components/UsefulResourcesPanel';
import CollapsibleSection from '../components/CollapsibleSection';
import SkeletonCard, { ResolvingSkeleton } from '../components/SkeletonCard';
import { TAB_EXPLAINERS } from '../utils/tabExplainers';
import { buildSectionSummary } from '../utils/sectionSummary';
import { saveArea, removeSavedArea, isAreaSaved, buildSavedAreaId, type SavedAreaCollection } from '../utils/savedAreas';

/* ── Map layer priority per tab ── */
const MAP_LAYER_PRIORITY: Record<string, string[]> = {
  'Property & Market': ['sold_price', 'choropleth_avg_price', 'choropleth_price_per_sqft', 'choropleth_median_rent', 'choropleth_epc_score'],
  'Lifestyle & Connectivity': [
    'station', 'amenity', 'park', 'sports_recreation', 'ev_charger',
    'choropleth_broadband', 'choropleth_full_fibre', 'choropleth_superfast_broadband',
    'choropleth_mobile_coverage', 'choropleth_mobile_4g_indoor', 'choropleth_mobile_5g_outdoor',
  ],
  'Environment & Safety': ['flood_zone', 'choropleth_air_quality_no2', 'choropleth_air_quality_pm25'],
  'Community & Education': [
    'school', 'nhs_facility',
    'choropleth_population_density', 'choropleth_median_age', 'choropleth_household_composition',
    'choropleth_good_health', 'choropleth_economically_active', 'choropleth_degree_educated',
    'choropleth_no_car', 'choropleth_born_abroad', 'choropleth_wfh',
    'choropleth_housing_tenure', 'choropleth_housing_type', 'choropleth_household_size',
    'choropleth_deprivation', 'choropleth_deprivation_income', 'choropleth_deprivation_employment',
    'choropleth_deprivation_education', 'choropleth_deprivation_health', 'choropleth_deprivation_crime',
    'choropleth_deprivation_barriers', 'choropleth_deprivation_living_environment',
  ],
  'Local Governance': ['choropleth_council_tax', 'choropleth_median_earnings'],
};

/* ── Metric → map layer bindings (metric-follow system) ── */
type MetricMapBinding = {
  mode: 'layer' | 'context';
  layerKey?: string;
  label: string;
  reason: string;
};

const METRIC_MAP_BINDINGS: Record<string, MetricMapBinding> = {
  avg_price: { mode: 'layer', layerKey: 'choropleth_avg_price', label: 'Average price heatmap', reason: 'This metric has nearby spatial evidence, so the map follows it with the average-price heatmap.' },
  median_price: { mode: 'layer', layerKey: 'choropleth_avg_price', label: 'Average price heatmap', reason: 'Median price is interpreted against the surrounding local price pattern.' },
  transaction_volume: { mode: 'layer', layerKey: 'sold_price', label: 'Recent sold-price points', reason: 'Transaction volume is best read against nearby sold-price evidence.' },
  price_per_sqft: { mode: 'layer', layerKey: 'choropleth_price_per_sqft', label: 'Price per sqft heatmap', reason: 'This metric has a dedicated spatial layer.' },
  affordability: { mode: 'layer', layerKey: 'choropleth_avg_price', label: 'Average price heatmap', reason: 'Price geography is the most honest spatial context for affordability.' },
  price_trend_yoy: { mode: 'layer', layerKey: 'sold_price', label: 'Recent sold-price points', reason: 'Price trend is grounded in transaction evidence.' },
  new_build_proportion: { mode: 'layer', layerKey: 'sold_price', label: 'Recent sold-price points', reason: 'New-build share is best interpreted against recent transaction evidence.' },
  epc_energy_score: { mode: 'layer', layerKey: 'choropleth_epc_score', label: 'EPC score heatmap', reason: 'This metric has a dedicated spatial layer.' },
  epc_rating_c_plus: { mode: 'layer', layerKey: 'choropleth_epc_score', label: 'EPC score heatmap', reason: 'Best read with nearby EPC performance.' },
  epc_rating: { mode: 'layer', layerKey: 'choropleth_epc_score', label: 'EPC score heatmap', reason: 'Best read with nearby EPC performance.' },
  nearest_station: { mode: 'layer', layerKey: 'station', label: 'Nearby stations', reason: 'This metric has direct spatial evidence.' },
  ptal: { mode: 'layer', layerKey: 'station', label: 'Nearby stations', reason: 'Nearby stations are the clearest honest spatial evidence.' },
  ptal_score: { mode: 'layer', layerKey: 'station', label: 'Nearby stations', reason: 'Nearby stations are the clearest honest spatial evidence.' },
  commute_distance: { mode: 'layer', layerKey: 'station', label: 'Nearby stations', reason: 'Commute distance is interpreted through nearby transport access.' },
  cycling: { mode: 'layer', layerKey: 'station', label: 'Nearby stations', reason: 'No dedicated route layer yet; map uses transport nodes as best current anchor.' },
  ev_chargers: { mode: 'layer', layerKey: 'ev_charger', label: 'Nearby EV chargers', reason: 'This metric has direct spatial evidence.' },
  no_car: { mode: 'layer', layerKey: 'choropleth_no_car', label: 'No-car households heatmap', reason: 'LSOA-level census evidence available.' },
  flood_risk: { mode: 'layer', layerKey: 'flood_zone', label: 'Flood-risk zones', reason: 'This metric has direct spatial evidence.' },
  primary_schools: { mode: 'layer', layerKey: 'school', label: 'Nearby schools', reason: 'This metric has direct spatial evidence.' },
  primary_school_quality: { mode: 'layer', layerKey: 'school', label: 'Nearby schools', reason: 'School quality is best interpreted alongside the nearby school footprint.' },
  secondary_schools: { mode: 'layer', layerKey: 'school', label: 'Nearby schools', reason: 'This metric has direct spatial evidence.' },
  secondary_school_quality: { mode: 'layer', layerKey: 'school', label: 'Nearby schools', reason: 'School quality is best interpreted alongside the nearby school footprint.' },
  freehold_leasehold: { mode: 'context', label: 'Local analysis boundary', reason: 'Tenure mix does not yet have a direct spatial layer.' },
  median_rent: { mode: 'layer', layerKey: 'choropleth_median_rent', label: 'Median rent heatmap', reason: 'Honest local-authority proxy layer available.' },
  gross_yield: { mode: 'context', label: 'Local analysis boundary', reason: 'Computed from numeric evidence rather than a rent surface.' },
  investment_grade: { mode: 'context', label: 'Local analysis boundary', reason: 'Composite decision metric without a standalone spatial layer.' },
  amenities_15min: { mode: 'layer', layerKey: 'amenity', label: 'Nearby amenities', reason: 'Mapped place evidence available.' },
  fifteen_min_score: { mode: 'layer', layerKey: 'amenity', label: 'Nearby amenities', reason: 'Grounded in mapped amenity evidence.' },
  mobile_coverage: { mode: 'layer', layerKey: 'choropleth_mobile_coverage', label: '4G outdoor coverage heatmap', reason: 'Postcode-level spatial evidence available.' },
  mobile_4g_indoor: { mode: 'layer', layerKey: 'choropleth_mobile_4g_indoor', label: '4G indoor coverage heatmap', reason: 'Postcode-level spatial evidence available.' },
  mobile_5g_outdoor: { mode: 'layer', layerKey: 'choropleth_mobile_5g_outdoor', label: '5G outdoor coverage heatmap', reason: 'Postcode-level spatial evidence available.' },
  broadband: { mode: 'layer', layerKey: 'choropleth_broadband', label: 'Gigabit broadband heatmap', reason: 'Postcode-level spatial evidence available.' },
  full_fibre: { mode: 'layer', layerKey: 'choropleth_full_fibre', label: 'Full fibre heatmap', reason: 'Postcode-level spatial evidence available.' },
  superfast_broadband: { mode: 'layer', layerKey: 'choropleth_superfast_broadband', label: 'Superfast broadband heatmap', reason: 'Postcode-level spatial evidence available.' },
  air_quality_no2: { mode: 'layer', layerKey: 'choropleth_air_quality_no2', label: 'NO2 heatmap', reason: 'DEFRA air-quality grid cells aggregated to LSOAs.' },
  air_quality_pm25: { mode: 'layer', layerKey: 'choropleth_air_quality_pm25', label: 'PM2.5 heatmap', reason: 'DEFRA air-quality grid cells aggregated to LSOAs.' },
  noise: { mode: 'context', label: 'Local analysis boundary', reason: 'Currently numeric-only.' },
  nearest_park: { mode: 'layer', layerKey: 'park', label: 'Parks and green spaces', reason: 'Mapped green-space evidence available.' },
  green_cover: { mode: 'layer', layerKey: 'park', label: 'Parks and green spaces', reason: 'Anchored to mapped green-space sites.' },
  green_spaces: { mode: 'layer', layerKey: 'park', label: 'Parks and green spaces', reason: 'Mapped polygon evidence available.' },
  parks_1km: { mode: 'layer', layerKey: 'park', label: 'Parks and green spaces', reason: 'Mapped park locations available.' },
  sports_recreation: { mode: 'layer', layerKey: 'sports_recreation', label: 'Sports and recreation places', reason: 'Mapped place evidence available.' },
  nhs_facilities: { mode: 'layer', layerKey: 'nhs_facility', label: 'Nearby NHS facilities', reason: 'Mapped place evidence available.' },
  demographics_overview: { mode: 'layer', layerKey: 'choropleth_population_density', label: 'Population density heatmap', reason: 'Defaults to the broadest demographic surface.' },
  population_density: { mode: 'layer', layerKey: 'choropleth_population_density', label: 'Population density heatmap', reason: 'Direct LSOA-level census evidence.' },
  median_age: { mode: 'layer', layerKey: 'choropleth_median_age', label: 'Median age heatmap', reason: 'Direct LSOA-level census evidence.' },
  household_composition: { mode: 'layer', layerKey: 'choropleth_household_composition', label: 'Household composition heatmap', reason: 'LSOA-level census evidence.' },
  housing_tenure: { mode: 'layer', layerKey: 'choropleth_housing_tenure', label: 'Housing tenure heatmap', reason: 'LSOA-level census evidence.' },
  housing_type: { mode: 'layer', layerKey: 'choropleth_housing_type', label: 'Housing stock heatmap', reason: 'LSOA-level census evidence.' },
  deprivation: { mode: 'layer', layerKey: 'choropleth_deprivation', label: 'Deprivation heatmap', reason: 'LSOA-level spatial evidence.' },
  deprivation_income: { mode: 'layer', layerKey: 'choropleth_deprivation_income', label: 'Income deprivation heatmap', reason: 'LSOA-level spatial evidence.' },
  deprivation_employment: { mode: 'layer', layerKey: 'choropleth_deprivation_employment', label: 'Employment deprivation heatmap', reason: 'LSOA-level spatial evidence.' },
  deprivation_education: { mode: 'layer', layerKey: 'choropleth_deprivation_education', label: 'Education deprivation heatmap', reason: 'LSOA-level spatial evidence.' },
  deprivation_health: { mode: 'layer', layerKey: 'choropleth_deprivation_health', label: 'Health deprivation heatmap', reason: 'LSOA-level spatial evidence.' },
  deprivation_crime: { mode: 'layer', layerKey: 'choropleth_deprivation_crime', label: 'Crime deprivation heatmap', reason: 'LSOA-level spatial evidence.' },
  deprivation_barriers: { mode: 'layer', layerKey: 'choropleth_deprivation_barriers', label: 'Housing and services barriers heatmap', reason: 'LSOA-level spatial evidence.' },
  deprivation_living_environment: { mode: 'layer', layerKey: 'choropleth_deprivation_living_environment', label: 'Living environment heatmap', reason: 'LSOA-level spatial evidence.' },
  good_health: { mode: 'layer', layerKey: 'choropleth_good_health', label: 'Good health heatmap', reason: 'Direct LSOA-level census evidence.' },
  economically_active: { mode: 'layer', layerKey: 'choropleth_economically_active', label: 'Economic activity heatmap', reason: 'Direct LSOA-level census evidence.' },
  degree_educated: { mode: 'layer', layerKey: 'choropleth_degree_educated', label: 'Degree education heatmap', reason: 'Direct LSOA-level census evidence.' },
  born_abroad: { mode: 'layer', layerKey: 'choropleth_born_abroad', label: 'Born abroad heatmap', reason: 'Direct LSOA-level census evidence.' },
  wfh: { mode: 'layer', layerKey: 'choropleth_wfh', label: 'Works from home heatmap', reason: 'Direct LSOA-level census evidence.' },
  household_size: { mode: 'layer', layerKey: 'choropleth_household_size', label: 'Household size heatmap', reason: 'LSOA-level census evidence.' },
  council_tax: { mode: 'layer', layerKey: 'choropleth_council_tax', label: 'Council tax heatmap', reason: 'Honest local-authority proxy layer available.' },
  local_authority: { mode: 'context', label: 'Local analysis boundary', reason: 'Already reflected by the search boundary.' },
  controlling_party: { mode: 'context', label: 'Local analysis boundary', reason: 'Governance metric without a direct map layer.' },
  water_company: { mode: 'context', label: 'Local analysis boundary', reason: 'Service-region metric without a direct rendered layer.' },
  financial_health: { mode: 'context', label: 'Local analysis boundary', reason: 'Aggregate governance metric.' },
  median_earnings: { mode: 'layer', layerKey: 'choropleth_median_earnings', label: 'Median earnings heatmap', reason: 'Honest local-authority proxy layer available.' },
};

const METRIC_TO_MAP_LAYER: Record<string, string> = Object.entries(METRIC_MAP_BINDINGS).reduce((acc, [metricId, binding]) => {
  if (binding.mode === 'layer' && binding.layerKey) {
    acc[metricId] = binding.layerKey;
  }
  return acc;
}, {} as Record<string, string>);

const ALL_CHOROPLETH_KEYS = [
  'choropleth_avg_price', 'choropleth_price_per_sqft', 'choropleth_median_rent', 'choropleth_epc_score',
  'choropleth_population_density', 'choropleth_median_age', 'choropleth_household_composition',
  'choropleth_good_health', 'choropleth_economically_active', 'choropleth_degree_educated',
  'choropleth_no_car', 'choropleth_born_abroad', 'choropleth_wfh',
  'choropleth_housing_tenure', 'choropleth_housing_type', 'choropleth_household_size',
  'choropleth_deprivation', 'choropleth_deprivation_income', 'choropleth_deprivation_employment',
  'choropleth_deprivation_education', 'choropleth_deprivation_health', 'choropleth_deprivation_crime',
  'choropleth_deprivation_barriers', 'choropleth_deprivation_living_environment',
  'choropleth_broadband', 'choropleth_full_fibre', 'choropleth_superfast_broadband',
  'choropleth_mobile_coverage', 'choropleth_mobile_4g_indoor', 'choropleth_mobile_5g_outdoor',
  'choropleth_air_quality_no2', 'choropleth_air_quality_pm25',
  'choropleth_council_tax', 'choropleth_median_earnings',
];

const LSOA_SUFFIX = 'LSOAs are small geographic units for statistical analysis in England and Wales, designed by the Office for National Statistics (ONS) to have 1,000–3,000 residents or 400–1,200 households. As of 2021, there are 33,755 LSOAs in England and 1,917 in Wales. The results below use LSOA-level data at their lowest level of granularity.';

function lsoaList(codes: string[], count: number): string {
  if (count === 0) return '';
  const label = count === 1 ? 'Lower Layer Super Output Area (LSOA)' : 'Lower Layer Super Output Areas (LSOAs)';
  if (codes.length > 0) return `${count} ${label}: ${codes.join(', ')}`;
  return `${count} ${label}`;
}

function LsoaContextBlurb({ resolved, areaName }: { resolved: any; areaName: string }) {
  const type = resolved?.type;
  const rc = resolved?.resolved_codes;
  const count: number = resolved?.lsoa_count ?? 0;
  const lsoaCodes: string[] = resolved?.lsoa_codes ?? [];

  if (!type || count === 0) return null;

  let intro = '';
  if (type === 'postcode' && rc?.lsoa && rc.lsoa !== '_') {
    intro = `${areaName} is part of Lower Layer Super Output Area (LSOA) ${rc.lsoa}.`;
  } else if (type === 'postcode_district') {
    intro = `${areaName} postcode district spans ${lsoaList(lsoaCodes, count)}.`;
  } else if (type === 'ward') {
    intro = `${areaName} ward spans ${lsoaList(lsoaCodes, count)}.`;
  } else if (type === 'borough') {
    intro = `${areaName} is a London Borough spanning ${lsoaList(lsoaCodes, count)}.`;
  } else if (type === 'district') {
    intro = `${areaName} is a Local Authority District spanning ${lsoaList(lsoaCodes, count)}.`;
  } else if (type === 'county') {
    intro = `${areaName} is a county spanning ${lsoaList(lsoaCodes, count)} across its constituent Local Authority Districts.`;
  } else if (type === 'place') {
    intro = `${areaName} is mapped to ${lsoaList(lsoaCodes, count)}.`;
  } else {
    return null;
  }

  return (
    <p className="mt-2 text-[11px] text-white/40 leading-relaxed">
      <span className="text-white/60">{intro}</span>{' '}{LSOA_SUFFIX}
    </p>
  );
}

export default function Results() {
  const [params, setParams] = useSearchParams();
  const q = params.get('q') || '';
  const rawMode = params.get('mode');
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<TabName>('Property & Market');
  const [persona, setPersona] = useState<PersonaId>('family');
  const [decisionMode, setDecisionMode] = useState<DecisionMode>(
    rawMode === 'rent' || rawMode === 'invest' ? rawMode : 'buy',
  );
  const handleDecisionModeChange = (mode: DecisionMode) => {
    setDecisionMode(mode);
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('mode', mode);
      return next;
    }, { replace: true });
  };
  const [savedCollections, setSavedCollections] = useState<Record<SavedAreaCollection, boolean>>({
    shortlist: false,
    watchlist: false,
  });
  const [showMap, setShowMap] = useState(true);
  const [visibleLayers, setVisibleLayers] = useState<Record<string, boolean>>({});
  const [activeChoropleth, setActiveChoropleth] = useState<string | null>(null);
  const [mapFocusMode, setMapFocusMode] = useState<'section' | 'metric' | 'manual' | 'metric-fallback'>('section');
  const [activeMapMetricId, setActiveMapMetricId] = useState<string | null>(null);
  const isDesktop = useIsDesktop();
  const mapViewportRef = useRef<{ center: [number, number]; zoom: number } | null>(null);
  const metricElementRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const activeScrollMetricIdRef = useRef<string | null>(null);
  const handleViewportChange = useCallback((vp: { center: [number, number]; zoom: number }) => {
    mapViewportRef.current = vp;
  }, []);

  // Reset saved viewport + clear choropleth when search query changes (new location)
  useEffect(() => {
    mapViewportRef.current = null;
    setActiveChoropleth(null);
    setMapFocusMode('section');
    setActiveMapMetricId(null);
    setVisibleLayers((prev) => {
      const next = { ...prev };
      for (const ck of ALL_CHOROPLETH_KEYS) next[ck] = false;
      return next;
    });
  }, [q]);

  // Reset focus mode and clear choropleth on tab change
  useEffect(() => {
    setMapFocusMode('section');
    setActiveMapMetricId(null);
    activeScrollMetricIdRef.current = null;
    setActiveChoropleth(null);
    setVisibleLayers((prev) => {
      const next = { ...prev };
      for (const ck of ALL_CHOROPLETH_KEYS) next[ck] = false;
      return next;
    });
  }, [activeTab]);

  const CHOROPLETH_KEYS = ALL_CHOROPLETH_KEYS;

  const handleLayerToggle = (key: string) => {
    setMapFocusMode('manual');
    setActiveMapMetricId(null);
    if (CHOROPLETH_KEYS.includes(key)) {
      // Mutual exclusion: toggle off if already active, otherwise switch
      setActiveChoropleth((prev) => prev === key ? null : key);
      setVisibleLayers((prev) => {
        const next = { ...prev };
        for (const ck of CHOROPLETH_KEYS) next[ck] = ck === key ? !prev[key] : false;
        return next;
      });
    } else {
      setVisibleLayers((prev) => ({ ...prev, [key]: prev[key] !== false ? false : true }));
    }
  };

  // Resolve
  const { data: resolved, isLoading: resolving, error: resolveError } = useQuery({
    queryKey: ['resolve', q],
    queryFn: () => resolveSearch(q),
    enabled: !!q,
  });

  const codes = resolved?.resolved_codes;
  const sessionKey = resolved?.session_key;
  const lsoa = codes?.lsoa || '_';
  const parentName = codes?.parent || 'England';
  const areaName = resolved?.type === 'postcode' || resolved?.type === 'postcode_district' ? q.toUpperCase() : q;

  // Refresh saved-area state when area or decision mode changes
  useEffect(() => {
    if (!areaName) return;
    setSavedCollections({
      shortlist: isAreaSaved(areaName, 'shortlist', decisionMode),
      watchlist: isAreaSaved(areaName, 'watchlist', decisionMode),
    });
  }, [areaName, decisionMode]);

  const toggleSave = (collection: SavedAreaCollection) => {
    if (!areaName) return;
    if (savedCollections[collection]) {
      removeSavedArea(buildSavedAreaId(areaName, collection, decisionMode));
    } else {
      saveArea({
        collection,
        query: q,
        areaName,
        parentName,
        sessionKey: sessionKey ?? null,
        decisionMode,
        persona,
        notes: [],
      });
    }
    setSavedCollections((prev) => ({ ...prev, [collection]: !prev[collection] }));
  };

  // Pre-fetch all tabs in the background as soon as sessionKey is available.
  // The active tab is already fetched by the main useQuery below; this primes
  // the React Query cache for the other 4 tabs so switching is instant.
  const ALL_TABS: TabName[] = ['Property & Market', 'Lifestyle & Connectivity', 'Environment & Safety', 'Community & Education', 'Local Governance'];
  useEffect(() => {
    if (!sessionKey) return;
    for (const tab of ALL_TABS) {
      if (tab === activeTab) continue; // already fetched by the main query
      queryClient.prefetchQuery({
        queryKey: ['area', sessionKey, tab],
        queryFn: () => fetchAreaTab(sessionKey, tab),
        staleTime: 5 * 60 * 1000,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionKey]);

  // Fetch boundary (single consolidated endpoint)
  const { data: boundaryData } = useQuery({
    queryKey: ['boundary', sessionKey],
    queryFn: () => fetchBoundary(sessionKey!),
    enabled: !!sessionKey,
  });

  // For ward_lsoa searches, boundary endpoint returns a FeatureCollection with both ward + LSOA features.
  // For other search types, it returns a single Feature (or FeatureCollection).
  // MapView accepts boundary (ward/area) and lsoaBoundary (LSOA overlay for postcode searches).
  const effectiveBoundary: GeoJSON.Feature | null = boundaryData
    ? (boundaryData.type === 'FeatureCollection'
        ? ((boundaryData as GeoJSON.FeatureCollection).features.find(
            (f: GeoJSON.Feature) => f.properties?.layer !== 'lsoa'
          ) ?? (boundaryData as GeoJSON.FeatureCollection).features[0] ?? null)
        : (boundaryData as GeoJSON.Feature))
    : null;
  const effectiveLsoaBoundary = (
    boundaryData &&
    'type' in boundaryData &&
    boundaryData.type === 'FeatureCollection' &&
    'features' in boundaryData &&
    (boundaryData as GeoJSON.FeatureCollection).features.length > 1
  ) ? (boundaryData as GeoJSON.FeatureCollection).features.find(
    (f: GeoJSON.Feature) => f.properties?.layer === 'lsoa'
  ) ?? null : null;

  // Fetch tab data
  const { data: tabData, isLoading: tabLoading } = useQuery({
    queryKey: ['area', sessionKey, activeTab],
    queryFn: () => fetchAreaTab(sessionKey!, activeTab),
    enabled: !!sessionKey,
  });

  // Fetch price history for chart (Property tab)
  const { data: priceHistory } = useQuery({
    queryKey: ['priceHistory', sessionKey],
    queryFn: () => fetchPriceHistory(sessionKey!),
    enabled: !!sessionKey && activeTab === 'Property & Market',
  });

  // Fetch AQ history for chart (Environment tab) — only when that tab is active
  const { data: aqHistory } = useQuery({
    queryKey: ['aqHistory', sessionKey],
    queryFn: () => fetchAqHistory(sessionKey!),
    enabled: !!sessionKey && activeTab === 'Environment & Safety',
  });

  // Fetch price breakdown by property type
  const { data: priceByType } = useQuery({
    queryKey: ['priceByType', sessionKey],
    queryFn: () => fetchPriceByType(sessionKey!),
    enabled: !!sessionKey && activeTab === 'Property & Market',
  });

  // Fetch comparable areas
  const { data: comparable } = useQuery({
    queryKey: ['comparable', sessionKey],
    queryFn: () => fetchComparable(sessionKey!),
    enabled: !!sessionKey,
  });

  // Fetch map POIs based on active tab
  const { data: mapPois, isFetching: mapPoisLoading } = useQuery({
    queryKey: ['mapPois', sessionKey, activeTab],
    queryFn: () => fetchMapPois(sessionKey!, activeTab),
    enabled: !!sessionKey && (activeTab === 'Property & Market' || activeTab === 'Community & Education' || activeTab === 'Lifestyle & Connectivity' || activeTab === 'Environment & Safety'),
  });

  // Lazy-fetch choropleth data only when a heatmap layer is active
  const choroplethLayer = activeChoropleth?.replace('choropleth_', '') || null;
  const { data: choroplethData } = useQuery({
    queryKey: ['choropleth', sessionKey, choroplethLayer],
    queryFn: () => fetchChoropleth(sessionKey!, choroplethLayer!),
    enabled: !!sessionKey && !!choroplethLayer,
  });

  /* ── Metric-follow system ── */
  const allMetrics = tabData?.metrics ?? [];

  const allMetricsById = useMemo(
    () => new globalThis.Map(allMetrics.map((m) => [m.id, m])),
    [allMetrics],
  );

  const applyMapFocusLayer = useCallback((layerKey: string | null) => {
    setActiveChoropleth(ALL_CHOROPLETH_KEYS.includes(layerKey || '') ? layerKey : null);
    setVisibleLayers((prev) => {
      const next = { ...prev };
      const priorityKeys = MAP_LAYER_PRIORITY[activeTab] || [];
      priorityKeys.forEach((key) => { next[key] = layerKey ? key === layerKey : false; });
      ALL_CHOROPLETH_KEYS.forEach((key) => { next[key] = key === layerKey; });
      next.ward_boundary = true;
      next.lsoa_boundary = true;
      return next;
    });
  }, [activeTab]);

  const handleMetricMapFocus = useCallback((metricId: string, source: 'click' | 'scroll' = 'click') => {
    const binding = METRIC_MAP_BINDINGS[metricId];
    if (!binding) return;
    setActiveMapMetricId(metricId);
    if (binding.mode === 'layer' && binding.layerKey) {
      setMapFocusMode('metric');
      applyMapFocusLayer(binding.layerKey);
    } else {
      setMapFocusMode('metric-fallback');
      applyMapFocusLayer(null);
    }
    if (!isDesktop && source === 'click') setShowMap(true);
  }, [applyMapFocusLayer, isDesktop]);

  const focusMetricById = useCallback((metricId: string, source: 'click' | 'scroll' = 'click') => {
    const metric = allMetricsById.get(metricId);
    if (!metric) return;
    handleMetricMapFocus(metricId, source);
  }, [allMetricsById, handleMetricMapFocus]);

  const setMetricElementRef = useCallback((metricId: string, node: HTMLDivElement | null) => {
    metricElementRefs.current[metricId] = node;
  }, []);

  // Scroll-based metric follow (desktop only)
  const displayedMetrics = allMetrics;
  useEffect(() => {
    if (!isDesktop || !showMap || mapFocusMode === 'manual' || displayedMetrics.length === 0) return;
    let frame = 0;
    const updateActiveMetricFromScroll = () => {
      frame = 0;
      const anchor = Math.max(160, window.innerHeight * 0.35);
      const candidates = displayedMetrics
        .map((m) => {
          const el = metricElementRefs.current[m.id];
          if (!el) return null;
          const rect = el.getBoundingClientRect();
          if (rect.bottom < 120 || rect.top > window.innerHeight * 0.82) return null;
          return { metricId: m.id, distance: Math.abs(rect.top - anchor), top: rect.top };
        })
        .filter((item): item is { metricId: string; distance: number; top: number } => item !== null)
        .sort((a, b) => a.distance - b.distance || a.top - b.top);
      const nextMetricId = candidates[0]?.metricId ?? null;
      if (!nextMetricId || nextMetricId === activeScrollMetricIdRef.current) return;
      activeScrollMetricIdRef.current = nextMetricId;
      focusMetricById(nextMetricId, 'scroll');
    };
    const requestUpdate = () => { if (frame) return; frame = window.requestAnimationFrame(updateActiveMetricFromScroll); };
    requestUpdate();
    window.addEventListener('scroll', requestUpdate, { passive: true });
    window.addEventListener('resize', requestUpdate);
    return () => {
      if (frame) window.cancelAnimationFrame(frame);
      window.removeEventListener('scroll', requestUpdate);
      window.removeEventListener('resize', requestUpdate);
    };
  }, [displayedMetrics, focusMetricById, isDesktop, mapFocusMode, showMap]);

  // Compute focus label/reason for MapLayerControl
  const activeFocusBinding = activeMapMetricId ? METRIC_MAP_BINDINGS[activeMapMetricId] : null;
  const focusLabel = activeFocusBinding?.label || null;
  const focusReason = activeFocusBinding?.reason || null;

  return (
    <div className="min-h-dvh flex flex-col bg-surface">
      {/* Skip to content (keyboard accessibility) */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-[100] focus:px-4 focus:py-2 focus:bg-brand-600 focus:text-white focus:rounded-xl focus:text-sm focus:font-semibold"
      >
        Skip to main content
      </a>

      {/* Header */}
      <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-md border-b border-divider/60">
        <div className="max-w-[1400px] mx-auto px-4 lg:px-6 py-2.5 flex items-center gap-3">
          <Link to="/" className="p-2 rounded-xl hover:bg-surface transition-colors" aria-label="Back to home">
            <ArrowLeft className="w-5 h-5 text-ink-muted" aria-hidden="true" />
          </Link>
          <Link to="/" className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-brand-500 flex items-center justify-center">
              <Leaf className="w-3.5 h-3.5 text-white" />
            </div>
            <span className="font-bold text-sm tracking-tight text-ink hidden sm:block">PropertyPulse</span>
          </Link>
          <div className="flex-1 max-w-md">
            <SearchBox size="sm" initialValue={q} />
          </div>
          <DecisionModeSelector current={decisionMode} onChange={handleDecisionModeChange} variant="dropdown" />
          <PersonaSelector current={persona} onChange={setPersona} />
          <Link
            to="/saved"
            className="p-2 rounded-xl hover:bg-surface transition-colors"
            aria-label="Saved areas"
            title="Saved areas"
          >
            <Heart className="w-5 h-5 text-ink-muted" aria-hidden="true" />
          </Link>
        </div>
      </header>

      {/* Resolve status */}
      {resolving && <ResolvingSkeleton />}

      {resolveError && (
        <div className="max-w-2xl mx-auto mt-16 p-6 rounded-2xl bg-signal-red-bg text-signal-red text-center">
          Could not resolve &ldquo;{q}&rdquo;. Try a valid UK postcode or place name.
        </div>
      )}

      {resolved?.error && (
        <div className="max-w-xl mx-auto mt-16 px-4">
          <div className="rounded-2xl bg-white p-8 text-center shadow-sm">
            <div className="w-12 h-12 rounded-2xl bg-surface flex items-center justify-center mx-auto mb-4">
              <SearchX className="w-6 h-6 text-ink-faint" />
            </div>
            <h2 className="text-lg font-bold text-ink mb-1">No results for &ldquo;{q}&rdquo;</h2>
            <p className="text-sm text-ink-muted mb-5">
              Check the spelling, or try a full postcode (e.g. SW1A 1AA) or a city name.
            </p>
            {resolved.suggestions && resolved.suggestions.length > 0 && (
              <>
                <p className="text-xs font-semibold text-ink-faint uppercase tracking-wide mb-3">Did you mean?</p>
                <div className="flex flex-wrap justify-center gap-2">
                  {resolved.suggestions.map((s) => (
                    <button
                      key={s.label}
                      onClick={() => window.location.href = `/results?q=${encodeURIComponent(s.label)}`}
                      className="group flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm bg-surface hover:bg-brand-50 hover:text-brand-700 transition-all cursor-pointer"
                    >
                      <MapPin className="w-3 h-3 text-ink-faint group-hover:text-brand-500 shrink-0" />
                      <span className="font-semibold text-ink group-hover:text-brand-700">{s.label}</span>
                      {s.area && <span className="text-ink-faint text-xs group-hover:text-brand-500">{s.area}</span>}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {codes && sessionKey && (
        <>
          {/* Area banner — hero strip */}
          <div className="bg-gradient-to-r from-brand-950 via-brand-900 to-brand-800 border-b border-brand-800/50">
            <div className="max-w-[1400px] mx-auto px-4 lg:px-6 py-5 lg:py-6">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                  <h1 className="text-2xl sm:text-3xl lg:text-4xl font-black tracking-tight text-white leading-tight">
                    {areaName}
                    {parentName && (
                      <span className="text-base sm:text-lg lg:text-xl font-medium text-white/50">, {parentName}</span>
                    )}
                  </h1>
                </div>
                <div className="flex items-center gap-2 self-start">
                  <button
                    type="button"
                    onClick={() => toggleSave('shortlist')}
                    aria-label={savedCollections.shortlist ? 'Remove from shortlist' : 'Save to shortlist'}
                    className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold active:scale-95 transition-all backdrop-blur-sm border self-start ${
                      savedCollections.shortlist
                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-400/30'
                        : 'bg-white/10 text-white hover:bg-white/15 border-white/10'
                    }`}
                  >
                    <Heart className={`w-4 h-4 ${savedCollections.shortlist ? 'fill-current' : ''}`} aria-hidden="true" />
                    {savedCollections.shortlist ? 'Shortlisted' : 'Shortlist'}
                  </button>
                  <button
                    type="button"
                    onClick={() => toggleSave('watchlist')}
                    aria-label={savedCollections.watchlist ? 'Remove from watchlist' : 'Save to watchlist'}
                    className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold active:scale-95 transition-all backdrop-blur-sm border self-start ${
                      savedCollections.watchlist
                        ? 'bg-sky-500/20 text-sky-300 border-sky-400/30'
                        : 'bg-white/10 text-white hover:bg-white/15 border-white/10'
                    }`}
                  >
                    <BellRing className={`w-4 h-4`} aria-hidden="true" />
                    {savedCollections.watchlist ? 'Watching' : 'Watch'}
                  </button>
                  <a
                    href={`/api/v1/report?session_key=${encodeURIComponent(sessionKey)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={`Download PDF report for ${areaName}`}
                    className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold bg-white/10 text-white hover:bg-white/15 active:scale-95 transition-all backdrop-blur-sm border border-white/10 self-start"
                  >
                    <FileDown className="w-4 h-4" aria-hidden="true" />
                    Download Report
                  </a>
                </div>
              </div>
              {resolved && <LsoaContextBlurb resolved={resolved} areaName={areaName} />}
            </div>
          </div>

          {/* Tabs — sticky below header */}
          <div className="sticky top-[53px] z-40 bg-white/95 backdrop-blur-md border-b border-divider/60">
            <div className="max-w-[1400px] mx-auto px-4 lg:px-6">
              <TabBar active={activeTab} onChange={setActiveTab} />
            </div>
          </div>

          {/* Main layout: content + map side panel */}
          <div className="max-w-[1400px] mx-auto w-full flex-1 flex flex-col lg:flex-row">
            {/* Left: metrics */}
            <main id="main-content" className="flex-1 min-w-0 px-4 lg:px-6 py-6">
              {/* Map toggle (mobile only) */}
              {!isDesktop && (
                <div className="mb-4">
                  <button
                    onClick={() => setShowMap(!showMap)}
                    aria-label={showMap ? 'Hide map' : 'Show map'}
                    aria-expanded={showMap}
                    className="flex items-center gap-2 text-sm text-brand-600 font-medium"
                  >
                    <Map className="w-4 h-4" aria-hidden="true" />
                    {showMap ? 'Hide Map' : 'View Map'}
                    <ChevronDown className={`w-4 h-4 transition-transform ${showMap ? 'rotate-180' : ''}`} aria-hidden="true" />
                  </button>
                </div>
              )}

              {/* Mobile map — only mounted on mobile viewports */}
              <AnimatePresence>
                {!isDesktop && showMap && resolved?.coordinates?.lat && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 280, opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.3 }}
                    className="overflow-hidden mb-4"
                  >
                    <div className="rounded-2xl overflow-hidden shadow-sm h-[280px] relative">
                      <MapView lat={resolved.coordinates.lat} lon={resolved.coordinates.lon!} boundary={effectiveBoundary} lsoaBoundary={effectiveLsoaBoundary} pois={mapPois} activeTab={activeTab} visibleLayers={visibleLayers} searchLsoa={lsoa !== '_' ? lsoa : undefined} initialViewport={mapViewportRef.current} onViewportChange={handleViewportChange} choroplethData={activeChoropleth ? choroplethData : null} />
                      <MapLayerControl activeTab={activeTab} visibleLayers={visibleLayers} onToggle={handleLayerToggle} soldPricesSince={(mapPois as any)?.sold_prices_since} focusMode={mapFocusMode} focusLabel={focusLabel} focusReason={focusReason} />
                      {mapPoisLoading && (
                        <div className="absolute inset-0 z-[5] flex items-center justify-center bg-white/20 backdrop-blur-[1px] rounded-2xl pointer-events-none">
                          <div className="px-3 py-1.5 rounded-full bg-white/90 text-xs font-medium text-ink-muted shadow-sm">Loading…</div>
                        </div>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {tabLoading ? (
                <SkeletonCard count={8} />
              ) : (
                <motion.div
                  key={activeTab}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25 }}
                  className="grid gap-2.5"
                >
                  {/* Tab explainer bar */}
                  {TAB_EXPLAINERS[activeTab] && (
                    <div className="rounded-xl bg-brand-50/50 border border-brand-100/60 px-4 py-3">
                      <p className="text-xs font-semibold text-brand-700">{TAB_EXPLAINERS[activeTab].decision}</p>
                      <p className="text-[11px] text-brand-600/70 mt-0.5">{TAB_EXPLAINERS[activeTab].summary}</p>
                    </div>
                  )}

                  {/* Section summary chip */}
                  {tabData?.metrics && tabData.metrics.length > 0 && (() => {
                    const summary = buildSectionSummary(tabData.metrics, parentName);
                    return summary.comparableCount > 0 ? (
                      <div className="flex items-center gap-2 text-[11px] text-ink-muted">
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-surface border border-divider/60 font-medium">
                          {summary.headline}
                        </span>
                        <span className="text-ink-faint">{summary.totalCount} metrics total</span>
                      </div>
                    ) : null;
                  })()}

                  {/* Persona score card */}
                  {tabData?.metrics && tabData.metrics.length > 0 && (
                    <PersonaScoreCard metrics={tabData.metrics} persona={persona} />
                  )}
                  {/* Desktop table header */}
                  {tabData?.metrics && tabData.metrics.length > 0 && (
                    <div className="hidden lg:grid lg:grid-cols-[2fr_1fr_1fr_1fr_1fr_28px] lg:gap-4 lg:px-5 lg:py-2 lg:text-[11px] lg:font-semibold lg:uppercase lg:tracking-wider lg:text-ink-faint">
                      <span>Metric</span>
                      <span>Local</span>
                      <span>{parentName}</span>
                      <span>So What</span>
                      <span>Watch Out</span>
                      <span />
                    </div>
                  )}
                  {tabData?.metrics.map((m) => (
                    <div key={m.id} id={`metric-${m.id}`} ref={(node) => setMetricElementRef(m.id, node)}>
                      <MetricCard
                        metric={m}
                        persona={persona}
                        parentName={parentName}
                        priceByTypeData={(m.id === 'avg_price' || m.id === 'median_price' || m.id === 'price_per_sqft') ? (priceByType ?? undefined) : undefined}
                        priceHistoryData={(m.id === 'avg_price' || m.id === 'median_price' || m.id === 'price_per_sqft') ? (priceHistory ?? undefined) : undefined}
                        areaName={(m.id === 'avg_price' || m.id === 'median_price' || m.id === 'price_per_sqft') ? areaName : undefined}
                        sessionKey={m.id === 'transaction_volume' ? sessionKey : undefined}
                      />
                    </div>
                  ))}
                  {/* Interactive tools for Property tab */}
                  {activeTab === 'Property & Market' && tabData?.metrics && tabData.metrics.length > 0 && (() => {
                    const medianPrice = tabData.metrics.find(m => m.id === 'median_price')?.local_value as number | undefined;
                    const medianEarnings = tabData.metrics.find(m => m.id === 'median_earnings')?.local_value as number | undefined;
                    const medianRent = tabData.metrics.find(m => m.id === 'median_rent')?.local_value as number | undefined;
                    const avgPrice = tabData.metrics.find(m => m.id === 'avg_price')?.local_value as number | undefined;
                    return (
                      <CollapsibleSection title="Property Calculators">
                        <div className="grid gap-3 sm:grid-cols-2 mt-3">
                          <MortgageCalculator
                            defaultPrice={medianPrice ? Math.round(medianPrice) : undefined}
                            medianEarnings={medianEarnings ? Math.round(medianEarnings) : undefined}
                          />
                          <RentalYieldCalculator
                            defaultPrice={avgPrice ? Math.round(avgPrice) : undefined}
                            defaultRent={medianRent ? Math.round(medianRent) : undefined}
                          />
                        </div>
                      </CollapsibleSection>
                    );
                  })()}
                  {/* Comparable areas */}
                  {activeTab === 'Property & Market' && comparable && comparable.comparable.length > 0 && (
                    <CollapsibleSection title="Comparable Areas">
                      <ComparableAreas target={comparable.target} comparable={comparable.comparable} />
                    </CollapsibleSection>
                  )}
                  {activeTab === 'Property & Market' && comparable?.unsupported_scope && (
                    <CollapsibleSection title="Comparable Areas">
                      <div className="px-3 py-4 text-center">
                        <p className="text-sm text-ink-muted">{comparable.reason || 'Comparable areas require a single local authority. Try a specific borough.'}</p>
                      </div>
                    </CollapsibleSection>
                  )}
                  {/* Commute estimator (Lifestyle tab) */}
                  {activeTab === 'Lifestyle & Connectivity' && resolved?.coordinates?.lat && (
                    <CollapsibleSection title="Commute Estimator">
                      <CommuteEstimator
                        sessionKey={sessionKey}
                        originLabel={areaName}
                      />
                    </CollapsibleSection>
                  )}
                  {/* Air quality trend chart */}
                  {activeTab === 'Environment & Safety' && aqHistory && aqHistory.local.length > 1 && (
                    <CollapsibleSection title="Air Quality Trend">
                      <AirQualityChart
                        local={aqHistory.local}
                        national={aqHistory.national}
                        ladName={aqHistory.lad_name}
                      />
                    </CollapsibleSection>
                  )}

                  {/* Useful resources — always shown when data is resolved */}
                  {tabData?.metrics && (
                    <CollapsibleSection title="Useful Resources" defaultOpen={false}>
                      <UsefulResourcesPanel
                        postcode={resolved?.type === 'postcode' ? q : null}
                        ladCode={codes?.lad}
                      />
                    </CollapsibleSection>
                  )}

                  {tabData?.metrics.length === 0 && (
                    <div className="py-12 text-center text-ink-muted">
                      No data available for this tab and area.
                    </div>
                  )}
                </motion.div>
              )}
            </main>

            {/* Right: persistent map panel (desktop only) — only mounted on desktop viewports */}
            {isDesktop && resolved?.coordinates?.lat && (
              <aside className="w-[420px] shrink-0 sticky top-[105px] h-[calc(100vh-105px)] p-4 pl-0">
                <div className="rounded-2xl overflow-hidden shadow-sm h-full relative">
                  <MapView lat={resolved.coordinates.lat} lon={resolved.coordinates.lon!} boundary={effectiveBoundary} lsoaBoundary={effectiveLsoaBoundary} pois={mapPois} activeTab={activeTab} visibleLayers={visibleLayers} searchLsoa={lsoa !== '_' ? lsoa : undefined} initialViewport={mapViewportRef.current} onViewportChange={handleViewportChange} choroplethData={activeChoropleth ? choroplethData : null} />
                  <MapLayerControl activeTab={activeTab} visibleLayers={visibleLayers} onToggle={handleLayerToggle} soldPricesSince={(mapPois as any)?.sold_prices_since} />
                  {mapPoisLoading && (
                    <div className="absolute inset-0 z-[5] flex items-center justify-center bg-white/20 backdrop-blur-[1px] rounded-2xl pointer-events-none">
                      <div className="px-3 py-1.5 rounded-full bg-white/90 text-xs font-medium text-ink-muted shadow-sm">Loading…</div>
                    </div>
                  )}
                </div>
              </aside>
            )}
          </div>
        </>
      )}

      {/* Footer */}
      <footer className="px-6 py-4 text-center text-xs text-ink-faint border-t border-divider mt-auto">
        Contains OS, Land Registry, ONS, Ofcom data &copy; Crown copyright. &copy; OpenStreetMap contributors.{' '}
        <Link to="/data-attribution" className="underline hover:text-brand-600">Sources</Link>
      </footer>
    </div>
  );
}
