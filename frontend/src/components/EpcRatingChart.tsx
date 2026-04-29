interface Props {
  pctAb?: number | null;
  pctC?: number | null;
  pctD?: number | null;
  pctEg?: number | null;
  avgScore?: number | null;
  parentAvgScore?: number | null;
  parentRatings?: { ab?: number | null; c?: number | null; d?: number | null; eg?: number | null } | null;
  cPlusPct?: number | null;
  parentCPlusPct?: number | null;
  enhanced?: boolean;
}

// Classic UK EPC colour bands
const BANDS = [
  { label: 'A–B', key: 'ab' as const, colour: '#22c55e', range: '81–100' },
  { label: 'C', key: 'c' as const, colour: '#a3e635', range: '69–80' },
  { label: 'D', key: 'd' as const, colour: '#facc15', range: '55–68' },
  { label: 'E–G', key: 'eg' as const, colour: '#ef4444', range: '1–54' },
];

// Score → band label for the pointer
function scoreToBand(score: number): string {
  if (score >= 92) return 'A';
  if (score >= 81) return 'B';
  if (score >= 69) return 'C';
  if (score >= 55) return 'D';
  if (score >= 39) return 'E';
  if (score >= 21) return 'F';
  return 'G';
}

export default function EpcRatingChart({
  pctAb, pctC, pctD, pctEg,
  avgScore, parentAvgScore,
  parentRatings,
  cPlusPct, parentCPlusPct,
  enhanced,
}: Props) {
  const bands: { label: string; local: number; parent: number | null; colour: string; range: string }[] = BANDS.map(b => ({
    label: b.label,
    colour: b.colour,
    range: b.range,
    local: (b.key === 'ab' ? pctAb : b.key === 'c' ? pctC : b.key === 'd' ? pctD : pctEg) ?? 0,
    parent: parentRatings ? (parentRatings[b.key] ?? null) : null,
  })).filter(b => b.local > 0 || (b.parent ?? 0) > 0);

  const band = avgScore != null ? scoreToBand(avgScore) : null;

  return (
    <div className="bg-surface rounded-xl p-4 space-y-4 mt-2">
      {/* ─── Header: score + band + C+ pct ─── */}
      <div className="flex items-center gap-4 flex-wrap">
        {avgScore != null && (
          <div className="flex items-center gap-3">
            {/* EPC arrow badge */}
            <div className="relative w-14 h-14 rounded-xl flex items-center justify-center shadow-sm"
              style={{ backgroundColor: band === 'A' || band === 'B' ? '#22c55e' : band === 'C' ? '#a3e635' : band === 'D' ? '#facc15' : band === 'E' ? '#fb923c' : '#ef4444' }}>
              <span className="text-2xl font-black text-white leading-none">{band}</span>
            </div>
            <div>
              <div className="text-[11px] text-ink-faint uppercase tracking-wide font-medium">Avg energy score</div>
              <div className="flex items-baseline gap-2 mt-0.5">
                <span className="text-2xl font-bold text-ink">{Math.round(avgScore)}</span>
                {parentAvgScore != null && (
                  <span className="text-xs text-ink-faint">area avg {Math.round(parentAvgScore)}</span>
                )}
              </div>
            </div>
          </div>
        )}
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

      {/* ─── Rating distribution bars (classic EPC arrow style) ─── */}
      {bands.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-ink-muted mb-2">EPC Rating Distribution</h4>
          <div className="space-y-1.5">
            {bands.map(({ label, local, parent, colour, range }, idx) => (
              <div key={label} className="flex items-center gap-2">
                {/* Arrow-style band label */}
                <div className="flex items-center shrink-0" style={{ width: 70 }}>
                  <div
                    className="h-6 rounded-l-md flex items-center px-2 text-[10px] font-bold text-white"
                    style={{ backgroundColor: colour, width: 42 }}
                  >
                    {label}
                  </div>
                  <div
                    className="w-0 h-0"
                    style={{
                      borderTop: '12px solid transparent',
                      borderBottom: '12px solid transparent',
                      borderLeft: `8px solid ${colour}`,
                    }}
                  />
                  <span className="text-[9px] text-ink-faint ml-1">{range}</span>
                </div>
                {/* Bar */}
                <div className="flex-1 relative h-5 bg-divider rounded-full overflow-hidden">
                  <div
                    className="absolute left-0 top-0 h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${Math.min(local, 100)}%`,
                      backgroundColor: colour,
                      opacity: 0.85,
                      animation: enhanced ? `enhanced-bar-fill 0.7s ease-out ${idx * 100}ms both` : undefined,
                    }}
                  />
                  {parent != null && parent > 0 && (
                    <div
                      className="absolute top-0 h-full w-0.5 bg-ink-muted opacity-40"
                      style={{ left: `${Math.min(parent, 100)}%` }}
                      title={`Area avg: ${parent.toFixed(1)}%`}
                    />
                  )}
                </div>
                <div className="w-12 text-right text-xs font-medium text-ink tabular-nums shrink-0">
                  {local.toFixed(1)}%
                </div>
              </div>
            ))}
          </div>
          {parentRatings && (
            <p className="text-[10px] text-ink-faint mt-1.5">Grey tick = area average</p>
          )}
        </div>
      )}
    </div>
  );
}
