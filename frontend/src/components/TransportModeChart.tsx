import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell } from 'recharts';

interface Props {
  modeCounts: Record<string, number>;
}

const MODE_CONFIG: Record<string, { label: string; colour: string }> = {
  bus:   { label: 'Bus',   colour: '#2563eb' },
  rail:  { label: 'Rail',  colour: '#7c3aed' },
  metro: { label: 'Metro', colour: '#059669' },
  tram:  { label: 'Tram',  colour: '#ea580c' },
  ferry: { label: 'Ferry', colour: '#0891b2' },
};

const ORDER = ['bus', 'rail', 'metro', 'tram', 'ferry'];

export default function TransportModeChart({ modeCounts }: Props) {
  const data = ORDER
    .filter((k) => (modeCounts[k] ?? 0) > 0)
    .map((k) => ({
      name: MODE_CONFIG[k]?.label ?? k,
      count: modeCounts[k],
      key: k,
    }));

  if (data.length === 0) return null;

  return (
    <div className="bg-surface rounded-xl p-3 space-y-1 mt-2">
      <h4 className="text-xs font-semibold text-ink-muted">Stops within 1km by mode</h4>
      <div className="h-[140px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} barSize={36}>
            <XAxis
              dataKey="name"
              tick={{ fontSize: 11, fill: '#9ca3af' }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: '#9ca3af' }}
              tickLine={false}
              axisLine={false}
              width={30}
              allowDecimals={false}
            />
            <Tooltip
              formatter={(value) => [Number(value), 'Stops']}
              labelStyle={{ fontWeight: 600, color: '#111827' }}
              contentStyle={{ borderRadius: 12, border: '1px solid #e5e7eb', fontSize: 13 }}
              cursor={{ fill: 'rgba(0,0,0,0.04)' }}
            />
            <Bar dataKey="count" radius={[4, 4, 0, 0]}>
              {data.map((d) => (
                <Cell key={d.key} fill={MODE_CONFIG[d.key]?.colour ?? '#6b7280'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
