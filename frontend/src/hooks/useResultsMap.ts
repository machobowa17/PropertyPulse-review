import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import type { Dispatch, SetStateAction, MutableRefObject } from 'react';
import type { TabName, Metric } from '../types';
import {
  MAP_LAYER_PRIORITY, METRIC_MAP_BINDINGS, ALL_CHOROPLETH_KEYS,
} from '../utils/resultsConstants';

export type MapFocusMode = 'section' | 'metric' | 'manual' | 'metric-fallback';

type Viewport = { center: [number, number]; zoom: number };

interface UseResultsMapParams {
  allMetrics: Metric[];
  activeTab: TabName;
  isDesktop: boolean;
  sessionKey: string | undefined;
  q: string;
}

interface UseResultsMapReturn {
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
}

export function useResultsMap({
  allMetrics,
  activeTab,
  isDesktop,
  q,
}: UseResultsMapParams): UseResultsMapReturn {
  const [showMap, setShowMap] = useState(true);
  const [visibleLayers, setVisibleLayers] = useState<Record<string, boolean>>({});
  const [activeChoropleth, setActiveChoropleth] = useState<string | null>(null);
  const [mapFocusMode, setMapFocusMode] = useState<MapFocusMode>('section');
  const [activeMapMetricId, setActiveMapMetricId] = useState<string | null>(null);

  const mapViewportRef = useRef<Viewport | null>(null);
  const metricElementRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const activeScrollMetricIdRef = useRef<string | null>(null);

  const handleViewportChange = useCallback((vp: Viewport) => {
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

  const handleLayerToggle = useCallback((key: string) => {
    setMapFocusMode('manual');
    setActiveMapMetricId(null);
    if (ALL_CHOROPLETH_KEYS.includes(key)) {
      // Mutual exclusion: toggle off if already active, otherwise switch
      setActiveChoropleth((prev) => prev === key ? null : key);
      setVisibleLayers((prev) => {
        const next = { ...prev };
        for (const ck of ALL_CHOROPLETH_KEYS) next[ck] = ck === key ? !prev[key] : false;
        return next;
      });
    } else {
      setVisibleLayers((prev) => ({ ...prev, [key]: prev[key] !== false ? false : true }));
    }
  }, []);

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

  const handleMetricMapFocus = useCallback((metricId: string, _source: 'click' | 'scroll' = 'click') => {
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
  }, [applyMapFocusLayer]);

  const focusMetricById = useCallback((metricId: string, source: 'click' | 'scroll' = 'click') => {
    const metric = allMetricsById.get(metricId);
    if (!metric) return;
    handleMetricMapFocus(metricId, source);
  }, [allMetricsById, handleMetricMapFocus]);

  const setMetricElementRef = useCallback((metricId: string, node: HTMLDivElement | null) => {
    metricElementRefs.current[metricId] = node;
  }, []);

  // Scroll-based metric follow via IntersectionObserver (desktop only)
  useEffect(() => {
    if (!isDesktop || !showMap || mapFocusMode === 'manual' || allMetrics.length === 0) return;

    const visibleIds = new Set<string>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const mid = (entry.target as HTMLElement).dataset.metricId;
          if (!mid) continue;
          if (entry.isIntersecting) visibleIds.add(mid);
          else visibleIds.delete(mid);
        }
        // Pick the first visible metric in document order (matches allMetrics order)
        let nextMetricId: string | null = null;
        for (const m of allMetrics) {
          if (visibleIds.has(m.id)) { nextMetricId = m.id; break; }
        }
        if (!nextMetricId || nextMetricId === activeScrollMetricIdRef.current) return;
        activeScrollMetricIdRef.current = nextMetricId;
        focusMetricById(nextMetricId, 'scroll');
      },
      { rootMargin: '-35% 0px -35% 0px', threshold: 0 },
    );

    // Observe all registered metric elements
    for (const m of allMetrics) {
      const el = metricElementRefs.current[m.id];
      if (el) {
        el.dataset.metricId = m.id;
        observer.observe(el);
      }
    }

    return () => { observer.disconnect(); };
  }, [allMetrics, focusMetricById, isDesktop, mapFocusMode, showMap]);

  // Compute focus label/reason for MapLayerControl
  const activeFocusBinding = activeMapMetricId ? METRIC_MAP_BINDINGS[activeMapMetricId] : null;
  const focusLabel = activeFocusBinding?.label || null;
  const focusReason = activeFocusBinding?.reason || null;

  return {
    showMap,
    setShowMap,
    visibleLayers,
    activeChoropleth,
    mapFocusMode,
    activeMapMetricId,
    focusLabel,
    focusReason,
    mapViewportRef,
    handleViewportChange,
    handleLayerToggle,
    handleMetricMapFocus,
    setMetricElementRef,
  };
}
