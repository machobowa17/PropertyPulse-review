interface Props {
  decile: number;           // 1–10
  rank?: number | null;
  parentAvgDecile?: number | null;
  income?: number | null;
  employment?: number | null;
  education?: number | null;
  health?: number | null;
  crime?: number | null;
  barriers?: number | null;
  livingEnvironment?: number | null;
}

// Decile 1 = most deprived, 10 = least deprived
const DECILE_CONFIG: Record<number, { colour: string; bg: string; label: string }> = {
  1:  { colour: '#dc2626', bg: '#fef2f2', label: 'Very high deprivation' },
  2:  { colour: '#ea580c', bg: '#fff7ed', label: 'High deprivation' },
  3:  { colour: '#f97316', bg: '#fff7ed', label: 'High deprivation' },
  4:  { colour: '#f59e0b', bg: '#fffbeb', label: 'Above average deprivation' },
  5:  { colour: '#eab308', bg: '#fefce8', label: 'Slightly above average' },
  6:  { colour: '#84cc16', bg: '#f7fee7', label: 'Slightly below average' },
  7:  { colour: '#22c55e', bg: '#f0fdf4', label: 'Below average deprivation' },
  8:  { colour: '#16a34a', bg: '#f0fdf4', label: 'Low deprivation' },
  9:  { colour: '#15803d', bg: '#f0fdf4', label: 'Low deprivation' },
  10: { colour: '#166534', bg: '#f0fdf4', label: 'Very low deprivation' },
};

const SUB_DOMAINS = [
  { key: 'income',           label: 'Income' },
  { key: 'employment',       label: 'Employment' },
  { key: 'education',        label: 'Education' },
  { key: 'health',           label: 'Health' },
  { key: 'crime',            label: 'Crime' },
  { key: 'barriers',         label: 'Barriers' },
  { key: 'living_env',       label: 'Living Env' },
] as const;

export default function ImdDeprivationBlock({
  decile, rank, parentAvgDecile,
  income, employment, education, health, crime, barriers, livingEnvironment,
}: Props) {
  const cfg = DECILE_CONFIG[decile] ?? DECILE_CONFIG[5];
  // Progress bar: decile 1 = 10% filled (most deprived), decile 10 = 100% filled
  const barPct = (decile / 10) * 100;

  const subScores: Record<string, number | null | undefined> = {
    income, employment, education, health, crime, barriers, living_env: livingEnvironment,
  };

  return (
    <div className="bg-surface rounded-xl p-4 space-y-4 mt-2">
      {/* ─── Decile block header ─── */}
      <div className="flex items-center gap-4">
        <div
          className="w-20 h-20 rounded-2xl flex flex-col items-center justify-center shrink-0 shadow-sm"
          style={{ backgroundColor: cfg.colour }}
        >
          <span className="text-4xl font-black text-white leading-none">{decile}</span>
          <span className="text-[10px] text-white/80 font-semibold uppercase tracking-wide mt-0.5">of 10</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-base font-bold text-ink">{cfg.label}</div>
          <div className="text-xs text-ink-faint mt-0.5">
            Decile {decile} — {decile === 1 ? 'most' : decile === 10 ? 'least' : 'nationally ranked'} deprived
          </div>
          {rank != null && (
            <div className="text-xs text-ink-faint mt-0.5">
              Rank <span className="font-semibold text-ink">{rank.toLocaleString('en-GB')}</span>
              <span className="text-ink-faint"> / 32,844</span>
            </div>
          )}
          {parentAvgDecile != null && (
            <div className="text-xs text-ink-faint mt-1">
              Area avg decile: <span className="font-semibold text-ink">{parentAvgDecile.toFixed(1)}</span>
            </div>
          )}
        </div>
      </div>

      {/* ─── Progress bar ─── */}
      <div>
        <div className="flex justify-between text-[10px] text-ink-faint mb-1">
          <span>Most deprived</span>
          <span>Least deprived</span>
        </div>
        <div className="relative h-3 rounded-full overflow-hidden" style={{ backgroundColor: '#e5e7eb' }}>
          <div
            className="h-full rounded-full transition-all"
            style={{ width: `${barPct}%`, backgroundColor: cfg.colour }}
          />
          {/* Tick marks for each decile */}
          {Array.from({ length: 9 }, (_, i) => (
            <div
              key={i}
              className="absolute top-0 h-full w-px bg-white/60"
              style={{ left: `${(i + 1) * 10}%` }}
            />
          ))}
        </div>
        <div className="flex justify-between mt-0.5">
          {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((d) => (
            <span
              key={d}
              className={`text-[9px] font-medium w-[10%] text-center ${d === decile ? 'text-ink font-bold' : 'text-ink-faint'}`}
            >
              {d}
            </span>
          ))}
        </div>
      </div>

      {/* ─── Sub-domain scores ─── */}
      {(income != null || employment != null) && (
        <div>
          <div className="text-[11px] text-ink-faint uppercase tracking-wide font-medium mb-2">Domain scores</div>
          <div className="grid grid-cols-2 gap-1.5">
            {SUB_DOMAINS.map(({ key, label }) => {
              const val = subScores[key];
              if (val == null) return null;
              // Scores are 0–1 roughly; display as percentage-style bar
              const pct = Math.min(100, val * 100);
              return (
                <div key={key} className="bg-white border border-divider rounded-xl p-2">
                  <div className="text-[10px] text-ink-faint mb-1">{label}</div>
                  <div className="h-1.5 rounded-full bg-divider overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${pct}%`, backgroundColor: cfg.colour }}
                    />
                  </div>
                  <div className="text-xs font-semibold text-ink mt-1">{val.toFixed(3)}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <p className="text-[10px] text-ink-faint">
        Source: MHCLG English Indices of Deprivation 2019. Decile 1 = most deprived 10% nationally.
      </p>
    </div>
  );
}
