import { useMemo } from 'react';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip } from 'recharts';

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
  enhanced?: boolean;
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

// IMD domain score national ranges (approx) — used to normalise to 0–100
// Higher raw score = more deprived, so we invert for the radar (higher = better)
const DOMAINS = [
  { key: 'income',     label: 'Income',      min: 0, max: 0.55 },
  { key: 'employment', label: 'Employment',  min: 0, max: 0.45 },
  { key: 'education',  label: 'Education',   min: 0, max: 90 },
  { key: 'health',     label: 'Health',       min: -3, max: 3 },
  { key: 'crime',      label: 'Crime',        min: -3, max: 3 },
  { key: 'barriers',   label: 'Barriers',    min: 0, max: 50 },
  { key: 'living_env', label: 'Living Env',  min: 0, max: 70 },
] as const;

function normalise(val: number, min: number, max: number): number {
  // Clamp to range, map to 0–100, invert (100 = least deprived)
  const clamped = Math.max(min, Math.min(max, val));
  return Math.round(100 - ((clamped - min) / (max - min)) * 100);
}

export default function ImdDeprivationBlock({
  decile, rank, parentAvgDecile,
  income, employment, education, health, crime, barriers, livingEnvironment,
  enhanced,
}: Props) {
  const cfg = DECILE_CONFIG[decile] ?? DECILE_CONFIG[5];
  const barPct = (decile / 10) * 100;

  const subScores: Record<string, number | null | undefined> = {
    income, employment, education, health, crime, barriers, living_env: livingEnvironment,
  };

  const radarData = useMemo(() => {
    return DOMAINS
      .filter(d => subScores[d.key] != null)
      .map(d => ({
        domain: d.label,
        score: normalise(subScores[d.key]!, d.min, d.max),
        raw: subScores[d.key]!,
      }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [income, employment, education, health, crime, barriers, livingEnvironment]);

  const hasSubDomains = radarData.length > 0;

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
            style={{
              width: `${barPct}%`,
              backgroundColor: cfg.colour,
              animation: enhanced ? 'enhanced-bar-fill 0.7s ease-out both' : undefined,
            }}
          />
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

      {/* ─── Radar chart — 7 domain scores ─── */}
      {hasSubDomains && (
        <div>
          <div className="text-[11px] text-ink-faint uppercase tracking-wide font-medium mb-2">Domain breakdown</div>
          <div className="mx-auto" style={{ width: '100%', maxWidth: 340, height: 260 }}>
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart cx="50%" cy="50%" outerRadius="72%" data={radarData}>
                <PolarGrid stroke="#e5e7eb" />
                <PolarAngleAxis
                  dataKey="domain"
                  tick={{ fontSize: 11, fill: '#6b7280' }}
                />
                <Radar
                  name="Score"
                  dataKey="score"
                  stroke={cfg.colour}
                  fill={cfg.colour}
                  fillOpacity={0.25}
                  strokeWidth={2}
                  isAnimationActive={enhanced}
                  animationDuration={enhanced ? 700 : 0}
                  animationEasing="ease-out"
                />
                <Tooltip
                  content={({ payload }) => {
                    if (!payload?.[0]) return null;
                    const d = payload[0].payload as { domain: string; score: number; raw: number };
                    return (
                      <div className="bg-white shadow-lg border border-divider rounded-lg px-3 py-2 text-xs">
                        <div className="font-semibold text-ink">{d.domain}</div>
                        <div className="text-ink-muted mt-0.5">
                          Score: {d.score}/100 <span className="text-ink-faint">(raw: {d.raw.toFixed(3)})</span>
                        </div>
                        <div className="text-[10px] text-ink-faint mt-0.5">
                          100 = least deprived, 0 = most deprived
                        </div>
                      </div>
                    );
                  }}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
          {/* Domain scores table */}
          <div className="grid grid-cols-2 gap-1.5 mt-2">
            {radarData.map(({ domain, score }) => (
              <div key={domain} className="flex items-center gap-2 bg-white border border-divider rounded-lg px-2.5 py-1.5">
                <div className="flex-1 text-[11px] text-ink-muted">{domain}</div>
                <div
                  className="text-xs font-bold"
                  style={{ color: score >= 60 ? '#16a34a' : score >= 40 ? '#eab308' : '#dc2626' }}
                >
                  {score}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <p className="text-[10px] text-ink-faint">
        Source: MHCLG English Indices of Deprivation 2019. Decile 1 = most deprived 10% nationally.
        Radar scores normalised: 100 = least deprived, 0 = most deprived.
      </p>
    </div>
  );
}
