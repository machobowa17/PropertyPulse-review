import { useState } from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';

interface TrendPoint {
  year: number;
  new_builds: number;
  total: number;
  pct: number;
}

interface Props {
  trend: TrendPoint[];
  enhanced?: boolean;
}

export default function NewBuildTrendChart({ trend, enhanced }: Props) {
  const [hoveredPoint, setHoveredPoint] = useState<TrendPoint | null>(null);
  if (!trend || trend.length === 0) return null;

  return (
    <div className="bg-surface rounded-xl p-3 space-y-1 mt-2">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-ink-muted">New Build % of Sales by Year</h4>
        {enhanced && hoveredPoint && (
          <div className="flex items-center gap-2 text-[11px] font-mono tabular-nums">
            <span className="font-semibold text-brand-600">{hoveredPoint.year}</span>
            <span className="text-ink">{hoveredPoint.new_builds} of {hoveredPoint.total} sales</span>
            <span className="font-semibold text-purple-600">{hoveredPoint.pct}%</span>
          </div>
        )}
      </div>
      <div className="h-[180px]" role="img" aria-label="Bar chart showing new build percentage of sales by year">
        <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
          <BarChart
            data={trend}
            margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
            barSize={14}
            onMouseMove={enhanced ? ((state: Record<string, unknown>) => {
              const ap = state.activePayload as Array<{ payload: TrendPoint }> | undefined;
              if (ap?.[0]) setHoveredPoint(ap[0].payload);
            }) as never : undefined}
            onMouseLeave={enhanced ? (() => setHoveredPoint(null)) as never : undefined}
          >
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
            <XAxis
              dataKey="year"
              tick={{ fontSize: 10, fill: '#9ca3af' }}
              tickLine={false}
              axisLine={false}
              interval={Math.max(0, Math.floor(trend.length / 10) - 1)}
            />
            <YAxis
              tick={{ fontSize: 11, fill: '#9ca3af' }}
              tickLine={false}
              axisLine={false}
              width={34}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip
              content={enhanced ? () => null : ({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const d = payload[0].payload as TrendPoint;
                return (
                  <div className="bg-white rounded-xl border border-divider shadow-md px-3 py-2 text-xs">
                    <div className="font-semibold text-ink">{d.year}</div>
                    <div className="text-ink-muted mt-0.5">
                      {d.new_builds} of {d.total} sales ({d.pct}%)
                    </div>
                  </div>
                );
              }}
              cursor={{ fill: 'rgba(0,0,0,0.04)' }}
            />
            <Bar
              dataKey="pct"
              fill="#8b5cf6"
              radius={[2, 2, 0, 0]}
              isAnimationActive={enhanced}
              animationDuration={enhanced ? 700 : 0}
              animationEasing="ease-out"
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
