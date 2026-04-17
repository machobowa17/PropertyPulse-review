import MetricCard from '../MetricCard';
import MortgageCalculator from '../MortgageCalculator';
import RentalYieldCalculator from '../RentalYieldCalculator';
import AirQualityChart from '../AirQualityChart';
import ComparableAreas from '../ComparableAreas';
import CommuteEstimator from '../CommuteEstimator';
import PersonaScoreCard from '../PersonaScoreCard';
import UsefulResourcesPanel from '../UsefulResourcesPanel';
import CollapsibleSection from '../CollapsibleSection';
import SkeletonCard from '../SkeletonCard';
import { TAB_EXPLAINERS } from '../../utils/tabExplainers';
import { buildSectionSummary } from '../../utils/sectionSummary';
import { useResults } from '../../context/ResultsContext';
import { ResultsMobileMap } from './ResultsMapPanel';

export function ResultsMetricsPanel() {
  const {
    q,
    resolved,
    codes,
    sessionKey,
    parentName,
    areaName,
    activeTab,
    persona,
    tabData,
    tabLoading,
    priceHistory,
    aqHistory,
    priceByType,
    comparable,
    decisionMode,
    setMetricElementRef,
  } = useResults();

  return (
    <main id="main-content" className="flex-1 min-w-0 px-4 lg:px-6 py-6">
      <ResultsMobileMap />

      {tabLoading ? (
        <SkeletonCard count={8} />
      ) : (
        <div
          key={activeTab}
          className="grid gap-2.5 animate-tab-enter"
        >
          {/* Tab explainer bar */}
          {TAB_EXPLAINERS[activeTab] != null && (
            <div className="rounded-xl bg-brand-50/50 border border-brand-100/60 px-4 py-3">
              <p className="text-xs font-semibold text-brand-700">{TAB_EXPLAINERS[activeTab].decision}</p>
              <p className="text-[11px] text-brand-600/70 mt-0.5">{TAB_EXPLAINERS[activeTab].summary}</p>
            </div>
          )}

          {/* Section summary chip */}
          {(tabData?.metrics?.length ?? 0) > 0 && (() => {
            const summary = buildSectionSummary(tabData!.metrics, parentName);
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
          {(tabData?.metrics?.length ?? 0) > 0 && (
            <PersonaScoreCard metrics={tabData!.metrics} persona={persona} decisionMode={decisionMode} />
          )}
          {/* Desktop table header */}
          {(tabData?.metrics?.length ?? 0) > 0 ? (
            <div className="hidden lg:grid lg:grid-cols-[2fr_1fr_1fr_1fr_1fr_28px] lg:gap-4 lg:px-5 lg:py-2 lg:text-[11px] lg:font-semibold lg:uppercase lg:tracking-wider lg:text-ink-faint">
              <span>Metric</span>
              <span>Local</span>
              <span>{parentName}</span>
              <span>So What</span>
              <span>Watch Out</span>
              <span />
            </div>
          ) : null}
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
          {activeTab === 'Property & Market' && (tabData?.metrics?.length ?? 0) > 0 && (() => {
            const metrics = tabData!.metrics;
            const medianPrice = metrics.find(m => m.id === 'median_price')?.local_value as number | undefined;
            const medianEarnings = metrics.find(m => m.id === 'median_earnings')?.local_value as number | undefined;
            const medianRent = metrics.find(m => m.id === 'median_rent')?.local_value as number | undefined;
            const avgPrice = metrics.find(m => m.id === 'avg_price')?.local_value as number | undefined;
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
          {activeTab === 'Property & Market' && comparable != null && comparable.comparable.length > 0 && (
            <CollapsibleSection title="Comparable Areas">
              <ComparableAreas target={comparable.target} comparable={comparable.comparable} />
            </CollapsibleSection>
          )}
          {activeTab === 'Property & Market' && comparable != null && !!(comparable as unknown as Record<string, unknown>).unsupported_scope && (
            <CollapsibleSection title="Comparable Areas">
              <div className="px-3 py-4 text-center">
                <p className="text-sm text-ink-muted">{String((comparable as unknown as Record<string, unknown>).reason || 'Comparable areas require a single local authority. Try a specific borough.')}</p>
              </div>
            </CollapsibleSection>
          )}
          {/* Commute estimator (Lifestyle tab) */}
          {activeTab === 'Lifestyle & Connectivity' && resolved?.coordinates?.lat != null && (tabData?.metrics?.length ?? 0) > 0 && (
            <CollapsibleSection title="Commute Estimator">
              <CommuteEstimator
                metrics={tabData!.metrics}
                originLabel={areaName}
              />
            </CollapsibleSection>
          )}
          {/* Air quality trend chart */}
          {activeTab === 'Environment & Safety' && aqHistory != null && aqHistory.local.length > 1 && (
            <CollapsibleSection title="Air Quality Trend">
              <AirQualityChart
                local={aqHistory.local}
                national={aqHistory.national}
                ladName={aqHistory.lad_name}
              />
            </CollapsibleSection>
          )}

          {/* Useful resources — always shown when data is resolved */}
          {tabData != null && (
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
        </div>
      )}
    </main>
  );
}
