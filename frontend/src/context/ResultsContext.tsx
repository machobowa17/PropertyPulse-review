import { createContext, useContext, useState, useEffect, useRef, useCallback, useTransition, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useIsDesktop } from '../hooks/useIsDesktop';
import { useResultsMap } from '../hooks/useResultsMap';
import type { MapFocusMode } from '../hooks/useResultsMap';
import {
  resolveSearch, fetchAreaTab, fetchBoundary,
  fetchPriceHistory, fetchAqHistory, fetchComparable,
  fetchMapPois, fetchPriceByType, fetchChoropleth, buildChoroplethUrl, SessionExpiredError,
  fetchPropertyData,
} from '../api/client';
import type { ResolveResponse, AreaResponse, TabName, PersonaId, Metric } from '../types';
import type {
  PriceHistoryResponse, AqHistoryResponse, PriceByTypeResponse, ComparableResponse, ChoroplethResponse,
  MapPoisResponse, PropertyDataResponse,
} from '../api/client';
import type { DecisionMode } from '../components/DecisionModeSelector';
import { saveArea, removeSavedArea, isAreaSaved, buildSavedAreaId } from '../utils/savedAreas';
import type { Dispatch, SetStateAction, MutableRefObject } from 'react';

export const ALL_TABS: TabName[] = [
  'Overview',
  'Property & Market',
  'Lifestyle & Connectivity',
  'Environment & Safety',
  'Community & Education',
  'Local Governance',
];

/** Property selection state for P53 single-address drill-down */
export interface SelectedProperty {
  lat: number;
  lon: number;
  postcode: string | null;
  paon: string | null;
  saon: string | null;
  street: string | null;
  uprn: number | null;
  addressDisplay?: string;
}

type ResolvedCodes = NonNullable<ResolveResponse['resolved_codes']>;
type Viewport = { center: [number, number]; zoom: number };

// ── R1: Split into stable data context + volatile UI context ─────────────────
// ResultsDataContext: stable — changes when tab/area/session changes
export interface ResultsDataContextValue {
  // ── Resolved search ──────────────────────────────────────────────────────
  q: string;
  resolved: ResolveResponse | undefined;
  resolving: boolean;
  resolveError: Error | null;
  codes: ResolvedCodes | undefined;
  sessionKey: string | undefined;
  lsoa: string;
  parentName: string;
  areaName: string;

  // ── Tab & persona ─────────────────────────────────────────────────────────
  activeTab: TabName;
  setActiveTab: (tab: TabName) => void;
  persona: PersonaId;
  setPersona: (id: PersonaId) => void;
  decisionMode: DecisionMode;
  handleDecisionModeChange: (mode: DecisionMode) => void;

  // ── Tab data ──────────────────────────────────────────────────────────────
  tabData: AreaResponse | undefined;
  tabLoading: boolean;
  allMetrics: Metric[];

  // ── Supplemental data ─────────────────────────────────────────────────────
  priceHistory: PriceHistoryResponse | undefined | null;
  aqHistory: AqHistoryResponse | undefined | null;
  priceByType: PriceByTypeResponse | undefined | null;
  comparable: ComparableResponse | undefined | null;

  // ── Map data (fetched, not UI state) ─────────────────────────────────────
  boundaryData: GeoJSON.Feature | GeoJSON.FeatureCollection | null | undefined;
  effectiveBoundary: GeoJSON.Feature | null;
  effectiveLsoaBoundary: GeoJSON.Feature | null | undefined;
  mapPois: MapPoisResponse | undefined | null;
  mapPoisLoading: boolean;
  choroplethData: ChoroplethResponse | undefined | null;
  choroplethUrl: string | null;

  // ── Property selection (P53) ─────────────────────────────────────────────
  selectedProperty: SelectedProperty | null;
  selectProperty: (prop: SelectedProperty) => void;
  clearProperty: () => void;
  propertyData: PropertyDataResponse | null | undefined;
  propertyLoading: boolean;
  propertyError: boolean;

  // ── Saved areas ───────────────────────────────────────────────────────────
  isSaved: boolean;
  toggleSave: () => void;

  // ── Viewport ──────────────────────────────────────────────────────────────
  isDesktop: boolean;
}

// ResultsUIContext: volatile — changes on every scroll, pan, layer toggle
export interface ResultsUIContextValue {
  showMap: boolean;
  setShowMap: Dispatch<SetStateAction<boolean>>;
  visibleLayers: Record<string, boolean>;
  activeChoropleth: string | null;
  mapFocusMode: MapFocusMode;
  activeMapMetricId: string | null;
  autoFollowEnabled: boolean;
  setAutoFollowEnabled: Dispatch<SetStateAction<boolean>>;
  focusLabel: string | null;
  focusReason: string | null;
  mapViewportRef: MutableRefObject<Viewport | null>;
  handleViewportChange: (vp: Viewport) => void;
  handleLayerToggle: (key: string) => void;
  handleMetricMapFocus: (metricId: string, source?: 'click' | 'scroll') => void;
  setMetricElementRef: (metricId: string, node: HTMLDivElement | null) => void;
  mapFlyToRef: MutableRefObject<((lng: number, lat: number, zoom?: number) => void) | null>;
  mapHighlightRef: MutableRefObject<((lng: number, lat: number, props?: Record<string, unknown>) => void) | null>;
  clearMapHighlight: () => void;
}

// Combined type for backward-compatible useResults()
export type ResultsContextValue = ResultsDataContextValue & ResultsUIContextValue;

const ResultsDataContext = createContext<ResultsDataContextValue | null>(null);
const ResultsUIContext = createContext<ResultsUIContextValue | null>(null);
// Legacy single-context kept for backward compatibility (reads from both)
const ResultsContext = createContext<ResultsContextValue | null>(null);

export function ResultsProvider({ children }: { children: React.ReactNode }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const q = searchParams.get('q') || '';
  const rawMode = searchParams.get('mode');
  const queryClient = useQueryClient();

  const rawTab = searchParams.get('tab');
  const initialTab = ALL_TABS.find((t) => t === rawTab) ?? 'Overview';
  const [activeTab, setActiveTabRaw] = useState<TabName>(initialTab);
  const [, startTransition] = useTransition();
  const setActiveTab = useCallback((tab: TabName) => {
    startTransition(() => setActiveTabRaw(tab));
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (tab === 'Overview') {
        next.delete('tab');
      } else {
        next.set('tab', tab);
      }
      return next;
    }, { replace: true });
  }, [startTransition, setSearchParams]);
  const [persona, setPersona] = useState<PersonaId>('family');
  const [decisionMode, setDecisionMode] = useState<DecisionMode>(
    rawMode === 'rent' || rawMode === 'invest' ? rawMode : 'buy',
  );
  const handleDecisionModeChange = (mode: DecisionMode) => {
    setDecisionMode(mode);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('mode', mode);
      return next;
    }, { replace: true });
  };
  const [isSaved, setIsSaved] = useState(false);

  const isDesktop = useIsDesktop();

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
    setIsSaved(isAreaSaved(areaName, decisionMode));
  }, [areaName, decisionMode]);

  // Sync saved-area state across browser tabs via storage events
  useEffect(() => {
    const handleStorage = (e: StorageEvent) => {
      if (e.key === 'propertypulse_saved_areas_v2' && areaName) {
        setIsSaved(isAreaSaved(areaName, decisionMode));
      }
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, [areaName, decisionMode]);

  const toggleSave = () => {
    if (!areaName) return;
    if (isSaved) {
      removeSavedArea(buildSavedAreaId(areaName, decisionMode));
    } else {
      saveArea({
        query: q,
        areaName,
        parentName,
        sessionKey: sessionKey ?? null,
        decisionMode,
        persona,
        notes: [],
      });
    }
    setIsSaved((prev) => !prev);
  };

  // ── Property selection state (P53) ────────────────────────────────────────
  const [selectedProperty, setSelectedProperty] = useState<SelectedProperty | null>(null);

  const selectProperty = useCallback((prop: SelectedProperty) => {
    setSelectedProperty(prop);
    // Switch to Property tab (first position) — but Property tab doesn't exist
    // as a server tab, so we render it client-side when selectedProperty is set
  }, []);

  const clearProperty = useCallback(() => {
    setSelectedProperty(null);
    // Switch back to Overview when property is dismissed
    setActiveTab('Overview');
  }, [setActiveTab]);

  // Fetch property-specific data (parcel, flood, noise, broadband, LLC)
  const { data: propertyData, isLoading: propertyLoading, isError: propertyError } = useQuery({
    queryKey: ['propertyData', sessionKey, selectedProperty?.lat, selectedProperty?.lon, selectedProperty?.paon, selectedProperty?.saon, selectedProperty?.uprn],
    queryFn: () => fetchPropertyData(
      sessionKey!,
      selectedProperty!.lat,
      selectedProperty!.lon,
      selectedProperty!.postcode,
      selectedProperty!.paon,
      selectedProperty!.saon,
      selectedProperty!.street,
      selectedProperty!.uprn,
      codes?.lsoa,
    ),
    enabled: !!sessionKey && !!selectedProperty,
  });

  // If resolve returns property data (address search), auto-select it —
  // UNLESS there are alternatives needing disambiguation (e.g. multiple flats).
  useEffect(() => {
    if (resolved?.type === 'address' && resolved?.property) {
      // If alternatives exist (multiple flats), don't auto-select — PropertyTab shows picker
      if (resolved.alternatives && resolved.alternatives.length > 0) {
        setSelectedProperty(null);
      } else {
        const p = resolved.property;
        setSelectedProperty({
          lat: p.lat,
          lon: p.lon,
          postcode: p.postcode,
          paon: p.paon,
          saon: p.saon ?? null,
          street: p.street,
          uprn: p.uprn ?? null,
          addressDisplay: p.address_display,
        });
      }
    } else if (resolved && resolved.type !== 'address') {
      setSelectedProperty(null);
    }
  }, [resolved]);

  // Pre-fetch remaining tabs with staggered delays to avoid a 4-request burst.
  // Adjacent tab fires immediately; others stagger at 2s intervals.
  useEffect(() => {
    if (!sessionKey) return;
    const otherTabs = ALL_TABS.filter((t) => t !== activeTab);
    const timers: ReturnType<typeof setTimeout>[] = [];
    otherTabs.forEach((tab, i) => {
      const delay = i === 0 ? 0 : i * 2000;
      const timer = setTimeout(() => {
        queryClient.prefetchQuery({
          queryKey: ['area', sessionKey, tab],
          queryFn: () => fetchAreaTab(sessionKey, tab),
          staleTime: 5 * 60 * 1000,
        });
      }, delay);
      timers.push(timer);
    });
    return () => timers.forEach(clearTimeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionKey]);

  // Fetch boundary
  const { data: boundaryData } = useQuery({
    queryKey: ['boundary', sessionKey],
    queryFn: () => fetchBoundary(sessionKey!),
    enabled: !!sessionKey,
  });

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

  // Fetch tab data — R14: on 410 (session expired), invalidate resolve to get fresh session key
  const { data: tabData, isLoading: tabLoading } = useQuery({
    queryKey: ['area', sessionKey, activeTab],
    queryFn: () => fetchAreaTab(sessionKey!, activeTab),
    enabled: !!sessionKey,
    retry: (failureCount, error) => {
      if (error instanceof SessionExpiredError) {
        queryClient.invalidateQueries({ queryKey: ['resolve', q] });
        return false; // don't retry — new session key will re-trigger
      }
      return failureCount < 2;
    },
  });

  // allMetrics: on Overview tab, combine metrics from all cached data tabs for holistic persona scoring
  const allMetrics = useMemo(() => {
    if (activeTab !== 'Overview') return tabData?.metrics ?? [];
    const combined: Metric[] = [];
    for (const tab of ALL_TABS.filter(t => t !== 'Overview')) {
      const cached = queryClient.getQueryData<AreaResponse>(['area', sessionKey, tab]);
      if (cached?.metrics) combined.push(...cached.metrics);
    }
    return combined;
  }, [activeTab, sessionKey, tabData, queryClient]);

  // Fetch price history (Property tab)
  const { data: priceHistory } = useQuery({
    queryKey: ['priceHistory', sessionKey],
    queryFn: () => fetchPriceHistory(sessionKey!),
    enabled: !!sessionKey && activeTab === 'Property & Market',
  });

  // Fetch AQ history (Environment tab)
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

  // Fetch comparable areas (Overview + Property tabs)
  const { data: comparable } = useQuery({
    queryKey: ['comparable', sessionKey],
    queryFn: () => fetchComparable(sessionKey!),
    enabled: !!sessionKey && (activeTab === 'Overview' || activeTab === 'Property & Market'),
  });

  // Fetch map POIs based on active tab
  const { data: mapPois, isFetching: mapPoisLoading } = useQuery({
    queryKey: ['mapPois', sessionKey, activeTab],
    queryFn: () => fetchMapPois(sessionKey!, activeTab),
    enabled: !!sessionKey && (
      activeTab === 'Property & Market' ||
      activeTab === 'Community & Education' ||
      activeTab === 'Lifestyle & Connectivity' ||
      activeTab === 'Environment & Safety'
    ),
    placeholderData: (prev) => prev,
  });

  // Map state — call useResultsMap BEFORE choropleth query (activeChoropleth comes from hook)
  const mapState = useResultsMap({ allMetrics, activeTab, isDesktop, sessionKey, q });

  // Ref for map flyTo function — populated by MapView's onMapReady callback
  const mapFlyToRef = useRef<((lng: number, lat: number, zoom?: number) => void) | null>(null);
  // Ref for map temporary highlight marker — shows a marker at coordinates, removed on clear
  const mapHighlightRef = useRef<((lng: number, lat: number, props?: Record<string, unknown>) => void) | null>(null);
  const clearMapHighlight = useCallback(() => { mapHighlightRef.current?.(0, 0); }, []);

  // Fly map to property when selected (P53)
  useEffect(() => {
    if (selectedProperty && mapFlyToRef.current) {
      mapFlyToRef.current(selectedProperty.lon, selectedProperty.lat, 17);
      mapHighlightRef.current?.(selectedProperty.lon, selectedProperty.lat, { title: 'Selected property' });
    }
  }, [selectedProperty]);

  // Lazy-fetch choropleth data only when a heatmap layer is active
  const choroplethLayer = mapState.activeChoropleth?.replace('choropleth_', '') || null;
  const { data: choroplethData } = useQuery({
    queryKey: ['choropleth', sessionKey, choroplethLayer],
    queryFn: () => fetchChoropleth(sessionKey!, choroplethLayer!),
    enabled: !!sessionKey && !!choroplethLayer,
  });
  // R2: URL for MapLibre off-thread fetch (parsed in worker, not main thread)
  const choroplethUrl = sessionKey && choroplethLayer ? buildChoroplethUrl(sessionKey, choroplethLayer) : null;

  // R1: split into stable data + volatile UI — memoized to prevent unnecessary re-renders
  const dataValue: ResultsDataContextValue = useMemo(() => ({
    q,
    resolved,
    resolving,
    resolveError: resolveError as Error | null,
    codes,
    sessionKey,
    lsoa,
    parentName,
    areaName,
    activeTab,
    setActiveTab,
    persona,
    setPersona,
    decisionMode,
    handleDecisionModeChange,
    tabData,
    tabLoading,
    allMetrics,
    priceHistory,
    aqHistory,
    priceByType,
    comparable,
    boundaryData,
    effectiveBoundary,
    effectiveLsoaBoundary,
    mapPois,
    mapPoisLoading,
    choroplethData,
    choroplethUrl,
    selectedProperty,
    selectProperty,
    clearProperty,
    propertyData,
    propertyLoading,
    propertyError,
    isSaved,
    toggleSave,
    isDesktop,
  }), [
    q, resolved, resolving, resolveError, codes, sessionKey, lsoa, parentName, areaName,
    activeTab, setActiveTab, persona, setPersona, decisionMode, handleDecisionModeChange,
    tabData, tabLoading, allMetrics, priceHistory, aqHistory, priceByType, comparable,
    boundaryData, effectiveBoundary, effectiveLsoaBoundary, mapPois, mapPoisLoading,
    choroplethData, choroplethUrl,
    selectedProperty, selectProperty, clearProperty, propertyData, propertyLoading, propertyError,
    isSaved, toggleSave, isDesktop,
  ]);

  const uiValue: ResultsUIContextValue = useMemo(
    () => ({ ...mapState, mapFlyToRef, mapHighlightRef, clearMapHighlight }),
    [mapState, mapFlyToRef, mapHighlightRef, clearMapHighlight],
  );

  const combinedValue: ResultsContextValue = useMemo(
    () => ({ ...dataValue, ...uiValue }),
    [dataValue, uiValue],
  );

  return (
    <ResultsDataContext.Provider value={dataValue}>
      <ResultsUIContext.Provider value={uiValue}>
        <ResultsContext.Provider value={combinedValue}>
          {children}
        </ResultsContext.Provider>
      </ResultsUIContext.Provider>
    </ResultsDataContext.Provider>
  );
}

/** Backward-compatible combined context — use for existing consumers */
export function useResults(): ResultsContextValue {
  const ctx = useContext(ResultsContext);
  if (!ctx) throw new Error('useResults must be used within ResultsProvider');
  return ctx;
}

/** Stable data context — subscribe only to session/tab/data changes */
export function useResultsData(): ResultsDataContextValue {
  const ctx = useContext(ResultsDataContext);
  if (!ctx) throw new Error('useResultsData must be used within ResultsProvider');
  return ctx;
}

/** Volatile UI context — subscribe to map interaction changes */
export function useResultsUI(): ResultsUIContextValue {
  const ctx = useContext(ResultsUIContext);
  if (!ctx) throw new Error('useResultsUI must be used within ResultsProvider');
  return ctx;
}
