import { useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import { MapPin, ArrowLeft, ChevronDown, SearchX, FileDown, Leaf, Map } from 'lucide-react';
import { resolveSearch, fetchAreaTab, fetchBoundary, fetchLsoaBoundary, fetchPriceHistory, fetchAqHistory, fetchComparable, fetchMapPois, fetchDistrictPriceHistory } from '../api/client';
import type { TabName, PersonaId } from '../types';
import PersonaSelector from '../components/PersonaSelector';
import SearchBox from '../components/SearchBox';
import TabBar from '../components/TabBar';
import MetricCard from '../components/MetricCard';
import MortgageCalculator from '../components/MortgageCalculator';
import RentalYieldCalculator from '../components/RentalYieldCalculator';
import PriceHistoryChart from '../components/PriceHistoryChart';
import AirQualityChart from '../components/AirQualityChart';
import ComparableAreas from '../components/ComparableAreas';
import DistrictPriceHistoryChart from '../components/DistrictPriceHistoryChart';
import CommuteEstimator from '../components/CommuteEstimator';
import PersonaScoreCard from '../components/PersonaScoreCard';
import MapView from '../components/MapView';
import UsefulResourcesPanel from '../components/UsefulResourcesPanel';
import CollapsibleSection from '../components/CollapsibleSection';
import SkeletonCard, { ResolvingSkeleton } from '../components/SkeletonCard';

export default function Results() {
  const [params] = useSearchParams();
  const q = params.get('q') || '';
  const [activeTab, setActiveTab] = useState<TabName>('Property & Market');
  const [persona, setPersona] = useState<PersonaId>('family');
  const [showMap, setShowMap] = useState(true);

  // Resolve
  const { data: resolved, isLoading: resolving, error: resolveError } = useQuery({
    queryKey: ['resolve', q],
    queryFn: () => resolveSearch(q),
    enabled: !!q,
  });

  const codes = resolved?.resolved_codes;
  const lad = codes?.lad || '_';
  const ward = codes?.ward || '_';
  const lsoa = codes?.lsoa || '_';

  // Fetch ward boundary for map (Bible 6.2.4)
  const { data: boundary } = useQuery({
    queryKey: ['boundary', ward],
    queryFn: () => fetchBoundary(ward),
    enabled: !!ward && ward !== '_',
  });

  // Fetch LSOA boundary for tighter overlay on map
  const { data: lsoaBoundary } = useQuery({
    queryKey: ['lsoa-boundary', lsoa],
    queryFn: () => fetchLsoaBoundary(lsoa),
    enabled: !!lsoa && lsoa !== '_',
  });

  // Fetch tab data
  const { data: tabData, isLoading: tabLoading } = useQuery({
    queryKey: ['area', lad, ward, lsoa, activeTab],
    queryFn: () => fetchAreaTab(lad, ward, lsoa, activeTab),
    enabled: !!codes && !!lad,
  });

  // Fetch price history for chart (Property tab)
  const { data: priceHistory } = useQuery({
    queryKey: ['priceHistory', lad, ward, lsoa],
    queryFn: () => fetchPriceHistory(lad, ward, lsoa),
    enabled: !!codes && !!lad && lad !== '_',
  });

  // Fetch AQ history for chart (Environment tab)
  const { data: aqHistory } = useQuery({
    queryKey: ['aqHistory', lad],
    queryFn: () => fetchAqHistory(lad),
    enabled: !!codes && !!lad && lad !== '_',
  });

  // Derive postcode district from query (for postcode searches: "SW1A 1AA" → "SW1A")
  const postcodeDistrict = resolved?.type === 'postcode'
    ? q.toUpperCase().replace(/\s.*$/, '')
    : null;

  // Fetch district price history (postcode searches only)
  const { data: districtPrices } = useQuery({
    queryKey: ['districtPrices', postcodeDistrict],
    queryFn: () => fetchDistrictPriceHistory(postcodeDistrict!),
    enabled: !!postcodeDistrict && activeTab === 'Property & Market',
  });

  // Fetch comparable areas
  const { data: comparable } = useQuery({
    queryKey: ['comparable', lad],
    queryFn: () => fetchComparable(lad),
    enabled: !!codes && !!lad && lad !== '_',
  });

  // Fetch map POIs based on active tab
  const { data: mapPois } = useQuery({
    queryKey: ['mapPois', resolved?.coordinates?.lat, resolved?.coordinates?.lon, activeTab],
    queryFn: () => fetchMapPois(resolved!.coordinates!.lat ?? 0, resolved!.coordinates!.lon ?? 0, activeTab),
    enabled: resolved?.coordinates?.lat != null && resolved?.coordinates?.lon != null && (activeTab === 'Community & Education' || activeTab === 'Lifestyle & Connectivity' || activeTab === 'Environment & Safety'),
  });

  const parentName = codes?.parent || 'England';
  const areaName = resolved?.type === 'postcode' ? q.toUpperCase() : q;

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

      {codes && (
        <>
          {/* Area banner — hero strip */}
          <div className="bg-gradient-to-r from-brand-950 via-brand-900 to-brand-800 border-b border-brand-800/50">
            <div className="max-w-[1400px] mx-auto px-4 lg:px-6 py-5 lg:py-6">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                  <h1 className="text-2xl sm:text-3xl lg:text-4xl font-black tracking-tight text-white">{areaName}</h1>
                  <div className="flex items-center gap-3 mt-1.5">
                    <span className="text-sm text-white/50 font-medium">vs {parentName}</span>
                    <div className="flex items-center gap-1.5 text-[11px] text-white/30 font-mono">
                      {codes.lad && <span className="px-1.5 py-0.5 rounded bg-white/[0.06]">{codes.lad}</span>}
                      {codes.ward && <span className="px-1.5 py-0.5 rounded bg-white/[0.06]">{codes.ward}</span>}
                    </div>
                  </div>
                </div>
                <a
                  href={`/api/v1/report/${lad}/${ward}/${lsoa}`}
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
              <div className="lg:hidden mb-4">
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

              {/* Mobile map */}
              <AnimatePresence>
                {showMap && resolved?.coordinates?.lat && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 280, opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.3 }}
                    className="lg:hidden overflow-hidden mb-4"
                  >
                    <div className="rounded-2xl overflow-hidden shadow-sm h-[280px]">
                      <MapView lat={resolved.coordinates.lat} lon={resolved.coordinates.lon!} boundary={boundary} lsoaBoundary={lsoaBoundary} pois={mapPois} activeTab={activeTab} />
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
                    <MetricCard key={m.id} metric={m} persona={persona} parentName={parentName} />
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
                  {/* Price history chart */}
                  {activeTab === 'Property & Market' && priceHistory && priceHistory.local.length > 1 && (
                    <CollapsibleSection title="Price History">
                      <PriceHistoryChart
                        local={priceHistory.local}
                        regional={priceHistory.regional}
                        regionalName={priceHistory.regional_name}
                      />
                    </CollapsibleSection>
                  )}
                  {/* District price history by property type */}
                  {activeTab === 'Property & Market' && districtPrices && Object.keys(districtPrices.by_type).length > 0 && (
                    <CollapsibleSection title={`${districtPrices.district} — Price by Property Type`}>
                      <DistrictPriceHistoryChart data={districtPrices} />
                    </CollapsibleSection>
                  )}
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
                        originLat={resolved.coordinates.lat}
                        originLon={resolved.coordinates.lon!}
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

            {/* Right: persistent map panel (desktop only) */}
            {resolved?.coordinates?.lat && (
              <aside className="hidden lg:block w-[420px] shrink-0 sticky top-[105px] h-[calc(100vh-105px)] p-4 pl-0">
                <div className="rounded-2xl overflow-hidden shadow-sm h-full">
                  <MapView lat={resolved.coordinates.lat} lon={resolved.coordinates.lon!} boundary={boundary} lsoaBoundary={lsoaBoundary} pois={mapPois} activeTab={activeTab} />
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
