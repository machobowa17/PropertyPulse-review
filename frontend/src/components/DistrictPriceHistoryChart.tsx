import { useEffect, useMemo, useRef, useState } from 'react';
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
import type { PriceByTypeResponse, PriceHistoryPoint, BedroomBreakdownPoint } from '../api/client';

const TYPE_LINES = [
  { key: 'Detached',       label: 'Detached',       colour: '#2563eb' },
  { key: 'Semi-Detached',  label: 'Semi-Detached',  colour: '#7c3aed' },
  { key: 'Terraced',       label: 'Terraced',       colour: '#059669' },
  { key: 'Flat',           label: 'Flat',           colour: '#ea580c' },
] as const;

const BED_LINES = [
  { key: '1', label: '1 bed', colour: '#8b5cf6' },
  { key: '2', label: '2 bed', colour: '#2563eb' },
  { key: '3', label: '3 bed', colour: '#059669' },
  { key: '4', label: '4 bed', colour: '#ea580c' },
  { key: '5', label: '5+ bed', colour: '#dc2626' },
] as const;

const TYPE_COLOUR_MAP: Record<string, string> = Object.fromEntries(
  TYPE_LINES.map((t) => [t.key, t.colour]),
);

const fmtPrice = (v: number) => {
  if (v >= 1_000_000) return '£' + (v / 1_000_000).toFixed(1) + 'm';
  if (v >= 1_000) return '£' + (v / 1_000).toFixed(0) + 'k';
  return '£' + Math.round(v);
};

const fmtPct = (v: number) => `${v > 0 ? '+' : ''}${v.toFixed(1)}%`;

const fmtAxisPct = (v: number) => `${v > 0 ? '+' : ''}${Number.isInteger(v) ? v : v.toFixed(1)}%`;

// Layout constants — shared between Recharts props and proximity math
const LC_MARGIN = { top: 8, right: 8, bottom: 0, left: 8 } as const;
const Y_AXIS_W = 62;
const Y_AXIS_W_PCT = 55;
const X_AXIS_H = 20;

type ViewMode = 'price' | 'yoy';
type Row = Record<string, number | string | null>;

/** Generate nice round tick values for a given range */
function niceScale(lo: number, hi: number, targetTicks: number): { min: number; max: number; ticks: number[] } {
  if (lo === hi) { lo -= 1; hi += 1; }
  const range = hi - lo;
  const rawStep = range / Math.max(targetTicks - 1, 1);

  // Find a "nice" step: 1, 2, 5, 10, 20, 50, 100, 200, 500, ...
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
    ticks.push(Math.round(v * 1e6) / 1e6); // avoid float drift
  }
  return { min: niceMin, max: niceMax, ticks };
}

/** Check if a year string is a real calendar year (4 digits) */
function isCalendarYear(y: string): boolean {
  return /^\d{4}$/.test(y);
}

type Dimension = 'type' | 'bedrooms';

interface Props {
  data: PriceByTypeResponse;
  overallLocal?: PriceHistoryPoint[];
  overallRegional?: PriceHistoryPoint[];
  regionalName?: string;
  areaName?: string;
  priceField?: 'avg_price' | 'median_price' | 'avg_ppsf';
  byBedrooms?: BedroomBreakdownPoint[];
  enhanced?: boolean;
}

function CustomTooltip({ active, payload, label, activeKey, mode, fmtGBP }: {
  active?: boolean;
  payload?: Array<{ dataKey: string; name: string; value: number; color: string; payload: Record<string, unknown> }>;
  label?: string;
  activeKey: string | null;
  mode: ViewMode;
  fmtGBP: (v: number) => string;
}) {
  if (!active || !payload?.length) return null;
  const item = activeKey ? payload.find((p) => p.dataKey === activeKey) : payload[0];
  if (!item || item.value == null) return null;
  const txn = item.payload?.[`__txn_${item.dataKey}`] as number | undefined;
  return (
    <div className="rounded-xl border border-divider bg-white px-3 py-2 shadow-md text-[13px] pointer-events-none">
      <div className="text-[11px] text-ink-faint mb-1">{label}</div>
      <div className="font-bold text-ink">
        {mode === 'price' ? fmtGBP(Number(item.value)) : fmtPct(Number(item.value))}
      </div>
      <div className="text-[11px] text-ink-muted mt-0.5">{item.name}</div>
      {mode === 'price' && txn != null && (
        <div className="text-[11px] text-ink-faint mt-0.5">
          {txn.toLocaleString('en-GB')} {txn === 1 ? 'transaction' : 'transactions'}
        </div>
      )}
    </div>
  );
}

/** Compute YoY % from yearly price data keyed by type */
function computeYoy(
  priceRows: Row[],
  valueKeys: string[],
): Row[] {
  const result: Row[] = [];
  for (let i = 1; i < priceRows.length; i++) {
    const cur = priceRows[i];
    const prev = priceRows[i - 1];
    const row: Row = { year: cur.year };
    for (const key of valueKeys) {
      const curVal = cur[key] as number | undefined;
      const prevVal = prev[key] as number | undefined;
      if (curVal != null && prevVal != null && prevVal !== 0) {
        row[key] = Math.round(((curVal - prevVal) / prevVal) * 1000) / 10;
      } else {
        row[key] = null;
      }
    }
    result.push(row);
  }
  return result;
}

export default function DistrictPriceHistoryChart({
  data,
  overallLocal,
  overallRegional,
  regionalName,
  areaName,
  priceField = 'avg_price',
  byBedrooms,
  enhanced,
}: Props) {
  const localLabel = areaName ?? 'Local';
  const parentLabel = regionalName ?? 'Parent';

  const [showParent, setShowParent] = useState(false);
  const [mode, setMode] = useState<ViewMode>('price');
  const [dimension, setDimension] = useState<Dimension>('type');
  const [activeTypes, setActiveTypes] = useState<Set<string>>(new Set(['__all']));
  const [activeBeds, setActiveBeds] = useState<Set<string>>(new Set(['__all_beds']));
  const [activeKey, setActiveKey] = useState<string | null>(null);

  const hasBedrooms = !!byBedrooms && byBedrooms.length > 0;

  const toggleType = (key: string) => {
    setActiveTypes((prev) => {
      const next = new Set(prev);
      if (key === '__all') {
        if (next.has('__all') && next.size === 1) return next;
        return new Set(['__all']);
      }
      next.delete('__all');
      if (next.has(key)) {
        next.delete(key);
        if (next.size === 0) next.add('__all');
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const toggleBed = (key: string) => {
    setActiveBeds((prev) => {
      const next = new Set(prev);
      if (key === '__all_beds') {
        if (next.has('__all_beds') && next.size === 1) return next;
        return new Set(['__all_beds']);
      }
      next.delete('__all_beds');
      if (next.has(key)) {
        next.delete(key);
        if (next.size === 0) next.add('__all_beds');
      } else {
        next.add(key);
      }
      return next;
    });
  };

  // Build bedroom price data keyed by year
  const bedroomPriceData = useMemo((): Row[] => {
    if (!byBedrooms?.length) return [];
    const byYear: Record<string, Record<string, number>> = {};
    for (const point of byBedrooms) {
      if (!isCalendarYear(point.year)) continue;
      if (!byYear[point.year]) byYear[point.year] = {};
      const bedKey = `bed_${point.bedrooms}`;
      byYear[point.year][bedKey] = point.avg_price;
      byYear[point.year][`__txn_${bedKey}`] = point.transaction_count;
    }
    // Also add __all_beds from overallLocal
    if (overallLocal) {
      for (const point of overallLocal) {
        if (!isCalendarYear(point.year)) continue;
        if (!byYear[point.year]) byYear[point.year] = {};
        const v = point[priceField];
        if (v) {
          byYear[point.year]['__all_beds'] = v;
          byYear[point.year]['__txn___all_beds'] = point.transactions;
        }
      }
    }
    return Object.entries(byYear)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([year, values]): Row => ({ year, ...values }));
  }, [byBedrooms, overallLocal, priceField]);

  const bedroomYoyData = useMemo(() => {
    if (!bedroomPriceData.length) return [];
    const keys = ['__all_beds', ...BED_LINES.map(b => `bed_${b.key}`)];
    return computeYoy(bedroomPriceData, keys);
  }, [bedroomPriceData]);

  // Measure DOM for proximity detection
  const containerRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState({ w: 0, h: 0 });
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const obs = new ResizeObserver(() => setDims({ w: el.offsetWidth, h: el.offsetHeight }));
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // Available types
  const localTypes = Object.keys(data.by_type).filter((t) => t in TYPE_COLOUR_MAP);
  const parentTypes = data.parent_by_type
    ? Object.keys(data.parent_by_type).filter((t) => t in TYPE_COLOUR_MAP)
    : [];
  const hasParentAvg = !!overallRegional && overallRegional.length > 0;
  const hasParent = parentTypes.length > 0 || hasParentAvg;

  // Build price data keyed by year — ONLY calendar years (exclude "Last 12m" etc.)
  const priceData = useMemo((): Row[] => {
    const byYear: Record<string, Record<string, number>> = {};

    // Local by type
    for (const [typeName, points] of Object.entries(data.by_type)) {
      for (const point of points) {
        if (!isCalendarYear(point.year)) continue;
        if (!byYear[point.year]) byYear[point.year] = {};
        const v = point[priceField];
        if (v) {
          byYear[point.year][typeName] = v;
          byYear[point.year][`__txn_${typeName}`] = point.transactions;
        }
      }
    }
    // Local overall
    if (overallLocal) {
      for (const point of overallLocal) {
        if (!isCalendarYear(point.year)) continue;
        if (!byYear[point.year]) byYear[point.year] = {};
        const v = point[priceField];
        if (v) {
          byYear[point.year]['__all'] = v;
          byYear[point.year]['__txn___all'] = point.transactions;
        }
      }
    }
    // Parent by type
    if (data.parent_by_type) {
      for (const [typeName, points] of Object.entries(data.parent_by_type)) {
        for (const point of points) {
          if (!isCalendarYear(point.year)) continue;
          if (!byYear[point.year]) byYear[point.year] = {};
          const v = point[priceField];
          if (v) {
            byYear[point.year][`__p_${typeName}`] = v;
            byYear[point.year][`__txn___p_${typeName}`] = point.transactions;
          }
        }
      }
    }
    // Parent overall
    if (overallRegional) {
      for (const point of overallRegional) {
        if (!isCalendarYear(point.year)) continue;
        if (!byYear[point.year]) byYear[point.year] = {};
        const v = point[priceField];
        if (v) {
          byYear[point.year]['__p___all'] = v;
          byYear[point.year]['__txn___p___all'] = point.transactions;
        }
      }
    }

    return Object.entries(byYear)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([year, values]): Row => ({ year, ...values }));
  }, [data, overallLocal, overallRegional, priceField]);

  // Compute YoY from price data
  const yoyData = useMemo(() => {
    const localValueKeys = ['__all', ...localTypes];
    const parentValueKeys = ['__p___all', ...parentTypes.map((t) => `__p_${t}`)];
    return computeYoy(priceData, [...localValueKeys, ...parentValueKeys]);
  }, [priceData, localTypes, parentTypes]);

  // Y-domain: computed from currently visible lines only, so scale fits what
  // the user is actually looking at. Now that local + parent show simultaneously
  // (rather than toggling), axes don't need to be stable across geo.
  const visibleKeys = useMemo(() => {
    const keys: string[] = [];
    if (dimension === 'bedrooms') {
      for (const bedKey of activeBeds) {
        keys.push(bedKey === '__all_beds' ? '__all_beds' : `bed_${bedKey}`);
      }
    } else {
      for (const typeKey of activeTypes) {
        keys.push(typeKey === '__all' ? '__all' : typeKey);
        if (showParent) {
          keys.push(typeKey === '__all' ? '__p___all' : `__p_${typeKey}`);
        }
      }
    }
    return keys;
  }, [dimension, activeTypes, activeBeds, showParent]);

  const stableScale = useMemo(() => {
    const source = dimension === 'bedrooms'
      ? (mode === 'price' ? bedroomPriceData : bedroomYoyData)
      : (mode === 'price' ? priceData : yoyData);
    const vals: number[] = [];
    for (const row of source) {
      for (const key of visibleKeys) {
        const v = row[key];
        if (v != null && typeof v === 'number' && !isNaN(v)) vals.push(v);
      }
    }
    if (!vals.length) return niceScale(0, 100, 5);
    const lo = Math.min(...vals);
    const hi = Math.max(...vals);
    return niceScale(mode === 'price' ? Math.max(0, lo) : lo, hi, 5);
  }, [mode, dimension, priceData, yoyData, bedroomPriceData, bedroomYoyData, visibleKeys]);

  // Select active data based on mode + active type/bed keys.
  const chartData = useMemo(() => {
    if (dimension === 'bedrooms') {
      const source = mode === 'price' ? bedroomPriceData : bedroomYoyData;
      return source.map((row) => {
        const filtered: Row = { year: row.year };
        for (const bedKey of activeBeds) {
          const dk = bedKey === '__all_beds' ? '__all_beds' : `bed_${bedKey}`;
          if (row[dk] != null) filtered[dk] = row[dk];
          if (row[`__txn_${dk}`] != null) filtered[`__txn_${dk}`] = row[`__txn_${dk}`];
        }
        return filtered;
      });
    }
    const source = mode === 'price' ? priceData : yoyData;
    return source.map((row) => {
      const filtered: Row = { year: row.year };
      for (const typeKey of activeTypes) {
        if (typeKey === '__all') {
          if (row['__all'] != null) filtered['__all'] = row['__all'];
          if (row['__txn___all'] != null) filtered['__txn___all'] = row['__txn___all'];
        } else {
          if (row[typeKey] != null) filtered[typeKey] = row[typeKey];
          if (row[`__txn_${typeKey}`] != null) filtered[`__txn_${typeKey}`] = row[`__txn_${typeKey}`];
        }
        if (showParent) {
          if (typeKey === '__all') {
            if (row['__p___all'] != null) {
              filtered['__p___all'] = row['__p___all'];
              if (row['__txn___p___all'] != null) filtered['__txn___p___all'] = row['__txn___p___all'];
            }
          } else {
            const pk = `__p_${typeKey}`;
            if (row[pk] != null) {
              filtered[pk] = row[pk];
              if (row[`__txn_${pk}`] != null) filtered[`__txn_${pk}`] = row[`__txn_${pk}`];
            }
          }
        }
      }
      return filtered;
    });
  }, [dimension, priceData, yoyData, bedroomPriceData, bedroomYoyData, mode, showParent, activeTypes, activeBeds]);

  const yAxisW = mode === 'price' ? Y_AXIS_W : Y_AXIS_W_PCT;
  const yDomain: [number, number] = [stableScale.min, stableScale.max];

  // 2D proximity hover
  const handleMouseMove = (_state: unknown, nativeEvent: { clientX?: number; clientY?: number; nativeEvent?: { clientX?: number; clientY?: number } }) => {
    if (!dims.w || !dims.h) return;
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const clientX = nativeEvent?.clientX ?? nativeEvent?.nativeEvent?.clientX;
    const clientY = nativeEvent?.clientY ?? nativeEvent?.nativeEvent?.clientY;
    if (clientX == null || clientY == null) return;
    const cx = clientX - rect.left;
    const cy = clientY - rect.top;

    const plotW = dims.w - LC_MARGIN.left - LC_MARGIN.right - yAxisW;
    const plotH = dims.h - LC_MARGIN.top - LC_MARGIN.bottom - X_AXIS_H;
    const [dMin, dMax] = yDomain;
    const yRange = dMax - dMin || 1;
    const n = chartData.length;

    let best: string | null = null;
    let bestDist = Infinity;

    chartData.forEach((point, i) => {
      const px = LC_MARGIN.left + yAxisW + (n > 1 ? (i / (n - 1)) * plotW : plotW / 2);
      Object.entries(point).forEach(([key, val]) => {
        if (key === 'year' || key.startsWith('__txn_') || val == null) return;
        const v = Number(val);
        if (isNaN(v)) return;
        const py = LC_MARGIN.top + ((dMax - v) / yRange) * plotH;
        const dist = Math.hypot(px - cx, py - cy);
        if (dist < bestDist) { bestDist = dist; best = key; }
      });
    });

    if (best !== activeKey) setActiveKey(best);
  };

  if (priceData.length < 2) return null;

  const fmtGBP = priceField === 'avg_ppsf'
    ? (v: number) => '£' + Math.round(v).toLocaleString('en-GB') + '/sqft'
    : (v: number) => '£' + v.toLocaleString('en-GB', { maximumFractionDigits: 0 });

  const metricLabel = priceField === 'median_price' ? 'Median' : priceField === 'avg_ppsf' ? 'Avg Price/Sqft' : 'Average';

  // Build lines for chart
  const lines: Array<{ dataKey: string; name: string; colour: string; dashed?: boolean }> = [];
  if (dimension === 'bedrooms') {
    for (const bedKey of activeBeds) {
      if (bedKey === '__all_beds') {
        lines.push({ dataKey: '__all_beds', name: `${localLabel}: All Beds`, colour: '#374151' });
      } else {
        const cfg = BED_LINES.find(b => b.key === bedKey);
        lines.push({ dataKey: `bed_${bedKey}`, name: `${localLabel}: ${cfg?.label ?? bedKey}`, colour: cfg?.colour ?? '#6b7280' });
      }
    }
  } else {
    for (const typeKey of activeTypes) {
      if (typeKey === '__all') {
        lines.push({ dataKey: '__all', name: `${localLabel}: All Types`, colour: '#374151' });
      } else if (localTypes.includes(typeKey)) {
        lines.push({ dataKey: typeKey, name: `${localLabel}: ${typeKey}`, colour: TYPE_COLOUR_MAP[typeKey] ?? '#6b7280' });
      }
      if (showParent) {
        if (typeKey === '__all' && hasParentAvg) {
          lines.push({ dataKey: '__p___all', name: `${parentLabel}: All Types`, colour: '#374151', dashed: true });
        } else if (typeKey !== '__all' && parentTypes.includes(typeKey)) {
          lines.push({ dataKey: `__p_${typeKey}`, name: `${parentLabel}: ${typeKey}`, colour: TYPE_COLOUR_MAP[typeKey] ?? '#6b7280', dashed: true });
        }
      }
    }
  }

  return (
    <div className="bg-surface rounded-xl p-4 space-y-3">
      <h4 className="text-sm font-semibold text-ink">
        {priceField === 'avg_ppsf' ? 'Price per Sqft History' : `${metricLabel} Sale Price History`}
        {priceData.length > 0 && (
          <span className="text-[11px] font-normal text-ink-faint"> (since {priceData[0].year})</span>
        )}
      </h4>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Geography toggle — only in type dimension */}
        {dimension === 'type' && hasParent && (
          <div className="flex rounded-lg border border-divider overflow-hidden">
            <span className="px-2.5 py-1 text-[11px] font-medium bg-brand-600 text-white">
              {localLabel}
            </span>
            <button
              onClick={() => setShowParent((p) => !p)}
              className={`px-2.5 py-1 text-[11px] font-medium transition-colors border-l border-divider ${
                showParent
                  ? 'bg-brand-600 text-white'
                  : 'bg-surface text-ink-muted hover:bg-surface-warm'
              }`}
            >
              {parentLabel}
            </button>
          </div>
        )}

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

        {/* Dimension toggle: Type vs Bedrooms */}
        {hasBedrooms && (
          <div className="flex rounded-lg border border-divider overflow-hidden">
            <button
              onClick={() => setDimension('type')}
              className={`px-2.5 py-1 text-[11px] font-medium transition-colors ${
                dimension === 'type'
                  ? 'bg-brand-600 text-white'
                  : 'bg-surface text-ink-muted hover:bg-surface-warm'
              }`}
            >
              By Type
            </button>
            <button
              onClick={() => setDimension('bedrooms')}
              className={`px-2.5 py-1 text-[11px] font-medium transition-colors border-l border-divider ${
                dimension === 'bedrooms'
                  ? 'bg-brand-600 text-white'
                  : 'bg-surface text-ink-muted hover:bg-surface-warm'
              }`}
            >
              By Beds
            </button>
          </div>
        )}

        {/* Type filter toggle (multi-select) — shown in type dimension */}
        {dimension === 'type' && (
          <div className="flex rounded-lg border border-divider overflow-hidden">
            <button
              onClick={() => toggleType('__all')}
              className={`px-2.5 py-1 text-[11px] font-medium transition-colors ${
                activeTypes.has('__all')
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
        )}

        {/* Bedroom filter toggle (multi-select) — shown in bedrooms dimension */}
        {dimension === 'bedrooms' && (
          <div className="flex rounded-lg border border-divider overflow-hidden">
            <button
              onClick={() => toggleBed('__all_beds')}
              className={`px-2.5 py-1 text-[11px] font-medium transition-colors ${
                activeBeds.has('__all_beds')
                  ? 'bg-brand-600 text-white'
                  : 'bg-surface text-ink-muted hover:bg-surface-warm'
              }`}
            >
              All Beds
            </button>
            {BED_LINES.map(({ key, label, colour }) => (
              <button
                key={key}
                onClick={() => toggleBed(key)}
                className={`px-2.5 py-1 text-[11px] font-medium transition-colors border-l border-divider ${
                  activeBeds.has(key)
                    ? 'text-white'
                    : 'bg-surface text-ink-muted hover:bg-surface-warm'
                }`}
                style={activeBeds.has(key) ? { backgroundColor: colour } : undefined}
              >
                {label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Chart */}
      <div ref={containerRef} className="h-[260px]" role="img" aria-label="Line chart showing district average sale price history">
        <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
          <LineChart
            data={chartData}
            margin={LC_MARGIN}
            onMouseMove={handleMouseMove}
            onMouseLeave={() => setActiveKey(null)}
          >
            {/* Enhanced mode: gradient defs for area fills */}
            {enhanced && (
              <defs>
                {lines.map(({ dataKey, colour }) => (
                  <linearGradient key={`grad-${dataKey}`} id={`grad-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={colour} stopOpacity={0.18} />
                    <stop offset="100%" stopColor={colour} stopOpacity={0} />
                  </linearGradient>
                ))}
              </defs>
            )}
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
              ticks={stableScale.ticks}
              width={yAxisW}
              tick={{ fontSize: 11, fill: '#9ca3af' }}
              tickFormatter={mode === 'price' ? fmtPrice : fmtAxisPct}
              tickLine={false}
              axisLine={false}
              allowDataOverflow
            />
            <Tooltip
              content={<CustomTooltip activeKey={activeKey} mode={mode} fmtGBP={fmtGBP} />}
              cursor={{ stroke: '#e5e7eb', strokeWidth: 1 }}
              allowEscapeViewBox={{ x: false, y: true }}
              isAnimationActive={false}
              offset={16}
            />
            {mode === 'yoy' && stableScale.min < 0 && stableScale.max > 0 && (
              <ReferenceLine y={0} stroke="#9ca3af" strokeDasharray="3 3" />
            )}
            {/* Enhanced mode: gradient area fills behind lines */}
            {enhanced && mode === 'price' && lines.map(({ dataKey }) => (
              <Area
                key={`area-${dataKey}`}
                type="monotone"
                dataKey={dataKey}
                stroke="none"
                fill={`url(#grad-${dataKey})`}
                fillOpacity={1}
                connectNulls
                isAnimationActive
                animationDuration={700}
                animationEasing="ease-out"
              />
            ))}
            {lines.map(({ dataKey, name, colour, dashed }) => (
              <Line
                key={dataKey}
                type="monotone"
                dataKey={dataKey}
                name={name}
                stroke={colour}
                strokeWidth={dataKey.includes('__all') ? 2.5 : 2}
                strokeDasharray={dashed ? '6 3' : undefined}
                strokeOpacity={
                  enhanced && activeKey
                    ? (dataKey === activeKey ? 1 : 0.3)
                    : (dashed ? 0.7 : 1)
                }
                dot={{ r: dataKey.includes('__all') ? 2.5 : 2 }}
                activeDot={{ r: 4 }}
                connectNulls
                isAnimationActive={enhanced}
                animationDuration={enhanced ? 700 : 0}
                animationEasing="ease-out"
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
