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
} from '../api/client';
import type { ResolveResponse, AreaResponse, TabName, PersonaId, Metric } from '../types';
import type {
  PriceHistoryResponse, AqHistoryResponse, PriceByTypeResponse, ComparableResponse, ChoroplethResponse,
  MapPoisResponse,
} from '../api/client';
import type { DecisionMode } from '../components/DecisionModeSelector';
import { saveArea, removeSavedArea, isAreaSaved, buildSavedAreaId } from '../utils/savedAreas';
import type { SavedAreaCollection } from '../utils/savedAreas';
import type { Dispatch, SetStateAction, MutableRefObject } from 'react';

export const ALL_TABS: TabName[] = [
  'Property & Market',
  'Lifestyle & Connectivity',
  'Environment & Safety',
  'Community & Education',
  'Local Governance',
];

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

  // ── Saved areas ───────────────────────────────────────────────────────────
  savedCollections: Record<SavedAreaCollection, boolean>;
  toggleSave: (collection: SavedAreaCollection) => void;

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
  const initialTab = ALL_TABS.find((t) => t === rawTab) ?? 'Property & Market';
  const [activeTab, setActiveTabRaw] = useState<TabName>(initialTab);
  const [, startTransition] = useTransition();
  const setActiveTab = useCallback((tab: TabName) => {
    startTransition(() => setActiveTabRaw(tab));
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (tab === 'Property & Market') {
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
  const [savedCollections, setSavedCollections] = useState<Record<SavedAreaCollection, boolean>>({
    shortlist: false,
    watchlist: false,
  });

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
    setSavedCollections({
      shortlist: isAreaSaved(areaName, 'shortlist', decisionMode),
      watchlist: isAreaSaved(areaName, 'watchlist', decisionMode),
    });
  }, [areaName, decisionMode]);

  // Sync saved-area state across browser tabs via storage events
  useEffect(() => {
    const handleStorage = (e: StorageEvent) => {
      if (e.key === 'propertypulse_saved_areas_v1' && areaName) {
        setSavedCollections({
          shortlist: isAreaSaved(areaName, 'shortlist', decisionMode),
          watchlist: isAreaSaved(areaName, 'watchlist', decisionMode),
        });
      }
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
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

  const allMetrics = tabData?.metrics ?? [];

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

  // Fetch comparable areas (only needed on Property tab)
  const { data: comparable } = useQuery({
    queryKey: ['comparable', sessionKey],
    queryFn: () => fetchComparable(sessionKey!),
    enabled: !!sessionKey && activeTab === 'Property & Market',
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
    savedCollections,
    toggleSave,
    isDesktop,
  }), [
    q, resolved, resolving, resolveError, codes, sessionKey, lsoa, parentName, areaName,
    activeTab, setActiveTab, persona, setPersona, decisionMode, handleDecisionModeChange,
    tabData, tabLoading, allMetrics, priceHistory, aqHistory, priceByType, comparable,
    boundaryData, effectiveBoundary, effectiveLsoaBoundary, mapPois, mapPoisLoading,
    choroplethData, choroplethUrl, savedCollections, toggleSave, isDesktop,
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
