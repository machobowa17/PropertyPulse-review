import { useMemo } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from 'recharts';
import type { DistrictPriceResponse } from '../api/client';

const TYPE_COLOURS: Record<string, string> = {
  Detached: '#2563eb',
  'Semi-Detached': '#7c3aed',
  Terraced: '#059669',
  Flat: '#ea580c',
};

interface Props {
  data: DistrictPriceResponse;
}

export default function DistrictPriceHistoryChart({ data }: Props) {
  const chartData = useMemo(() => {
    const byYear: Record<string, Record<string, number>> = {};
    for (const [typeName, points] of Object.entries(data.by_type)) {
      for (const point of points) {
        if (!byYear[point.year]) byYear[point.year] = {};
        if (point.avg_price) byYear[point.year][typeName] = point.avg_price;
      }
    }
    return Object.entries(byYear)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([year, values]) => ({ year, ...values }));
  }, [data]);

  const types = Object.keys(data.by_type).filter((t) => Object.keys(TYPE_COLOURS).includes(t));

  if (chartData.length < 2) return null;

  const fmtGBP = (v: number) => '£' + v.toLocaleString('en-GB', { maximumFractionDigits: 0 });

  return (
    <div className="bg-surface rounded-xl p-4 space-y-3">
      <h4 className="text-sm font-semibold text-ink">
        {data.district} — Price by Property Type
      </h4>
      <div className="h-[280px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-divider, #e5e7eb)" />
            <XAxis
              dataKey="year"
              tick={{ fontSize: 11, fill: '#9ca3af' }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: '#9ca3af' }}
              tickFormatter={(v) => '£' + (v / 1000).toFixed(0) + 'k'}
              tickLine={false}
              axisLine={false}
              width={58}
            />
            <Tooltip
              formatter={(value, name) => [fmtGBP(Number(value)), String(name)]}
              labelStyle={{ fontWeight: 600, color: '#111827' }}
              contentStyle={{ borderRadius: 12, border: '1px solid #e5e7eb', fontSize: 13 }}
            />
            <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
            {types.map((typeName) => (
              <Line
                key={typeName}
                type="monotone"
                dataKey={typeName}
                stroke={TYPE_COLOURS[typeName] ?? '#6b7280'}
                strokeWidth={2}
                dot={{ r: 2.5 }}
                activeDot={{ r: 4.5 }}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
