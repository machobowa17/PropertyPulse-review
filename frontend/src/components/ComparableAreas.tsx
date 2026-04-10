import { ArrowRight, Layers3 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import type { ComparableArea, ComparableTarget } from '../api/client';
import type { DecisionMode } from './DecisionModeSelector';

interface Props {
  target: ComparableTarget;
  comparable: ComparableArea[];
  decisionMode?: DecisionMode;
  comparisonBasis?: string;
}

function fmtCurrency(n: number | null | undefined) {
  if (n == null) return 'N/A';
  return '£' + n.toLocaleString('en-GB', { maximumFractionDigits: 0 });
}

function fmtSignedPercent(n: number | null | undefined): string {
  if (n == null) return 'N/A';
  return `${n > 0 ? '+' : ''}${n.toFixed(1)}%`;
}

function similarityColour(pct: number): string {
  if (pct >= 75) return '#22c55e';
  if (pct >= 50) return '#84cc16';
  if (pct >= 30) return '#facc15';
  return '#fb923c';
}

function similarityVerdict(pct: number): string {
  if (pct >= 75) return 'Very close profile match';
  if (pct >= 50) return 'Useful benchmark match';
  if (pct >= 30) return 'Partial benchmark match';
  return 'Loose benchmark only';
}

function scopeLabel(scopeType?: string, componentCount?: number) {
  if ((componentCount ?? 0) > 1) return `${componentCount} LAD scope`;
  if (scopeType === 'county') return 'County-scale benchmark';
  if (scopeType === 'place') return 'Place benchmark';
  return 'Local-authority benchmark';
}

export default function ComparableAreas({ target, comparable, decisionMode, comparisonBasis }: Props) {
  const navigate = useNavigate();

  if (comparable.length === 0) return null;

  const targetName = target.scope_name || target.lad_name || 'Selected area';
  const targetComponentCount = target.component_count ?? target.lad_count ?? 1;
  const targetScopeLabel = scopeLabel(target.scope_type, targetComponentCount);

  return (
    <div className="mt-2 space-y-3">
      <div className="rounded-xl border border-divider bg-surface/70 px-3 py-2.5">
        <p className="text-xs leading-5 text-ink-muted">
          These benchmark areas are the closest profile matches to <span className="font-semibold text-ink">{targetName}</span>{' '}
          using price, rent, earnings, air quality, and price growth. For broader searches, the target scope is first averaged across its
          component local authorities so the comparison stays directionally honest rather than pretending a county behaves like one single LAD.
        </p>
        {comparisonBasis && (
          <p className="mt-2 text-[11px] leading-5 text-ink-faint">Method: {comparisonBasis}</p>
        )}
      </div>

      <div className="rounded-xl border border-brand-100 bg-brand-50/70 px-3 py-2.5">
        <div className="flex flex-wrap items-center gap-2 text-[11px] text-brand-800">
          <span className="inline-flex items-center gap-1 rounded-full border border-brand-200 bg-white/70 px-2 py-1 font-semibold uppercase tracking-wide">
            <Layers3 className="h-3 w-3" aria-hidden="true" />
            {targetScopeLabel}
          </span>
          <span>
            Target basis: <span className="font-semibold">{targetComponentCount}</span> contributing {targetComponentCount === 1 ? 'authority' : 'authorities'}.
          </span>
        </div>
      </div>

      <div className="space-y-2">
        {comparable.map((area, index) => {
          const pct = Math.round(area.similarity_pct ?? 0);
          const colour = similarityColour(pct);
          const verdict = similarityVerdict(pct);
          const candidateComponentCount = area.component_count ?? 1;

          return (
            <div
              key={`${area.lad_code}-${index}`}
              className="rounded-xl border border-divider bg-white p-3 transition-shadow hover:shadow-sm"
            >
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full border border-divider bg-surface px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-faint">
                      #{index + 1} match
                    </span>
                    <span className="text-sm font-semibold text-ink">{area.scope_name || area.lad_name}</span>
                    <span className="text-[11px] font-medium" style={{ color: colour }}>
                      {verdict}
                    </span>
                    <span className="rounded-full border border-divider bg-white px-2 py-0.5 text-[10px] font-medium text-ink-faint">
                      {scopeLabel(area.scope_type, candidateComponentCount)}
                    </span>
                  </div>

                  <div className="mt-2 flex items-center gap-2">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-divider">
                      <div
                        className="h-full rounded-full transition-all"
                        style={{ width: `${pct}%`, backgroundColor: colour }}
                      />
                    </div>
                    <div className="shrink-0 text-right">
                      <div className="text-xs font-bold" style={{ color: colour }}>{pct}%</div>
                      <div className="text-[10px] text-ink-faint">similarity</div>
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => {
                    const next = new URLSearchParams({ q: area.lad_name });
                    if (decisionMode) next.set('mode', decisionMode);
                    navigate(`/results?${next.toString()}`);
                  }}
                  aria-label={`Explore ${area.lad_name}`}
                  className="group inline-flex shrink-0 items-center justify-center gap-1 rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-xs font-semibold text-brand-700 transition-colors hover:bg-brand-100"
                >
                  Explore this benchmark
                  <ArrowRight className="h-3 w-3 transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
                </button>
              </div>

              <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
                {[
                  { label: 'Avg Price', val: fmtCurrency(area.avg_price), ref: fmtCurrency(target.avg_price) },
                  { label: 'Rent / mo', val: fmtCurrency(area.median_rent), ref: fmtCurrency(target.median_rent) },
                  { label: 'Earnings', val: fmtCurrency(area.earnings), ref: fmtCurrency(target.earnings) },
                  { label: 'HPI YoY', val: fmtSignedPercent(area.hpi_yoy), ref: null },
                ].map(({ label, val, ref }) => (
                  <div key={label} className="rounded-lg bg-surface px-2.5 py-2 text-center">
                    <div className="text-[9px] uppercase tracking-wide text-ink-faint">{label}</div>
                    <div className="mt-0.5 text-xs font-bold text-ink">{val}</div>
                    {ref && <div className="text-[9px] leading-tight text-ink-faint">Target: {ref}</div>}
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
