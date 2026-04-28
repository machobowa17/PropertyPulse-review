import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  Cell,
} from 'recharts';

interface Props {
  detached?: number | null;
  semi?: number | null;
  terraced?: number | null;
  flat?: number | null;
  ukMedian?: number | null;
  parentMedian?: number | null;
}

const COLOURS: Record<string, string> = {
  Detached: '#2563eb',
  'Semi-det.': '#7c3aed',
  Terraced: '#059669',
  Flat: '#ea580c',
};

export default function PriceByTypeChart({ detached, semi, terraced, flat, ukMedian, parentMedian }: Props) {
  const data = [
    { name: 'Detached', price: detached },
    { name: 'Semi-det.', price: semi },
    { name: 'Terraced', price: terraced },
    { name: 'Flat', price: flat },
  ].filter((d) => d.price != null) as { name: string; price: number }[];

  if (data.length === 0) return null;

  const fmtGBP = (v: number) => '£' + Math.round(v).toLocaleString('en-GB');
  const fmtK = (v: number) => '£' + (v / 1000).toFixed(0) + 'k';

  return (
    <div className="bg-surface rounded-xl p-4 space-y-2 mt-2">
      <h4 className="text-sm font-semibold text-ink">Price by Property Type</h4>
      <div className="h-[180px]" role="img" aria-label="Bar chart showing price by property type">
        <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} barSize={32}>
            <XAxis
              dataKey="name"
              tick={{ fontSize: 11, fill: '#9ca3af' }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: '#9ca3af' }}
              tickFormatter={fmtK}
              tickLine={false}
              axisLine={false}
              width={52}
            />
            <Tooltip
              formatter={(value) => [fmtGBP(Number(value)), 'Avg price']}
              labelStyle={{ fontWeight: 600, color: '#111827' }}
              contentStyle={{ borderRadius: 12, border: '1px solid #e5e7eb', fontSize: 13 }}
              cursor={{ fill: 'rgba(0,0,0,0.04)' }}
            />
            {parentMedian != null && (
              <ReferenceLine
                y={parentMedian}
                stroke="#6366f1"
                strokeWidth={1.5}
                strokeDasharray="5 3"
                label={{
                  value: `Area avg ${fmtK(parentMedian)}`,
                  position: 'insideTopLeft',
                  fontSize: 10,
                  fill: '#6366f1',
                  dy: -4,
                }}
              />
            )}
            {ukMedian != null && (
              <ReferenceLine
                y={ukMedian}
                stroke="#f59e0b"
                strokeWidth={1.5}
                strokeDasharray="5 3"
                label={{
                  value: `UK avg ${fmtK(ukMedian)}`,
                  position: 'insideTopRight',
                  fontSize: 10,
                  fill: '#f59e0b',
                  dy: -4,
                }}
              />
            )}
            <Bar dataKey="price" radius={[4, 4, 0, 0]}>
              {data.map((entry) => (
                <Cell key={entry.name} fill={COLOURS[entry.name] ?? '#6b7280'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {(ukMedian != null || parentMedian != null) && (
        <p className="text-[10px] text-ink-faint space-x-2">
          {parentMedian != null && <span><span className="inline-block w-3 border-t-2 border-dashed border-indigo-500 mr-1 translate-y-[-2px]" />Area avg {fmtGBP(parentMedian)}</span>}
          {ukMedian != null && <span><span className="inline-block w-3 border-t-2 border-dashed border-amber-400 mr-1 translate-y-[-2px]" />UK avg {fmtGBP(ukMedian)}</span>}
          <span className="opacity-60">(all types, latest 12 months)</span>
        </p>
      )}
    </div>
  );
}
