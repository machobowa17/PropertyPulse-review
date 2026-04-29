import { useMemo, useState } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
} from 'recharts';

interface HpiPoint {
  year: number;
  avg_price: number | null;
  yoy_pct: number | null;
  detached: number | null;
  semi: number | null;
  terraced: number | null;
  flat: number | null;
}

interface Props {
  series: HpiPoint[];
  enhanced?: boolean;
}

type ViewMode = 'price' | 'yoy';

const TYPE_LINES = [
  { key: 'detached', label: 'Detached', colour: '#2563eb' },
  { key: 'semi', label: 'Semi-Detached', colour: '#7c3aed' },
  { key: 'terraced', label: 'Terraced', colour: '#059669' },
  { key: 'flat', label: 'Flat', colour: '#ea580c' },
] as const;

const fmtPrice = (v: number) => {
  if (v >= 1_000_000) return '£' + (v / 1_000_000).toFixed(1) + 'm';
  if (v >= 1_000) return '£' + (v / 1_000).toFixed(0) + 'k';
  return '£' + Math.round(v);
};

const fmtPct = (v: number) => `${v > 0 ? '+' : ''}${v.toFixed(1)}%`;
const fmtAxisPct = (v: number) => `${v > 0 ? '+' : ''}${Number.isInteger(v) ? v : v.toFixed(1)}%`;

/** Generate nice round tick values for a given range */
function niceScale(lo: number, hi: number, targetTicks: number): { min: number; max: number; ticks: number[] } {
  if (lo === hi) { lo -= 1; hi += 1; }
  const range = hi - lo;
  const rawStep = range / Math.max(targetTicks - 1, 1);

  const mag = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const residual = rawStep / mag;
  let niceStep: number;
  if (residual <= 1.5) niceStep = mag;
  else if (residual <= 3.5) niceStep = 2 * mag;
  else if (residual <= 7.5) niceStep = 5 * mag;
  else niceStep = 10 * mag;

  const niceMin = Math.floor(lo / niceStep) * niceStep;
  const niceMax = Math.ceil(hi / niceStep) * niceStep;

  const ticks: number[] = [];
  for (let v = niceMin; v <= niceMax + niceStep * 0.01; v += niceStep) {
    ticks.push(Math.round(v * 1e6) / 1e6);
  }
  return { min: niceMin, max: niceMax, ticks };
}

function CustomTooltip({ active, payload, label, mode }: {
  active?: boolean;
  payload?: Array<{ dataKey: string; name: string; value: number; color: string }>;
  label?: string;
  mode: ViewMode;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-divider bg-white px-3 py-2 shadow-lg text-xs">
      <div className="font-semibold text-ink mb-1">{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: p.color }} />
          <span className="text-ink-muted">{p.name}:</span>
          <span className="font-mono font-semibold text-ink">
            {mode === 'price' ? fmtPrice(p.value) : fmtPct(p.value)}
          </span>
        </div>
      ))}
    </div>
  );
}

/** Compute YoY % change from price series: (current - prior) / prior * 100 */
function computeYoy(series: HpiPoint[]): Record<string, number | null>[] {
  const result: Record<string, number | null>[] = [];
  for (let i = 0; i < series.length; i++) {
    const cur = series[i];
    const prev = i > 0 ? series[i - 1] : null;
    const row: Record<string, number | null> = {
      year: cur.year,
      avg_price: cur.yoy_pct,
    };
    for (const { key } of TYPE_LINES) {
      const curVal = cur[key as keyof HpiPoint] as number | null;
      const prevVal = prev ? (prev[key as keyof HpiPoint] as number | null) : null;
      if (curVal != null && prevVal != null && prevVal !== 0) {
        row[key] = Math.round(((curVal - prevVal) / prevVal) * 1000) / 10;
      } else {
        row[key] = null;
      }
    }
    result.push(row);
  }
  return result.slice(1);
}

export default function HpiTrendChart({ series, enhanced }: Props) {
  const [mode, setMode] = useState<ViewMode>('price');
  const [activeTypes, setActiveTypes] = useState<Set<string>>(new Set(['avg_price']));
  const [hoveredKey, setHoveredKey] = useState<string | null>(null);

  const toggleType = (key: string) => {
    setActiveTypes((prev) => {
      const next = new Set(prev);
      if (key === 'avg_price') {
        if (next.has('avg_price') && next.size === 1) return next;
        return new Set(['avg_price']);
      }
      next.delete('avg_price');
      if (next.has(key)) {
        next.delete(key);
        if (next.size === 0) next.add('avg_price');
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const priceData = useMemo(() =>
    series.map((p) => ({
      year: String(p.year),
      avg_price: p.avg_price,
      detached: p.detached,
      semi: p.semi,
      terraced: p.terraced,
      flat: p.flat,
    })),
  [series]);

  const yoyData = useMemo(() =>
    computeYoy(series).map((p) => ({
      year: String(p.year),
      avg_price: p.avg_price,
      detached: p.detached,
      semi: p.semi,
      terraced: p.terraced,
      flat: p.flat,
    })),
  [series]);

  // Scale from currently visible series only — fits the data the user is looking at.
  const stableScale = useMemo(() => {
    const source = mode === 'price' ? priceData : yoyData;
    const visibleKeys = Array.from(activeTypes);
    const vals: number[] = [];
    for (const row of source) {
      for (const key of visibleKeys) {
        const v = row[key as keyof typeof row];
        if (v != null && typeof v === 'number' && !isNaN(v)) vals.push(v);
      }
    }
    if (!vals.length) return niceScale(0, 100, 5);
    const lo = Math.min(...vals);
    const hi = Math.max(...vals);
    return niceScale(mode === 'price' ? Math.max(0, lo) : lo, hi, 5);
  }, [mode, priceData, yoyData, activeTypes]);

  const chartData = mode === 'price' ? priceData : yoyData;

  return (
    <div className="space-y-3">
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3">
        {/* View mode toggle */}
        <div className="flex rounded-lg border border-divider overflow-hidden">
          <button
            onClick={() => setMode('price')}
            className={`px-2.5 py-1 text-[11px] font-medium transition-colors ${
              mode === 'price'
                ? 'bg-brand-600 text-white'
                : 'bg-surface text-ink-muted hover:bg-surface-warm'
            }`}
          >
            Price
          </button>
          <button
            onClick={() => setMode('yoy')}
            className={`px-2.5 py-1 text-[11px] font-medium transition-colors border-l border-divider ${
              mode === 'yoy'
                ? 'bg-brand-600 text-white'
                : 'bg-surface text-ink-muted hover:bg-surface-warm'
            }`}
          >
            YoY %
          </button>
        </div>

        {/* Type filter toggle (multi-select) */}
        <div className="flex rounded-lg border border-divider overflow-hidden">
          <button
            onClick={() => toggleType('avg_price')}
            className={`px-2.5 py-1 text-[11px] font-medium transition-colors ${
              activeTypes.has('avg_price')
                ? 'bg-brand-600 text-white'
                : 'bg-surface text-ink-muted hover:bg-surface-warm'
            }`}
          >
            All Types
          </button>
          {TYPE_LINES.map(({ key, label, colour }) => (
            <button
              key={key}
              onClick={() => toggleType(key)}
              className={`px-2.5 py-1 text-[11px] font-medium transition-colors border-l border-divider ${
                activeTypes.has(key)
                  ? 'text-white'
                  : 'bg-surface text-ink-muted hover:bg-surface-warm'
              }`}
              style={activeTypes.has(key) ? { backgroundColor: colour } : undefined}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      <div className="h-[220px]" role="img" aria-label="Line chart showing house price index trend">
        <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
          <LineChart
            data={chartData}
            margin={{ top: 8, right: 8, bottom: 0, left: 8 }}
            onMouseMove={(e: { activeTooltipIndex?: number }) => {
              if (!enhanced) return;
              // Track which series is being hovered for dimming
            }}
            onMouseLeave={() => enhanced && setHoveredKey(null)}
          >
            {enhanced && (
              <defs>
                <linearGradient id="hpi-grad-avg" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#374151" stopOpacity={0.15} />
                  <stop offset="100%" stopColor="#374151" stopOpacity={0} />
                </linearGradient>
                {TYPE_LINES.map(({ key, colour }) => (
                  <linearGradient key={`hpi-grad-${key}`} id={`hpi-grad-${key}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={colour} stopOpacity={0.15} />
                    <stop offset="100%" stopColor={colour} stopOpacity={0} />
                  </linearGradient>
                ))}
              </defs>
            )}
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="year" tick={{ fontSize: 11 }} />
            <YAxis
              domain={[stableScale.min, stableScale.max]}
              ticks={stableScale.ticks}
              tick={{ fontSize: 11 }}
              tickFormatter={mode === 'price' ? fmtPrice : fmtAxisPct}
              width={mode === 'price' ? 62 : 55}
              allowDataOverflow
            />
            <Tooltip content={<CustomTooltip mode={mode} />} />
            {mode === 'yoy' && stableScale.min < 0 && stableScale.max > 0 && (
              <ReferenceLine y={0} stroke="#9ca3af" strokeDasharray="3 3" />
            )}
            {enhanced && mode === 'price' && activeTypes.has('avg_price') && (
              <Area type="monotone" dataKey="avg_price" stroke="none" fill="url(#hpi-grad-avg)" fillOpacity={1} connectNulls isAnimationActive animationDuration={700} animationEasing="ease-out" />
            )}
            {enhanced && mode === 'price' && TYPE_LINES.map(({ key }) =>
              activeTypes.has(key) ? (
                <Area key={`area-${key}`} type="monotone" dataKey={key} stroke="none" fill={`url(#hpi-grad-${key})`} fillOpacity={1} connectNulls isAnimationActive animationDuration={700} animationEasing="ease-out" />
              ) : null,
            )}
            {activeTypes.has('avg_price') && (
              <Line
                dataKey="avg_price"
                name="All Types"
                stroke="#374151"
                strokeWidth={2.5}
                dot={{ r: 2.5 }}
                activeDot={{ r: 4 }}
                connectNulls
                isAnimationActive={enhanced}
                animationDuration={enhanced ? 700 : 0}
                animationEasing="ease-out"
              />
            )}
            {TYPE_LINES.map(({ key, label, colour }) =>
              activeTypes.has(key) ? (
                <Line
                  key={key}
                  dataKey={key}
                  name={label}
                  stroke={colour}
                  strokeWidth={2}
                  dot={{ r: 2 }}
                  activeDot={{ r: 4 }}
                  connectNulls
                  isAnimationActive={enhanced}
                  animationDuration={enhanced ? 700 : 0}
                  animationEasing="ease-out"
                />
              ) : null,
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
