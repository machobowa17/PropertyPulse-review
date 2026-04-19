import { useMemo } from 'react';
import MetricCard from '../MetricCard';
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
import type { Metric } from '../../types';

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

  const hiddenMetrics = useMemo(() => {
    if (!tabData?.metrics) return [];
    return tabData.metrics
      .filter((m: Metric) => m.local_value == null)
      .map((m: Metric) => {
        const note = (m.details?.data_note as string)
          || (m.details?.data_unavailable_note as string)
          || 'Data not available for this search area.';
        return { name: m.name, reason: note };
      });
  }, [tabData]);

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
          {tabData?.metrics.filter((m) => m.local_value != null).map((m) => (
            <div key={m.id}>
              <div id={`metric-${m.id}`} ref={(node) => setMetricElementRef(m.id, node)}>
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
              {m.id === 'air_quality_pm25' && aqHistory != null && aqHistory.local.length > 1 && (
                <div className="mt-2">
                  <AirQualityChart local={aqHistory.local} national={aqHistory.national} ladName={aqHistory.lad_name} pollutant="pm25" />
                </div>
              )}
              {m.id === 'air_quality_no2' && aqHistory != null && aqHistory.local.length > 1 && (
                <div className="mt-2">
                  <AirQualityChart local={aqHistory.local} national={aqHistory.national} ladName={aqHistory.lad_name} pollutant="no2" />
                </div>
              )}
            </div>
          ))}
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

          {/* Useful resources — always shown when data is resolved */}
          {tabData != null && (
            <CollapsibleSection title="Useful Resources" defaultOpen={false}>
              <UsefulResourcesPanel
                postcode={resolved?.type === 'postcode' ? q : null}
                ladCode={codes?.lad}
              />
            </CollapsibleSection>
          )}

          {hiddenMetrics.length > 0 && (
            <div className="rounded-xl bg-surface border border-divider/60 px-4 py-3 mt-2">
              <p className="text-[11px] font-semibold text-ink-faint uppercase tracking-wider mb-1.5">
                Hidden metrics ({hiddenMetrics.length})
              </p>
              <ul className="space-y-1">
                {hiddenMetrics.map((h) => (
                  <li key={h.name} className="text-[11px] text-ink-muted">
                    <span className="font-medium text-ink-faint">{h.name}</span>
                    <span className="mx-1">—</span>
                    <span>{h.reason}</span>
                  </li>
                ))}
              </ul>
            </div>
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
