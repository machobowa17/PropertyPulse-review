import { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import { MapPin, ArrowLeft, ChevronDown, SearchX, FileDown, Leaf, Map } from 'lucide-react';

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
  const [params] = useSearchParams();
  const q = params.get('q') || '';
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<TabName>('Property & Market');
  const [persona, setPersona] = useState<PersonaId>('family');
  const [showMap, setShowMap] = useState(true);
  const [visibleLayers, setVisibleLayers] = useState<Record<string, boolean>>({});
  const [activeChoropleth, setActiveChoropleth] = useState<string | null>(null);
  const isDesktop = useIsDesktop();
  const mapViewportRef = useRef<{ center: [number, number]; zoom: number } | null>(null);
  const handleViewportChange = useCallback((vp: { center: [number, number]; zoom: number }) => {
    mapViewportRef.current = vp;
  }, []);

  // Reset saved viewport + clear choropleth when search query changes (new location)
  useEffect(() => {
    mapViewportRef.current = null;
    setActiveChoropleth(null);
    setVisibleLayers((prev) => {
      const next = { ...prev };
      for (const ck of ['choropleth_avg_price', 'choropleth_price_per_sqft', 'choropleth_epc_score']) next[ck] = false;
      return next;
    });
  }, [q]);

  // Clear choropleth when leaving Property tab
  useEffect(() => {
    if (activeTab !== 'Property & Market') {
      setActiveChoropleth(null);
      setVisibleLayers((prev) => {
        const next = { ...prev };
        for (const ck of ['choropleth_avg_price', 'choropleth_price_per_sqft', 'choropleth_epc_score']) next[ck] = false;
        return next;
      });
    }
  }, [activeTab]);

  const CHOROPLETH_KEYS = ['choropleth_avg_price', 'choropleth_price_per_sqft', 'choropleth_epc_score'];

  const handleLayerToggle = (key: string) => {
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
    enabled: !!sessionKey && !!choroplethLayer && activeTab === 'Property & Market',
  });

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
          <PersonaSelector current={persona} onChange={setPersona} />
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
                      <MapLayerControl activeTab={activeTab} visibleLayers={visibleLayers} onToggle={handleLayerToggle} soldPricesSince={(mapPois as any)?.sold_prices_since} />
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
                    <MetricCard
                      key={m.id}
                      metric={m}
                      persona={persona}
                      parentName={parentName}
                      priceByTypeData={(m.id === 'avg_price' || m.id === 'median_price' || m.id === 'price_per_sqft') ? (priceByType ?? undefined) : undefined}
                      priceHistoryData={(m.id === 'avg_price' || m.id === 'median_price' || m.id === 'price_per_sqft') ? (priceHistory ?? undefined) : undefined}
                      areaName={(m.id === 'avg_price' || m.id === 'median_price' || m.id === 'price_per_sqft') ? areaName : undefined}
                      sessionKey={m.id === 'transaction_volume' ? sessionKey : undefined}
                    />
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
