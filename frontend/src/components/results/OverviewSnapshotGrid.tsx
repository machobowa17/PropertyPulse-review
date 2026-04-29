/**
 * OverviewSnapshotGrid — 10-metric responsive grid for the Overview tab.
 * Each card shows: icon, short label, bold value, comparison arrow + "vs {parent}".
 */
import {
  PoundSterling, Receipt, Train, Wifi, ShieldAlert,
  Cloud, Clock, Scale, Users, GraduationCap,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { Metric } from '../../types';
import { formatValue } from '../../utils/tabs';

interface Props {
  metrics: Metric[];
  parentName: string;
  enhanced?: boolean;
}

const ICON_MAP: Record<string, LucideIcon> = {
  overview_avg_price: PoundSterling,
  overview_council_tax: Receipt,
  overview_nearest_station: Train,
  overview_broadband: Wifi,
  overview_crime_rate: ShieldAlert,
  overview_air_quality: Cloud,
  overview_median_age: Clock,
  overview_deprivation: Scale,
  overview_pop_density: Users,
  overview_degree_educated: GraduationCap,
};

function comparisonArrow(m: Metric): { text: string; className: string } | null {
  if (!m.comparison_flag || m.comparison_flag === 'equal_to_parent') return null;
  const dir = m.interpretation_direction;
  const isHigher = m.comparison_flag === 'higher_than_parent';
  const arrow = isHigher ? '\u2191' : '\u2193';

  if (!dir || dir === 'neutral') {
    return { text: arrow, className: 'text-slate-500' };
  }

  const isGood =
    (dir === 'lower_is_better' && !isHigher) ||
    (dir === 'higher_is_better' && isHigher);

  return {
    text: arrow,
    className: isGood ? 'text-emerald-600' : 'text-amber-600',
  };
}

export default function OverviewSnapshotGrid({ metrics, parentName, enhanced }: Props) {
  const visible = metrics.filter(m => m.local_value != null);
  if (visible.length === 0) return null;

  return (
    <div>
      <h3 className="text-sm font-semibold text-ink mb-2">Area Snapshot</h3>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5">
      {visible.map((m, i) => {
        const Icon = ICON_MAP[m.id] || PoundSterling;
        const arrow = comparisonArrow(m);
        const shortLabel = m.registry?.short_label || m.name;

        // Mini HBar data for enhanced mode
        const localNum = typeof m.local_value === 'number' ? m.local_value : null;
        const parentNum = typeof m.parent_value === 'number' ? m.parent_value : null;
        const showMiniBar = enhanced && localNum != null && parentNum != null && localNum > 0;
        const barMax = showMiniBar ? Math.max(localNum, parentNum) * 1.2 : 1;

        return (
          <div
            key={m.id}
            className="rounded-xl bg-white border border-divider px-3.5 py-3 shadow-sm hover:shadow-md transition-shadow"
            style={enhanced ? { animation: `enhanced-fade-in 0.4s ease-out ${i * 50}ms both` } : undefined}
          >
            <div className="flex items-center gap-2 mb-1.5">
              <div className="w-6 h-6 rounded-md bg-indigo-50 flex items-center justify-center shrink-0">
                <Icon size={13} className="text-indigo-600" />
              </div>
              <span className="text-[10px] uppercase tracking-wider text-ink-faint font-medium truncate">
                {shortLabel}
              </span>
            </div>
            <div className="text-lg font-bold text-ink tabular-nums leading-tight">
              {formatValue(m.local_value as number | string | null, m.unit)}
            </div>
            {arrow && (
              <div className="flex items-center gap-1 mt-1">
                <span className={`text-xs font-semibold ${arrow.className}`}>{arrow.text}</span>
                <span className="text-[10px] text-ink-faint">vs {parentName}</span>
              </div>
            )}
            {!arrow && m.parent_value != null && (
              <div className="flex items-center gap-1 mt-1">
                <span className="text-[10px] text-ink-faint">
                  {parentName}: {formatValue(m.parent_value as number | string | null, m.unit)}
                </span>
              </div>
            )}
            {showMiniBar && (
              <div className="relative mt-2 h-1.5 rounded-full bg-ink-faint/15 overflow-hidden">
                <div
                  className="absolute inset-y-0 left-0 rounded-full bg-brand-500/60"
                  style={{
                    width: `${(localNum / barMax) * 100}%`,
                    animation: 'enhanced-bar-fill 0.7s ease-out both',
                  }}
                />
                <div
                  className="absolute top-[-1px] w-0.5 h-[calc(100%+2px)] bg-amber-500 rounded-full"
                  style={{ left: `${(parentNum / barMax) * 100}%` }}
                  title={`${parentName}: ${formatValue(m.parent_value as number | string | null, m.unit)}`}
                />
              </div>
            )}
          </div>
        );
      })}
      </div>
    </div>
  );
}
