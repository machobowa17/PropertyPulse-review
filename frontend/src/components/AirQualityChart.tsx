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
  ReferenceLine,
} from 'recharts';
import type { AqHistoryPoint } from '../api/client';

interface Props {
  local: AqHistoryPoint[];
  national: AqHistoryPoint[];
  ladName: string;
  pollutant?: 'pm25' | 'no2';
}

const WHO_LIMITS: Record<string, number> = { pm25: 5, no2: 10 };
const LABELS: Record<string, string> = { pm25: 'PM2.5', no2: 'NO₂' };

export default function AirQualityChart({ local, national, ladName, pollutant = 'pm25' }: Props) {
  const localKey = `local_${pollutant}` as const;
  const nationalKey = `national_${pollutant}` as const;
  const label = LABELS[pollutant];
  const whoLimit = WHO_LIMITS[pollutant];

  const merged = useMemo(() => {
    const byYear: Record<number, Record<string, unknown>> = {};
    for (const row of local) {
      byYear[row.year] = {
        year: String(row.year),
        local_pm25: row.pm25_ugm3 ?? undefined,
        local_no2: row.no2_ugm3 ?? undefined,
      };
    }
    for (const row of national) {
      if (!byYear[row.year]) byYear[row.year] = { year: String(row.year) };
      byYear[row.year].national_pm25 = row.pm25_ugm3 ?? undefined;
      byYear[row.year].national_no2 = row.no2_ugm3 ?? undefined;
    }
    return Object.values(byYear).sort((a, b) =>
      String(a.year).localeCompare(String(b.year)),
    );
  }, [local, national]);

  // Only render if we have at least 2 data points for the selected pollutant
  const hasData = merged.filter((d) => d[localKey] != null).length >= 2;
  if (!hasData) return null;

  return (
    <div className="bg-surface rounded-xl p-4 space-y-3">
      <h4 className="text-sm font-semibold text-ink">Air Quality Trend ({label})</h4>
      <p className="text-xs text-ink-muted">WHO guideline: {whoLimit} µg/m³ annual mean</p>
      <div className="h-[260px]" role="img" aria-label="Line chart showing air quality trend over time">
        <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
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
              tickFormatter={(v) => v + ''}
              tickLine={false}
              axisLine={false}
              width={35}
              domain={[0, 'auto']}
              label={{ value: 'µg/m³', angle: -90, position: 'insideLeft', style: { fontSize: 10, fill: '#9ca3af' } }}
            />
            <Tooltip
              formatter={(value, name) => {
                const labels: Record<string, string> = {
                  [localKey]: `${ladName} ${label}`,
                  [nationalKey]: `National ${label}`,
                };
                return [Number(value).toFixed(1) + ' µg/m³', labels[String(name)] || String(name)];
              }}
              labelStyle={{ fontWeight: 600, color: '#111827' }}
              contentStyle={{ borderRadius: 12, border: '1px solid #e5e7eb', fontSize: 13 }}
            />
            <Legend
              formatter={(value: string) => {
                const labels: Record<string, string> = {
                  [localKey]: `${ladName}`,
                  [nationalKey]: 'National avg',
                };
                return labels[value] || value;
              }}
              iconType="circle"
              wrapperStyle={{ fontSize: 12 }}
            />
            <ReferenceLine
              y={whoLimit}
              stroke="#ef4444"
              strokeDasharray="6 3"
              label={{ value: 'WHO limit', position: 'right', style: { fontSize: 10, fill: '#ef4444' } }}
            />
            <Line
              type="monotone"
              dataKey={localKey}
              stroke="#059669"
              strokeWidth={2.5}
              dot={{ r: 3, fill: '#059669' }}
              activeDot={{ r: 5 }}
            />
            <Line
              type="monotone"
              dataKey={nationalKey}
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
