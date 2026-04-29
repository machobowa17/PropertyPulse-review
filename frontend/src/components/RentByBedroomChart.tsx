import { BedDouble } from 'lucide-react';

interface Props {
  // rent per bed (£/month)
  rent1bed?: number | null;
  rent2bed?: number | null;
  rent3bed?: number | null;
  rent4bed?: number | null;
  // yield per bed (%)
  yield1bed?: number | null;
  yield2bed?: number | null;
  yield3bed?: number | null;
  yield4bed?: number | null;
  enhanced?: boolean;
}

const BEDS = [
  { label: '1 bed', rentKey: 'rent1bed' as const, yieldKey: 'yield1bed' as const, colour: '#2563eb' },
  { label: '2 bed', rentKey: 'rent2bed' as const, yieldKey: 'yield2bed' as const, colour: '#7c3aed' },
  { label: '3 bed', rentKey: 'rent3bed' as const, yieldKey: 'yield3bed' as const, colour: '#059669' },
  { label: '4 bed', rentKey: 'rent4bed' as const, yieldKey: 'yield4bed' as const, colour: '#b45309' },
];

function yieldColour(y: number): string {
  if (y >= 6)  return '#22c55e';
  if (y >= 4)  return '#84cc16';
  if (y >= 3)  return '#facc15';
  return '#fb923c';
}

function fmtRent(v: number) {
  return '£' + Math.round(v).toLocaleString('en-GB') + '/mo';
}

export default function RentByBedroomChart({
  rent1bed, rent2bed, rent3bed, rent4bed,
  yield1bed, yield2bed, yield3bed, yield4bed,
  enhanced,
}: Props) {
  const rentVals = { rent1bed, rent2bed, rent3bed, rent4bed };
  const yieldVals = { yield1bed, yield2bed, yield3bed, yield4bed };

  const rows = BEDS.filter(b => rentVals[b.rentKey] != null || yieldVals[b.yieldKey] != null);
  if (rows.length === 0) return null;

  const maxRent = Math.max(...rows.map(b => rentVals[b.rentKey] ?? 0));

  return (
    <div className="bg-surface rounded-xl p-4 space-y-3 mt-2">
      <div className="flex items-center gap-1.5">
        <BedDouble className="w-4 h-4 text-ink-faint" />
        <span className="text-xs font-semibold text-ink-muted uppercase tracking-wide">Rent by bedroom count</span>
      </div>

      <div className="space-y-2.5">
        {rows.map(({ label, rentKey, yieldKey, colour }) => {
          const rent = rentVals[rentKey];
          const yld  = yieldVals[yieldKey];
          const barPct = maxRent > 0 && rent != null ? (rent / maxRent) * 100 : 0;

          return (
            <div key={label} className="flex items-center gap-3">
              {/* Bed label */}
              <div className="w-10 text-[11px] font-semibold text-ink-faint shrink-0">{label}</div>

              {/* Bar + rent */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-0.5">
                  <span className="text-xs font-bold text-ink">
                    {rent != null ? fmtRent(rent) : '—'}
                  </span>
                  {/* Yield badge */}
                  {yld != null && (
                    <span
                      className="text-[10px] font-bold px-1.5 py-0.5 rounded-full"
                      style={{ color: yieldColour(yld), backgroundColor: yieldColour(yld) + '18' }}
                    >
                      {yld.toFixed(1)}% yield
                    </span>
                  )}
                </div>
                <div className="h-2 rounded-full bg-divider overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${barPct}%`,
                      backgroundColor: colour,
                      animation: enhanced ? 'enhanced-bar-fill 0.7s ease-out both' : undefined,
                    }}
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <p className="text-[10px] text-ink-faint">
        Source: VOA Private Rental Market Statistics. Yield = annual rent ÷ avg sale price.
      </p>
    </div>
  );
}
