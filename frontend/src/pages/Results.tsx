import { useState } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, MapPin, ArrowLeft, ChevronDown, Loader2 } from 'lucide-react';
import { resolveSearch, fetchAreaTab, fetchBoundary } from '../api/client';
import type { TabName, PersonaId } from '../types';
import PersonaSelector from '../components/PersonaSelector';
import TabBar from '../components/TabBar';
import MetricCard from '../components/MetricCard';
import MapView from '../components/MapView';

export default function Results() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const q = params.get('q') || '';
  const [searchInput, setSearchInput] = useState(q);
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

  // Fetch tab data
  const { data: tabData, isLoading: tabLoading } = useQuery({
    queryKey: ['area', lad, ward, lsoa, activeTab],
    queryFn: () => fetchAreaTab(lad, ward, lsoa, activeTab),
    enabled: !!codes && !!lad,
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchInput.trim()) navigate(`/results?q=${encodeURIComponent(searchInput.trim())}`);
  };

  const parentName = codes?.parent || 'England';
  const areaName = resolved?.type === 'postcode' ? q.toUpperCase() : q;

  return (
    <div className="min-h-dvh flex flex-col bg-surface">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white/90 backdrop-blur-md border-b border-divider">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-3">
          <Link to="/" className="p-2 rounded-xl hover:bg-surface transition-colors" title="Home">
            <ArrowLeft className="w-5 h-5 text-ink-muted" />
          </Link>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-brand-600 flex items-center justify-center">
              <MapPin className="w-3.5 h-3.5 text-white" />
            </div>
            <span className="font-bold text-sm tracking-tight text-ink hidden sm:block">PropertyPulse</span>
          </div>
          <form onSubmit={handleSearch} className="flex-1 max-w-md relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-faint" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="w-full h-10 pl-9 pr-4 rounded-xl border border-divider bg-surface text-sm text-ink
                         placeholder:text-ink-faint focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
              placeholder="Search postcode or place..."
            />
          </form>
          <PersonaSelector current={persona} onChange={setPersona} />
        </div>
      </header>

      {/* Resolve status */}
      {resolving && (
        <div className="flex items-center justify-center gap-2 py-16">
          <Loader2 className="w-5 h-5 animate-spin text-brand-600" />
          <span className="text-ink-muted">Resolving {q}...</span>
        </div>
      )}

      {resolveError && (
        <div className="max-w-2xl mx-auto mt-16 p-6 rounded-2xl bg-signal-red-bg text-signal-red text-center">
          Could not resolve &ldquo;{q}&rdquo;. Try a valid UK postcode or place name.
        </div>
      )}

      {resolved?.error && (
        <div className="max-w-2xl mx-auto mt-16 p-6 rounded-2xl bg-signal-amber-bg text-signal-amber text-center">
          {resolved.error}
        </div>
      )}

      {codes && (
        <>
          {/* Area banner */}
          <div className="max-w-7xl mx-auto w-full px-4 pt-5 pb-2">
            <div className="flex flex-wrap items-baseline gap-2">
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-ink">{areaName}</h1>
              <span className="text-sm text-ink-faint font-medium">
                vs {parentName}
              </span>
            </div>
            <div className="flex flex-wrap gap-2 mt-2 text-xs text-ink-muted">
              {codes.lad && <span className="px-2 py-0.5 rounded bg-brand-50 text-brand-700">LAD: {codes.lad}</span>}
              {codes.ward && <span className="px-2 py-0.5 rounded bg-brand-50 text-brand-700">Ward: {codes.ward}</span>}
              {codes.lsoa && <span className="px-2 py-0.5 rounded bg-brand-50 text-brand-700">LSOA: {codes.lsoa}</span>}
            </div>
          </div>

          {/* Map toggle (mobile) */}
          <div className="max-w-7xl mx-auto w-full px-4 lg:hidden">
            <button
              onClick={() => setShowMap(!showMap)}
              className="flex items-center gap-2 text-sm text-brand-600 font-medium py-2"
            >
              <MapPin className="w-4 h-4" />
              {showMap ? 'Hide Map' : 'View Map'}
              <ChevronDown className={`w-4 h-4 transition-transform ${showMap ? 'rotate-180' : ''}`} />
            </button>
          </div>

          {/* Map */}
          <AnimatePresence>
            {showMap && resolved?.coordinates?.lat && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 280, opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.3 }}
                className="max-w-7xl mx-auto w-full px-4 overflow-hidden"
              >
                <div className="rounded-2xl overflow-hidden border border-divider shadow-sm h-[280px]">
                  <MapView lat={resolved.coordinates.lat} lon={resolved.coordinates.lon!} boundary={boundary} />
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Tabs */}
          <div className="sticky top-[61px] z-40 bg-white/90 backdrop-blur-md border-b border-divider mt-4">
            <div className="max-w-7xl mx-auto px-4">
              <TabBar active={activeTab} onChange={setActiveTab} />
            </div>
          </div>

          {/* Metrics */}
          <main className="max-w-7xl mx-auto w-full px-4 py-6 flex-1">
            {tabLoading ? (
              <div className="flex items-center justify-center gap-2 py-16">
                <Loader2 className="w-5 h-5 animate-spin text-brand-600" />
                <span className="text-ink-muted">Loading {activeTab}...</span>
              </div>
            ) : (
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
                className="grid gap-3"
              >
                {/* Desktop table header — Bible 6.2.1: Metric | Local | Parent | So What | Watch Out */}
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
                {tabData?.metrics.length === 0 && (
                  <div className="py-12 text-center text-ink-muted">
                    No data available for this tab and area.
                  </div>
                )}
              </motion.div>
            )}
          </main>
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
