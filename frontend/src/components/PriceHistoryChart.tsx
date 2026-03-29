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
import type { PriceHistoryPoint } from '../api/client';

interface Props {
  local: PriceHistoryPoint[];
  regional: PriceHistoryPoint[];
  regionalName: string;
}

export default function PriceHistoryChart({ local, regional, regionalName }: Props) {
  // Merge local and regional data by year
  const merged = useMemo(() => {
    const byYear: Record<string, { year: string; local?: number; regional?: number }> = {};
    for (const row of local) {
      byYear[row.year] = { year: row.year, local: row.avg_price };
    }
    for (const row of regional) {
      if (!byYear[row.year]) byYear[row.year] = { year: row.year };
      byYear[row.year].regional = row.avg_price;
    }
    return Object.values(byYear).sort((a, b) => a.year.localeCompare(b.year));
  }, [local, regional]);

  const fmtGBP = (v: number) => '£' + v.toLocaleString('en-GB', { maximumFractionDigits: 0 });

  if (merged.length < 2) return null;

  return (
    <div className="bg-surface rounded-xl p-4 space-y-3">
      <h4 className="text-sm font-semibold text-ink">Price History</h4>
      <div className="h-[260px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={merged} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
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
              width={55}
            />
            <Tooltip
              formatter={(value, name) => [fmtGBP(Number(value)), name === 'local' ? 'Local' : regionalName]}
              labelStyle={{ fontWeight: 600, color: '#111827' }}
              contentStyle={{ borderRadius: 12, border: '1px solid #e5e7eb', fontSize: 13 }}
            />
            <Legend
              formatter={(value: string) => (value === 'local' ? 'Local (LSOA)' : regionalName)}
              iconType="circle"
              wrapperStyle={{ fontSize: 12 }}
            />
            <Line
              type="monotone"
              dataKey="local"
              stroke="#2563eb"
              strokeWidth={2.5}
              dot={{ r: 3, fill: '#2563eb' }}
              activeDot={{ r: 5 }}
            />
            <Line
              type="monotone"
              dataKey="regional"
              stroke="#9ca3af"
              strokeWidth={1.5}
              strokeDasharray="4 4"
              dot={{ r: 2, fill: '#9ca3af' }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
