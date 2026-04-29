interface Props {
  bands: Record<string, number | null>;   // band_a … band_i
  parents: Record<string, number | null>; // parent_a … parent_i
}

const BANDS = [
  { key: 'band_a', parent: 'parent_a', label: 'A', ratio: 6 / 9 },
  { key: 'band_b', parent: 'parent_b', label: 'B', ratio: 7 / 9 },
  { key: 'band_c', parent: 'parent_c', label: 'C', ratio: 8 / 9 },
  { key: 'band_d', parent: 'parent_d', label: 'D', ratio: 9 / 9 },
  { key: 'band_e', parent: 'parent_e', label: 'E', ratio: 11 / 9 },
  { key: 'band_f', parent: 'parent_f', label: 'F', ratio: 13 / 9 },
  { key: 'band_g', parent: 'parent_g', label: 'G', ratio: 15 / 9 },
  { key: 'band_h', parent: 'parent_h', label: 'H', ratio: 18 / 9 },
  { key: 'band_i', parent: 'parent_i', label: 'I', ratio: 21 / 9 },
];

function fmt(v: number | null | undefined): string {
  if (v == null) return '—';
  return '£' + Math.round(v).toLocaleString('en-GB');
}

export default function CouncilTaxBandGrid({ bands, parents }: Props) {
  const visibleBands = BANDS.filter(({ key, parent }) => bands[key] != null || parents[parent] != null);
  const maxVal = Math.max(0, ...visibleBands.map((b) => bands[b.key] ?? 0));

  return (
    <div className="bg-surface rounded-xl p-4 space-y-3 mt-2">
      <div className="text-[11px] text-ink-faint uppercase tracking-wide font-medium">Annual charge by band</div>

      <div className="space-y-2">
        {visibleBands.map(({ key, parent: parentKey, label }) => {
          const val = bands[key];
          const parentVal = parents[parentKey];
          const barPct = maxVal > 0 && val != null ? (val / maxVal) * 100 : 0;
          const diff = val != null && parentVal != null ? val - parentVal : null;
          const isHigher = diff != null && diff > 10;
          const isLower = diff != null && diff < -10;

          return (
            <div key={key} className="flex items-center gap-3">
              <div className="w-6 h-6 rounded-lg bg-brand/10 flex items-center justify-center shrink-0">
                <span className="text-[11px] font-black text-brand">{label}</span>
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-0.5">
                  <span className="text-xs font-semibold text-ink">{fmt(val)}</span>
                  {diff != null && (
                    <span className={`text-[10px] font-medium ${isHigher ? 'text-signal-red' : isLower ? 'text-signal-green' : 'text-ink-faint'}`}>
                      {isHigher ? '+' : ''}{fmt(diff)} vs area
                    </span>
                  )}
                </div>
                <div className="relative h-2 rounded-full bg-divider overflow-hidden">
                  <div
                    className="h-full rounded-full bg-brand-500 opacity-70"
                    style={{ width: `${barPct}%` }}
                  />
                  {parentVal != null && maxVal > 0 && (
                    <div
                      className="absolute top-0 h-full w-0.5 bg-ink/30"
                      style={{ left: `${(parentVal / maxVal) * 100}%` }}
                    />
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex items-center gap-1.5 text-[10px] text-ink-faint">
        <div className="w-3 h-3 flex items-center justify-center">
          <div className="w-0.5 h-3 bg-ink/30 rounded" />
        </div>
        <span>Vertical line = area average</span>
      </div>

      <p className="text-[10px] text-ink-faint">
        Source: England VOA council-tax levels and Welsh StatsWales council-tax levels. Band D remains the standard reference band.
      </p>
    </div>
  );
}
