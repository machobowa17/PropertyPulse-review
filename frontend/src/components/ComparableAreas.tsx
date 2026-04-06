import { useNavigate } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import type { ComparableArea } from '../api/client';

interface Props {
  target: { lad_name: string; avg_price: number; median_rent: number; earnings: number };
  comparable: ComparableArea[];
}

function fmt(n: number | null | undefined) {
  if (n == null) return 'N/A';
  return '£' + n.toLocaleString('en-GB', { maximumFractionDigits: 0 });
}

function similarityColour(pct: number): string {
  if (pct >= 75) return '#22c55e';
  if (pct >= 50) return '#84cc16';
  if (pct >= 30) return '#facc15';
  return '#fb923c';
}

export default function ComparableAreas({ target, comparable }: Props) {
  const navigate = useNavigate();

  if (comparable.length === 0) return null;

  return (
    <div className="space-y-2 mt-2">
      <p className="text-xs text-ink-muted px-1">
        LADs most similar to <span className="font-semibold text-ink">{target.lad_name}</span> based
        on price, rent, earnings, air quality and price growth.
      </p>

      {comparable.map((area) => {
        const pct = Math.round(area.similarity_pct ?? 0);
        const colour = similarityColour(pct);

        return (
          <div
            key={area.lad_code}
            className="bg-white rounded-xl border border-divider p-3 flex flex-col gap-2 hover:shadow-sm transition-shadow"
          >
            {/* Top row: name + similarity + explore */}
            <div className="flex items-center gap-3">
              <div className="flex-1 min-w-0">
                <span className="text-sm font-semibold text-ink truncate block">{area.lad_name}</span>
              </div>
              {/* Similarity badge */}
              <div className="flex items-center gap-1.5 shrink-0">
                <span className="text-xs font-bold" style={{ color: colour }}>{pct}%</span>
                <span className="text-[10px] text-ink-faint">similar</span>
              </div>
              {/* Explore button */}
              <button
                onClick={() => navigate(`/results?q=${encodeURIComponent(area.lad_name)}`)}
                aria-label={`Explore ${area.lad_name}`}
                className="group flex items-center gap-1 px-2.5 py-1 rounded-lg bg-brand-50 border border-brand-200
                           text-xs font-semibold text-brand-700 hover:bg-brand-100 transition-colors shrink-0"
              >
                Explore
                <ArrowRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" aria-hidden="true" />
              </button>
            </div>

            {/* Similarity progress bar */}
            <div className="flex items-center gap-2">
              <div className="flex-1 h-1.5 rounded-full bg-divider overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${pct}%`, backgroundColor: colour }}
                />
              </div>
            </div>

            {/* Key stats row */}
            <div className="grid grid-cols-4 gap-1 text-center">
              {[
                { label: 'Avg Price', val: fmt(area.avg_price), ref: fmt(target.avg_price) },
                { label: 'Rent/mo', val: fmt(area.median_rent), ref: fmt(target.median_rent) },
                { label: 'Earnings', val: fmt(area.earnings), ref: fmt(target.earnings) },
                { label: 'HPI YoY', val: area.hpi_yoy == null ? 'N/A' : (area.hpi_yoy > 0 ? '+' : '') + area.hpi_yoy.toFixed(1) + '%', ref: null },
              ].map(({ label, val, ref }) => (
                <div key={label} className="bg-surface rounded-lg px-1.5 py-1.5">
                  <div className="text-[9px] text-ink-faint uppercase tracking-wide leading-tight">{label}</div>
                  <div className="text-xs font-bold text-ink mt-0.5">{val}</div>
                  {ref && <div className="text-[9px] text-ink-faint leading-tight">vs {ref}</div>}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
