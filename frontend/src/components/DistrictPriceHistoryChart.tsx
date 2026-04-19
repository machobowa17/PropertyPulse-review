import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import type { PriceByTypeResponse, PriceHistoryPoint, BedroomBreakdownPoint } from '../api/client';

const TYPE_COLOURS: Record<string, string> = {
  Detached: '#2563eb',
  'Semi-Detached': '#7c3aed',
  Terraced: '#059669',
  Flat: '#ea580c',
};

const fmtAxis = (v: number) => {
  if (v >= 1_000_000) return '£' + (v / 1_000_000).toFixed(1) + 'm';
  if (v >= 1_000) return '£' + (v / 1_000).toFixed(0) + 'k';
  return '£' + Math.round(v);
};

function LineSwatch({ color, dash, opacity = 1, width = 2 }: { color: string; dash?: string; opacity?: number; width?: number }) {
  return (
    <svg width="22" height="8" className="shrink-0">
      <line x1="0" y1="4" x2="22" y2="4" stroke={color} strokeWidth={width} strokeDasharray={dash} strokeOpacity={opacity} />
    </svg>
  );
}

interface Props {
  data: PriceByTypeResponse;
  overallLocal?: PriceHistoryPoint[];
  overallRegional?: PriceHistoryPoint[];
  regionalName?: string;
  areaName?: string;
  byBedrooms?: BedroomBreakdownPoint[];
  priceField?: 'avg_price' | 'median_price' | 'avg_ppsf';
}

const BEDROOM_COLOURS: Record<number, string> = {
  1: '#06b6d4',
  2: '#8b5cf6',
  3: '#f59e0b',
  4: '#ef4444',
  5: '#10b981',
};

// Layout values defined ONCE — used both in Recharts props and in proximity calculation.
// Nothing is derived from magic numbers; everything comes from these or measured DOM size.
const LC_MARGIN = { top: 8, right: 8, bottom: 0, left: 8 } as const;
const Y_AXIS_W  = 62;
const X_AXIS_H  = 20;

function CustomTooltip({ active, payload, label, activeKey, fmtGBP }: {
  active?: boolean;
  payload?: Array<{ dataKey: string; name: string; value: number; payload: Record<string, unknown> }>;
  label?: string;
  activeKey: string | null;
  fmtGBP: (v: number) => string;
}) {
  if (!active || !payload?.length) return null;
  const item = activeKey ? payload.find((p) => p.dataKey === activeKey) : payload[0];
  if (!item || item.value == null) return null;
  const txn = item.payload?.[`__txn_${item.dataKey}`] as number | undefined;
  return (
    <div className="rounded-xl border border-divider bg-white px-3 py-2 shadow-md text-[13px] pointer-events-none">
      <div className="text-[11px] text-ink-faint mb-1">{label}</div>
      <div className="font-bold text-ink">{fmtGBP(Number(item.value))}</div>
      <div className="text-[11px] text-ink-muted mt-0.5">{item.name}</div>
      {txn != null && <div className="text-[11px] text-ink-faint mt-0.5">{txn.toLocaleString('en-GB')} {txn === 1 ? 'transaction' : 'transactions'}</div>}
    </div>
  );
}

export default function DistrictPriceHistoryChart({ data, overallLocal, overallRegional, regionalName, areaName, byBedrooms, priceField = 'avg_price' }: Props) {
  const localLabel  = areaName     ?? 'Local';
  const parentLabel = regionalName ?? 'Parent';

  const [showLocalByType,  setShowLocalByType]  = useState(true);
  const [showLocalAvg,     setShowLocalAvg]     = useState(true);
  const [showParentByType, setShowParentByType] = useState(true);
  const [showParentAvg,    setShowParentAvg]    = useState(true);
  const [showBedrooms,     setShowBedrooms]     = useState(false);
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [hiddenSeries, setHiddenSeries] = useState<Set<string>>(new Set());
  const toggleSeries = (key: string) => setHiddenSeries(prev => {
    const next = new Set(prev);
    next.has(key) ? next.delete(key) : next.add(key);
    return next;
  });

  // Measure the actual rendered container so we never guess at pixel dimensions
  const containerRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState({ w: 0, h: 0 });
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const obs = new ResizeObserver(() => setDims({ w: el.offsetWidth, h: el.offsetHeight }));
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const chartData = useMemo(() => {
    const byYear: Record<string, Record<string, number>> = {};

    for (const [typeName, points] of Object.entries(data.by_type)) {
      for (const point of points) {
        if (!byYear[point.year]) byYear[point.year] = {};
        const v = point[priceField];
        if (v) {
          byYear[point.year][typeName] = v;
          byYear[point.year][`__txn_${typeName}`] = point.transactions;
        }
      }
    }
    if (overallLocal) {
      for (const point of overallLocal) {
        if (!byYear[point.year]) byYear[point.year] = {};
        const v = point[priceField];
        if (v) {
          byYear[point.year]['__local_avg'] = v;
          byYear[point.year]['__txn___local_avg'] = point.transactions;
        }
      }
    }
    if (data.parent_by_type) {
      for (const [typeName, points] of Object.entries(data.parent_by_type)) {
        for (const point of points) {
          if (!byYear[point.year]) byYear[point.year] = {};
          const v = point[priceField];
          if (v) {
            byYear[point.year][`__p_${typeName}`] = v;
            byYear[point.year][`__txn___p_${typeName}`] = point.transactions;
          }
        }
      }
    }
    if (overallRegional) {
      for (const point of overallRegional) {
        if (!byYear[point.year]) byYear[point.year] = {};
        const v = point[priceField];
        if (v) {
          byYear[point.year]['__parent_avg'] = v;
          byYear[point.year]['__txn___parent_avg'] = point.transactions;
        }
      }
    }
    if (byBedrooms) {
      for (const point of byBedrooms) {
        if (!byYear[point.year]) byYear[point.year] = {};
        if (point.avg_price) {
          byYear[point.year][`__bed_${point.bedrooms}`] = point.avg_price;
          byYear[point.year][`__txn___bed_${point.bedrooms}`] = point.transaction_count;
        }
      }
    }

    return Object.entries(byYear)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([year, values]) => ({ year, ...values }));
  }, [data, overallLocal, overallRegional, byBedrooms, priceField]);

  // Y domain set explicitly so we control the exact scale used in proximity math
  const yDomain = useMemo((): [number, number] => {
    const vals = chartData.flatMap((d) =>
      Object.entries(d)
        .filter(([k]) => k !== 'year' && !k.startsWith('__txn_'))
        .map(([, v]) => Number(v))
        .filter((v) => !isNaN(v) && v > 0),
    );
    if (!vals.length) return [0, 1];
    const lo = Math.min(...vals);
    const hi = Math.max(...vals);
    const pad = (hi - lo) * 0.06;
    return [Math.max(0, lo - pad), hi + pad];
  }, [chartData]);

  // 2D proximity: search every (year × series) data point, pick the one closest
  // to the actual cursor in pixel space. Uses measured dims + the same layout
  // constants passed to the Recharts props below — no independent magic numbers.
  // In Recharts v3, state.chartX/chartY are not populated — use native event coords instead.
  const handleMouseMove = (_state: any, nativeEvent: any) => {
    if (!dims.w || !dims.h) return;
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const clientX = nativeEvent?.clientX ?? nativeEvent?.nativeEvent?.clientX;
    const clientY = nativeEvent?.clientY ?? nativeEvent?.nativeEvent?.clientY;
    if (clientX == null || clientY == null) return;
    const cx = clientX - rect.left;
    const cy = clientY - rect.top;

    const plotW = dims.w - LC_MARGIN.left - LC_MARGIN.right - Y_AXIS_W;
    const plotH = dims.h - LC_MARGIN.top  - LC_MARGIN.bottom - X_AXIS_H;
    const [dMin, dMax] = yDomain;
    const yRange = dMax - dMin || 1;
    const n = chartData.length;

    let best: string | null = null;
    let bestDist = Infinity;

    chartData.forEach((point, i) => {
      const px = LC_MARGIN.left + Y_AXIS_W + (n > 1 ? (i / (n - 1)) * plotW : plotW / 2);
      Object.entries(point).forEach(([key, val]) => {
        if (key === 'year' || key.startsWith('__txn_') || val == null) return;
        const v = Number(val);
        if (!v) return;
        const py = LC_MARGIN.top + ((dMax - v) / yRange) * plotH;
        const dist = Math.hypot(px - cx, py - cy);
        if (dist < bestDist) { bestDist = dist; best = key; }
      });
    });

    if (best !== activeKey) setActiveKey(best);
  };

  const localTypes  = Object.keys(data.by_type).filter((t) => Object.keys(TYPE_COLOURS).includes(t));
  const parentTypes = data.parent_by_type
    ? Object.keys(data.parent_by_type).filter((t) => Object.keys(TYPE_COLOURS).includes(t))
    : [];
  const bedroomNums = byBedrooms
    ? [...new Set(byBedrooms.map(p => p.bedrooms))].sort((a, b) => a - b)
    : [];

  if (chartData.length < 2) return null;

  const fmtGBP = priceField === 'avg_ppsf'
    ? (v: number) => '£' + Math.round(v).toLocaleString('en-GB') + '/sqft'
    : (v: number) => '£' + v.toLocaleString('en-GB', { maximumFractionDigits: 0 });

  const hasParentByType = parentTypes.length > 0;
  const hasParentAvg    = !!overallRegional && overallRegional.length > 0;
  const hasLocalAvg     = !!overallLocal    && overallLocal.length    > 0;
  const hasBedrooms     = bedroomNums.length > 0;
  const hasParent       = hasParentByType || hasParentAvg;

  const metricLabel = priceField === 'median_price' ? 'Median' : priceField === 'avg_ppsf' ? 'Avg Price/Sqft' : 'Average';
  const pills = [
    { label: `${localLabel}, Combined ${metricLabel}`,  active: showLocalAvg,     toggle: () => setShowLocalAvg(p => !p) },
    { label: `${localLabel}, ${metricLabel} by Type`,   active: showLocalByType,  toggle: () => setShowLocalByType(p => !p) },
    ...(hasBedrooms     ? [{ label: `${localLabel}, By Bedrooms (est.)`,    active: showBedrooms,     toggle: () => setShowBedrooms(p => !p) }] : []),
    ...(hasParentAvg    ? [{ label: `${parentLabel}, Combined ${metricLabel}`, active: showParentAvg,    toggle: () => setShowParentAvg(p => !p) }] : []),
    ...(hasParentByType ? [{ label: `${parentLabel}, ${metricLabel} by Type`,  active: showParentByType, toggle: () => setShowParentByType(p => !p) }] : []),
  ];

  const TYPE_ORDER = ['Detached', 'Semi-Detached', 'Terraced', 'Flat'];

  return (
    <div className="bg-surface rounded-xl p-4 space-y-3">
      <h4 className="text-sm font-semibold text-ink">
        {priceField === 'avg_ppsf' ? 'Price per Sqft History' : `${metricLabel} Sale Price History`}
        {chartData.length > 0 && (
          <span className="text-[11px] font-normal text-ink-faint"> (since {chartData[0].year})</span>
        )}
      </h4>

      <div className="flex flex-wrap gap-1.5">
        {pills.map(({ label, active, toggle }) => (
          <button
            key={label}
            onClick={toggle}
            className={`px-2.5 py-1 rounded-full text-[11px] font-medium transition-all border ${
              active
                ? 'bg-brand-50 text-brand-700 border-brand-200'
                : 'bg-white text-ink-faint border-divider opacity-50'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ref on the wrapper lets ResizeObserver give us real pixel dimensions */}
      <div ref={containerRef} className="h-[260px]">
        <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
          <LineChart
            data={chartData}
            margin={LC_MARGIN}
            onMouseMove={handleMouseMove}
            onMouseLeave={() => setActiveKey(null)}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-divider, #e5e7eb)" />
            <XAxis
              dataKey="year"
              height={X_AXIS_H}
              tick={{ fontSize: 11, fill: '#9ca3af' }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              domain={yDomain}
              width={Y_AXIS_W}
              tick={{ fontSize: 11, fill: '#9ca3af' }}
              tickFormatter={fmtAxis}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              content={<CustomTooltip activeKey={activeKey} fmtGBP={fmtGBP} />}
              cursor={{ stroke: '#e5e7eb', strokeWidth: 1 }}
              allowEscapeViewBox={{ x: false, y: false }}
              isAnimationActive={false}
              offset={16}
            />

            {showLocalByType && localTypes.filter(t => !hiddenSeries.has(t)).map((typeName) => (
              <Line
                key={`l_${typeName}`}
                type="monotone"
                dataKey={typeName}
                name={`${localLabel}: ${typeName}`}
                stroke={TYPE_COLOURS[typeName] ?? '#6b7280'}
                strokeWidth={2}
                dot={{ r: 2.5 }}
                activeDot={{ r: 4.5 }}
                connectNulls
              />
            ))}

            {showLocalAvg && hasLocalAvg && !hiddenSeries.has('__local_avg') && (
              <Line
                type="monotone"
                dataKey="__local_avg"
                name={`${localLabel}: All types`}
                stroke="#1e293b"
                strokeWidth={2}
                strokeDasharray="6 3"
                dot={{ r: 2 }}
                activeDot={{ r: 4 }}
                connectNulls
              />
            )}

            {showParentByType && parentTypes.filter(t => !hiddenSeries.has(`__p_${t}`)).map((typeName) => (
              <Line
                key={`p_${typeName}`}
                type="monotone"
                dataKey={`__p_${typeName}`}
                name={`${parentLabel}: ${typeName}`}
                stroke={TYPE_COLOURS[typeName] ?? '#6b7280'}
                strokeWidth={1.5}
                strokeDasharray="8 4"
                strokeOpacity={0.5}
                dot={false}
                activeDot={{ r: 3 }}
                connectNulls
              />
            ))}

            {showParentAvg && hasParentAvg && !hiddenSeries.has('__parent_avg') && (
              <Line
                type="monotone"
                dataKey="__parent_avg"
                name={`${parentLabel}: All types`}
                stroke="#9ca3af"
                strokeWidth={1.5}
                strokeDasharray="4 4"
                strokeOpacity={0.7}
                dot={false}
                activeDot={{ r: 3 }}
                connectNulls
              />
            )}

            {showBedrooms && bedroomNums.filter(n => !hiddenSeries.has(`__bed_${n}`)).map((n) => (
              <Line
                key={`__bed_${n}`}
                type="monotone"
                dataKey={`__bed_${n}`}
                name={`${n} bed (est.)`}
                stroke={BEDROOM_COLOURS[n] ?? '#6b7280'}
                strokeWidth={2}
                strokeDasharray="4 2"
                dot={{ r: 2 }}
                activeDot={{ r: 4 }}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Compact 2-row legend */}
      <div className="border-t border-divider/50 pt-2 space-y-1.5 text-[11px]">
        <div className="flex items-center flex-wrap gap-x-3 gap-y-1">
          <span className="text-[10px] font-semibold text-ink-faint uppercase tracking-wide whitespace-nowrap shrink-0">{localLabel}</span>
          {TYPE_ORDER.filter(t => localTypes.includes(t)).map(t => (
            <button key={t} type="button" onClick={() => toggleSeries(t)} className={`flex items-center gap-1 whitespace-nowrap cursor-pointer transition-opacity ${hiddenSeries.has(t) ? 'opacity-30' : ''}`}>
              <LineSwatch color={TYPE_COLOURS[t]} />
              <span className="text-ink-muted">{t}</span>
            </button>
          ))}
          {hasLocalAvg && (
            <button type="button" onClick={() => toggleSeries('__local_avg')} className={`flex items-center gap-1 whitespace-nowrap cursor-pointer transition-opacity ${hiddenSeries.has('__local_avg') ? 'opacity-30' : ''}`}>
              <LineSwatch color="#1e293b" dash="6 3" />
              <span className="text-ink-muted">All types</span>
            </button>
          )}
        </div>

        {hasBedrooms && showBedrooms && (
          <div className="flex items-center flex-wrap gap-x-3 gap-y-1">
            <span className="text-[10px] font-semibold text-ink-faint uppercase tracking-wide whitespace-nowrap shrink-0">Bedrooms (est.)</span>
            {bedroomNums.map(n => (
              <button key={n} type="button" onClick={() => toggleSeries(`__bed_${n}`)} className={`flex items-center gap-1 whitespace-nowrap cursor-pointer transition-opacity ${hiddenSeries.has(`__bed_${n}`) ? 'opacity-30' : ''}`}>
                <LineSwatch color={BEDROOM_COLOURS[n] ?? '#6b7280'} dash="4 2" />
                <span className="text-ink-muted">{n} bed</span>
              </button>
            ))}
          </div>
        )}

        {hasParent && (
          <div className="flex items-center flex-wrap gap-x-3 gap-y-1">
            <span className="text-[10px] font-semibold text-ink-faint uppercase tracking-wide whitespace-nowrap shrink-0">{parentLabel}</span>
            {TYPE_ORDER.filter(t => parentTypes.includes(t)).map(t => (
              <button key={t} type="button" onClick={() => toggleSeries(`__p_${t}`)} className={`flex items-center gap-1 whitespace-nowrap cursor-pointer transition-opacity ${hiddenSeries.has(`__p_${t}`) ? 'opacity-30' : ''}`}>
                <LineSwatch color={TYPE_COLOURS[t]} dash="8 4" opacity={0.5} width={1.5} />
                <span className="text-ink-faint">{t}</span>
              </button>
            ))}
            {hasParentAvg && (
              <button type="button" onClick={() => toggleSeries('__parent_avg')} className={`flex items-center gap-1 whitespace-nowrap cursor-pointer transition-opacity ${hiddenSeries.has('__parent_avg') ? 'opacity-30' : ''}`}>
                <LineSwatch color="#9ca3af" dash="4 4" opacity={0.7} width={1.5} />
                <span className="text-ink-faint">All types</span>
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
