import {
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Tooltip,
} from 'recharts';

const AMENITY_LABELS: Record<string, string> = {
  supermarket: 'Supermarkets',
  cafe: 'Cafés',
  restaurant: 'Restaurants',
  pub: 'Pubs',
  gym: 'Gyms',
  park: 'Parks',
  pharmacy: 'Pharmacies',
  dentist: 'Dentists',
  hospital: 'Hospitals',
  doctors: 'GPs',
};

interface Props {
  counts: Record<string, number>;
  nearest?: Array<{ type: string; name: string; distance_m?: number }>;
}

export default function AmenityRadarChart({ counts, nearest }: Props) {
  const data = Object.entries(AMENITY_LABELS).map(([key, label]) => ({
    amenity: label,
    count: counts[key] || 0,
  }));

  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  const typesPresent = data.filter((d) => d.count > 0).length;
  const score = typesPresent * 10;

  return (
    <div className="space-y-4 mt-2">
      {/* Score header */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div className="text-3xl font-extrabold text-brand-600">{score}</div>
          <div className="text-xs text-ink-faint font-medium leading-tight">
            <span className="block">/100</span>
            <span className="block">score</span>
          </div>
        </div>
        <div className="text-sm text-ink-muted">
          {total} amenities within 1km &middot; {typesPresent}/10 types found
        </div>
      </div>

      {/* Radar chart */}
      <div className="h-[260px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data} cx="50%" cy="50%" outerRadius="75%">
            <PolarGrid stroke="#e5e7eb" />
            <PolarAngleAxis
              dataKey="amenity"
              tick={{ fontSize: 11, fill: '#6b7280' }}
            />
            <PolarRadiusAxis
              angle={90}
              tick={{ fontSize: 10, fill: '#9ca3af' }}
              tickCount={4}
            />
            <Radar
              name="Count"
              dataKey="count"
              stroke="#4f46e5"
              fill="#4f46e5"
              fillOpacity={0.15}
              strokeWidth={2}
            />
            <Tooltip
              contentStyle={{
                borderRadius: '12px',
                border: '1px solid #e5e7eb',
                fontSize: '13px',
              }}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      {/* Nearest amenities list */}
      {nearest && nearest.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
            Nearest of each type
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
            {nearest.map((n) => (
              <div
                key={n.type}
                className="flex items-center gap-2 px-3 py-2 rounded-xl bg-surface"
              >
                <span className="text-xs font-medium text-brand-600 w-20 shrink-0 capitalize">
                  {AMENITY_LABELS[n.type] || n.type}
                </span>
                <span className="text-sm text-ink truncate flex-1">
                  {n.name || 'Unnamed'}
                </span>
                {n.distance_m != null && (
                  <span className="text-xs text-ink-faint shrink-0">
                    {n.distance_m.toLocaleString()}m
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
