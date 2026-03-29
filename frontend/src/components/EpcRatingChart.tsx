import { Flame, Zap, Droplet, Building2, Wind } from 'lucide-react';

interface Props {
  pctA?: number | null;
  pctB?: number | null;
  pctC?: number | null;
  pctD?: number | null;
  pctE?: number | null;
  pctF?: number | null;
  pctG?: number | null;
  avgScore?: number | null;
  parentAvgScore?: number | null;
  parentRatings?: { a?: number | null; b?: number | null; c?: number | null; d?: number | null; e?: number | null; f?: number | null; g?: number | null } | null;
  heatGasPct?: number | null;
  heatElectricPct?: number | null;
  heatOilPct?: number | null;
  heatDistrictPct?: number | null;
  heatOtherPct?: number | null;
  heatNonePct?: number | null;
  cPlusPct?: number | null;
  parentCPlusPct?: number | null;
}

const BAND_COLOURS: Record<string, string> = {
  A: '#22c55e',
  B: '#84cc16',
  C: '#a3e635',
  D: '#facc15',
  E: '#fb923c',
  F: '#f87171',
  G: '#ef4444',
};

const HEAT_ITEMS = [
  { key: 'gas', label: 'Gas', icon: Flame, colour: '#2563eb' },
  { key: 'electric', label: 'Electric', icon: Zap, colour: '#7c3aed' },
  { key: 'oil', label: 'Oil', icon: Droplet, colour: '#ea580c' },
  { key: 'district', label: 'District', icon: Building2, colour: '#0891b2' },
  { key: 'other', label: 'Other', icon: Wind, colour: '#6b7280' },
] as const;

export default function EpcRatingChart({
  pctA, pctB, pctC, pctD, pctE, pctF, pctG,
  avgScore, parentAvgScore,
  parentRatings,
  heatGasPct, heatElectricPct, heatOilPct, heatDistrictPct, heatOtherPct, heatNonePct,
  cPlusPct, parentCPlusPct,
}: Props) {
  const bands: { label: string; local: number; parent: number | null }[] = [
    { label: 'A', local: pctA ?? 0, parent: parentRatings?.a ?? null },
    { label: 'B', local: pctB ?? 0, parent: parentRatings?.b ?? null },
    { label: 'C', local: pctC ?? 0, parent: parentRatings?.c ?? null },
    { label: 'D', local: pctD ?? 0, parent: parentRatings?.d ?? null },
    { label: 'E', local: pctE ?? 0, parent: parentRatings?.e ?? null },
    { label: 'F', local: pctF ?? 0, parent: parentRatings?.f ?? null },
    { label: 'G', local: pctG ?? 0, parent: parentRatings?.g ?? null },
  ].filter((b) => b.local > 0 || (b.parent ?? 0) > 0);

  const hasHeating = heatGasPct != null || heatElectricPct != null;

  return (
    <div className="bg-surface rounded-xl p-4 space-y-4 mt-2">
      {/* ─── Header stats ─── */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex-1 min-w-[120px]">
          <div className="text-[11px] text-ink-faint uppercase tracking-wide font-medium">Avg energy score</div>
          <div className="flex items-baseline gap-2 mt-0.5">
            <span className="text-2xl font-bold text-ink">{avgScore != null ? Math.round(avgScore) : '—'}</span>
            {parentAvgScore != null && (
              <span className="text-xs text-ink-faint">area avg {Math.round(parentAvgScore)}</span>
            )}
          </div>
        </div>
        {cPlusPct != null && (
          <div className="flex-1 min-w-[120px]">
            <div className="text-[11px] text-ink-faint uppercase tracking-wide font-medium">Rated C or above</div>
            <div className="flex items-baseline gap-2 mt-0.5">
              <span className="text-2xl font-bold text-ink">{cPlusPct.toFixed(1)}%</span>
              {parentCPlusPct != null && (
                <span className="text-xs text-ink-faint">area {parentCPlusPct.toFixed(1)}%</span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ─── A–G rating bars ─── */}
      <div>
        <h4 className="text-xs font-semibold text-ink-muted mb-2">EPC Rating Distribution</h4>
        <div className="space-y-1.5">
          {bands.map(({ label, local, parent }) => (
            <div key={label} className="flex items-center gap-2">
              <div
                className="w-6 h-5 rounded text-[10px] font-bold flex items-center justify-center text-white shrink-0"
                style={{ backgroundColor: BAND_COLOURS[label] }}
              >
                {label}
              </div>
              <div className="flex-1 relative h-4 bg-divider rounded-full overflow-hidden">
                <div
                  className="absolute left-0 top-0 h-full rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(local, 100)}%`, backgroundColor: BAND_COLOURS[label], opacity: 0.85 }}
                />
                {/* Parent comparison tick */}
                {parent != null && parent > 0 && (
                  <div
                    className="absolute top-0 h-full w-0.5 bg-ink-muted opacity-40"
                    style={{ left: `${Math.min(parent, 100)}%` }}
                    title={`Area avg: ${parent.toFixed(1)}%`}
                  />
                )}
              </div>
              <div className="w-10 text-right text-xs font-medium text-ink tabular-nums shrink-0">
                {local.toFixed(1)}%
              </div>
            </div>
          ))}
        </div>
        {parentRatings && (
          <p className="text-[10px] text-ink-faint mt-1.5">Grey tick = area average</p>
        )}
      </div>

      {/* ─── Heating breakdown ─── */}
      {hasHeating && (
        <div>
          <h4 className="text-xs font-semibold text-ink-muted mb-2">Heating Type</h4>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {HEAT_ITEMS.map(({ key, label, icon: Icon, colour }) => {
              const pct = key === 'gas' ? heatGasPct
                : key === 'electric' ? heatElectricPct
                : key === 'oil' ? heatOilPct
                : key === 'district' ? heatDistrictPct
                : heatOtherPct;
              if (pct == null || pct < 0.5) return null;
              return (
                <div key={key} className="flex items-center gap-2 p-2 bg-white rounded-lg border border-divider">
                  <Icon className="w-4 h-4 shrink-0" style={{ color: colour }} />
                  <div className="flex-1 min-w-0">
                    <div className="text-[10px] text-ink-faint">{label}</div>
                    <div className="text-sm font-semibold text-ink">{pct.toFixed(1)}%</div>
                  </div>
                </div>
              );
            })}
            {heatNonePct != null && heatNonePct >= 0.5 && (
              <div className="flex items-center gap-2 p-2 bg-white rounded-lg border border-divider">
                <div className="w-4 h-4 shrink-0 rounded-full bg-divider" />
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] text-ink-faint">No heating</div>
                  <div className="text-sm font-semibold text-ink">{heatNonePct.toFixed(1)}%</div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
