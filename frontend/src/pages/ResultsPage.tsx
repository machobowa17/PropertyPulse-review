import { Link } from 'react-router-dom';
import { MapPin, SearchX } from 'lucide-react';

import TabBar from '../components/TabBar';
import { ResolvingSkeleton } from '../components/SkeletonCard';
import { ResultsHeader } from '../components/results/ResultsHeader';
import { ResultsHero } from '../components/results/ResultsHero';
import { ResultsDesktopMap } from '../components/results/ResultsMapPanel';
import { ResultsMetricsPanel } from '../components/results/ResultsMetricsPanel';

import { ResultsProvider, useResults } from '../context/ResultsContext';

// ── Inner component (reads from context) ────────────────────────────────────

function ResultsInner() {
  const {
    q,
    resolved,
    resolving,
    resolveError,
    codes,
    sessionKey,
    activeTab,
    setActiveTab,
  } = useResults();

  return (
    <div className="min-h-dvh flex flex-col bg-surface">
      {/* Skip to content (keyboard accessibility) */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-[9999] focus:px-4 focus:py-2 focus:bg-brand-600 focus:text-white focus:rounded-xl focus:text-sm focus:font-semibold focus:shadow-lg"
      >
        Skip to main content
      </a>

      <ResultsHeader />

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
                    <Link
                      key={s.label}
                      to={`/results?q=${encodeURIComponent(s.label)}`}
                      className="group flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm bg-surface hover:bg-brand-50 hover:text-brand-700 transition-all cursor-pointer"
                    >
                      <MapPin className="w-3 h-3 text-ink-faint group-hover:text-brand-500 shrink-0" />
                      <span className="font-semibold text-ink group-hover:text-brand-700">{s.label}</span>
                      {s.area && <span className="text-ink-faint text-xs group-hover:text-brand-500">{s.area}</span>}
                    </Link>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {codes && sessionKey && (
        <>
          <ResultsHero />

          {/* Tabs — sticky below header */}
          <div className="sticky top-[53px] z-40 bg-white/95 backdrop-blur-md border-b border-divider/60">
            <div className="max-w-[1400px] mx-auto px-4 lg:px-6">
              <TabBar active={activeTab} onChange={setActiveTab} />
            </div>
          </div>

          {/* Main layout: content + map side panel */}
          <div className="max-w-[1400px] mx-auto w-full flex-1 flex flex-col lg:flex-row">
            <ResultsMetricsPanel />
            <ResultsDesktopMap />
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

// ── Exported page component (wraps with Provider) ───────────────────────────

export function ResultsPage() {
  return (
    <ResultsProvider>
      <ResultsInner />
    </ResultsProvider>
  );
}
