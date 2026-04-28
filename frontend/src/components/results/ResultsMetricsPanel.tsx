import { useState, useEffect, useMemo } from 'react';
import { CirclePlus, CircleMinus } from 'lucide-react';
import MetricCard from '../MetricCard';
import { MetricErrorBoundary } from '../ErrorBoundary';
import ComparableAreas from '../ComparableAreas';
import CommuteEstimator from '../CommuteEstimator';
import PersonaScoreCard from '../PersonaScoreCard';
import UsefulResourcesPanel from '../UsefulResourcesPanel';
import CollapsibleSection from '../CollapsibleSection';
import SkeletonCard from '../SkeletonCard';
import { TAB_EXPLAINERS } from '../../utils/tabExplainers';
import { formatValue } from '../../utils/tabs';
import {
  groupMetricsBySection,
  pickSummaryPills,
  pillColor,
  sectionBadgeText,
  sectionBadgeColor,
} from '../../utils/sectionGrouping';
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
    priceByType,
    comparable,
    decisionMode,
    setMetricElementRef,
    activeMapMetricId,
    isDesktop,
  } = useResults();

  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());

  const sections = useMemo(
    () => groupMetricsBySection(tabData?.metrics ?? []),
    [tabData],
  );

  // All sections collapsed by default on tab change + scroll to top
  useEffect(() => {
    setExpandedSections(new Set());
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, [activeTab]);

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

          {/* Persona score card */}
          {(tabData?.metrics?.length ?? 0) > 0 && (
            <PersonaScoreCard metrics={tabData!.metrics} persona={persona} decisionMode={decisionMode} />
          )}

          {/* Section accordion */}
          {sections.map((section) => {
            const isOpen = expandedSections.has(section.config.id);
            const SectionIcon = section.config.icon;
            const badge = sectionBadgeText(section.metrics);
            const pills = !isOpen ? pickSummaryPills(section.metrics) : [];

            return (
              <div
                key={section.config.id}
                className="rounded-2xl border border-divider bg-white overflow-hidden shadow-sm"
              >
                {/* Section header */}
                <button
                  onClick={() => setExpandedSections(prev => {
                    const next = new Set(prev);
                    if (next.has(section.config.id)) next.delete(section.config.id);
                    else next.add(section.config.id);
                    return next;
                  })}
                  aria-expanded={isOpen}
                  aria-controls={`section-panel-${section.config.id}`}
                  className="w-full flex items-center gap-3 px-5 py-3 text-left hover:bg-surface-warm/50 transition-colors cursor-pointer"
                >
                  <div className="w-7 h-7 rounded-md bg-amber-50 flex items-center justify-center shrink-0">
                    <SectionIcon size={15} className="text-amber-700" />
                  </div>
                  <h3 className="text-sm font-semibold text-ink">{section.config.label}</h3>
                  <div className="flex-1" />
                  {badge && (
                    <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${sectionBadgeColor(badge)}`}>
                      {badge}
                    </span>
                  )}
                  {isOpen
                    ? <CircleMinus size={20} className="text-ink-faint shrink-0" />
                    : <CirclePlus size={20} className="text-ink-faint shrink-0" />
                  }
                </button>

                {/* Collapsed: summary pills */}
                {!isOpen && pills.length > 0 && (() => {
                  const remaining = section.metrics.length - pills.length;
                  return (
                    <div className="flex flex-wrap gap-2 px-5 pb-3">
                      {pills.map((m) => (
                        <span
                          key={m.id}
                          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs border ${pillColor(m.comparison_flag, m.interpretation_direction)}`}
                        >
                          <span className="truncate max-w-[120px]">{m.name}</span>
                          <span className="font-semibold font-mono tabular-nums">{formatValue(m.local_value as number | string | null, m.unit)}</span>
                        </span>
                      ))}
                      {remaining > 0 && (
                        <span className="inline-flex items-center px-2.5 py-1 rounded-lg bg-surface-warm text-xs text-ink-faint border border-divider/50">
                          +{remaining} more
                        </span>
                      )}
                    </div>
                  );
                })()}

                {/* Expanded: metric cards (prototype inline style) */}
                {isOpen && (
                  <div id={`section-panel-${section.config.id}`} role="region" aria-label={section.config.label} className="divide-y divide-divider/50 border-t border-divider/50">
                    {section.metrics.map((m) => (
                      <div key={m.id}>
                        <div id={`metric-${m.id}`} ref={(node) => setMetricElementRef(m.id, node)}>
                          <MetricErrorBoundary>
                            <MetricCard
                              metric={m}
                              persona={persona}
                              parentName={parentName}
                              priceByTypeData={(m.id === 'avg_price' || m.id === 'median_price' || m.id === 'price_per_sqft') ? (priceByType ?? undefined) : undefined}
                              priceHistoryData={(m.id === 'avg_price' || m.id === 'median_price' || m.id === 'price_per_sqft') ? (priceHistory ?? undefined) : undefined}
                              areaName={(m.id === 'avg_price' || m.id === 'median_price' || m.id === 'price_per_sqft') ? areaName : undefined}
                              sessionKey={m.id === 'transaction_volume' ? sessionKey : undefined}
                              isMapActive={isDesktop && activeMapMetricId === m.id}
                            />
                          </MetricErrorBoundary>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}

          {/* Comparable areas */}
          {activeTab === 'Property & Market' && comparable != null && comparable.comparable.length > 0 && (
            <CollapsibleSection title="Comparable Areas" defaultOpen={false}>
              <ComparableAreas target={comparable.target} comparable={comparable.comparable} />
            </CollapsibleSection>
          )}
          {activeTab === 'Property & Market' && comparable != null && !!(comparable as unknown as Record<string, unknown>).unsupported_scope && (
            <CollapsibleSection title="Comparable Areas" defaultOpen={false}>
              <div className="px-3 py-4 text-center">
                <p className="text-sm text-ink-muted">{String((comparable as unknown as Record<string, unknown>).reason || 'Comparable areas require a single local authority. Try a specific borough.')}</p>
              </div>
            </CollapsibleSection>
          )}
          {/* Commute estimator (Lifestyle tab) */}
          {activeTab === 'Lifestyle & Connectivity' && resolved?.coordinates?.lat != null && (tabData?.metrics?.length ?? 0) > 0 && (
            <CollapsibleSection title="Commute Estimator" defaultOpen={false}>
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
                Metrics not shown for this search key ({hiddenMetrics.length})
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
