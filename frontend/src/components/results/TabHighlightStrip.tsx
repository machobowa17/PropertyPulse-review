/**
 * TabHighlightStrip (P2) — Compact 3-stat row between tab explainer and PersonaScoreCard.
 * Shows the 3 highest persona-weighted metrics for the current tab.
 */
import type { Metric, PersonaId } from '../../types';
import { formatValue } from '../../utils/tabs';
import { PERSONA_METRIC_WEIGHTS } from '../../utils/personalization';

interface Props {
  metrics: Metric[];
  persona: PersonaId;
  parentName: string;
  enhanced?: boolean;
}

function comparisonLabel(m: Metric, parentName: string): { text: string; className: string } | null {
  if (!m.comparison_flag || m.comparison_flag === 'equal_to_parent') return null;
  const dir = m.interpretation_direction;
  const isHigher = m.comparison_flag === 'higher_than_parent';
  const label = isHigher ? `Above ${parentName}` : `Below ${parentName}`;

  if (!dir || dir === 'neutral') {
    return { text: label, className: 'text-slate-500' };
  }

  const isGood =
    (dir === 'lower_is_better' && !isHigher) ||
    (dir === 'higher_is_better' && isHigher);

  return {
    text: label,
    className: isGood ? 'text-emerald-600' : 'text-amber-600',
  };
}

export default function TabHighlightStrip({ metrics, persona, parentName, enhanced }: Props) {
  const withValue = metrics.filter(m => m.local_value != null);
  if (withValue.length === 0) return null;

  // Pick top 3 by persona weight
  const sorted = [...withValue].sort((a, b) => {
    const wa = PERSONA_METRIC_WEIGHTS[a.id]?.[persona] ?? 1;
    const wb = PERSONA_METRIC_WEIGHTS[b.id]?.[persona] ?? 1;
    return wb - wa;
  });
  const highlights = sorted.slice(0, 3);
  if (highlights.length === 0) return null;

  return (
    <div className="grid grid-cols-3 gap-2">
      {highlights.map((m, i) => {
        const comp = comparisonLabel(m, parentName);
        const localNum = typeof m.local_value === 'number' ? m.local_value : null;
        const parentNum = typeof m.parent_value === 'number' ? m.parent_value : null;
        const showMiniBar = enhanced && localNum != null && parentNum != null && localNum > 0;
        const barMax = showMiniBar ? Math.max(localNum, parentNum) * 1.2 : 1;
        return (
          <div
            key={m.id}
            className="rounded-xl bg-white border border-divider px-3 py-2.5 shadow-sm"
            style={enhanced ? { animation: `enhanced-fade-in 0.4s ease-out ${i * 80}ms both` } : undefined}
          >
            <div className="text-[10px] uppercase tracking-wider text-ink-faint font-medium truncate">
              {m.registry?.short_label || m.name}
            </div>
            <div className="text-lg font-bold text-ink tabular-nums leading-tight mt-0.5">
              {formatValue(m.local_value as number | string | null, m.unit)}
            </div>
            {comp && (
              <div className={`text-[10px] font-medium mt-0.5 ${comp.className}`}>
                {comp.text}
              </div>
            )}
            {showMiniBar && (
              <div className="relative mt-1.5 h-1 rounded-full bg-ink-faint/15 overflow-hidden">
                <div
                  className="absolute inset-y-0 left-0 rounded-full bg-brand-500/60"
                  style={{ width: `${(localNum / barMax) * 100}%`, animation: 'enhanced-bar-fill 0.7s ease-out both' }}
                />
                <div
                  className="absolute top-[-1px] w-0.5 h-[calc(100%+2px)] bg-amber-500 rounded-full"
                  style={{ left: `${(parentNum / barMax) * 100}%` }}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
