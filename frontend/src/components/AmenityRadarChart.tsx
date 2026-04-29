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

// Essential daily-life amenities highlighted in summary badges
const ESSENTIAL_TYPES = ['supermarket', 'doctors', 'pharmacy', 'park'];

function walkMinutes(distanceM: number): number {
  return Math.ceil(distanceM / 80); // ~80m/min walking speed
}

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

  // Summary badges: nearest essential amenity with walk time
  const essentialBadges = nearest
    ? ESSENTIAL_TYPES
        .map((type) => nearest.find((n) => n.type === type))
        .filter((n): n is NonNullable<typeof n> => !!n && n.distance_m != null)
        .map((n) => ({
          label: AMENITY_LABELS[n.type] || n.type,
          name: n.name || 'Nearest',
          walkMin: walkMinutes(n.distance_m!),
          distanceM: n.distance_m!,
        }))
    : [];

  return (
    <div className="space-y-4 mt-2">
      {/* Summary header */}
      <div className="flex items-baseline gap-3 flex-wrap">
        <div className="text-sm text-ink-muted">
          <span className="text-2xl font-bold text-ink tabular-nums">{total}</span>{' '}
          amenities within 1 km
          <span className="text-ink-faint"> &middot; {typesPresent}/10 types</span>
        </div>
      </div>

      {/* Essential amenity badges */}
      {essentialBadges.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {essentialBadges.map((b) => (
            <span
              key={b.label}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border ${
                b.walkMin <= 5
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  : b.walkMin <= 10
                  ? 'bg-amber-50 text-amber-700 border-amber-200'
                  : 'bg-surface text-ink-muted border-divider'
              }`}
            >
              {b.label}: {b.walkMin} min walk
            </span>
          ))}
        </div>
      )}

      {/* Radar chart */}
      <div className="h-[260px] w-full" role="img" aria-label="Radar chart showing local amenity density by type">
        <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
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

      {/* Nearest amenities list with walk times */}
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
                <span className="text-xs font-medium text-brand-600 w-20 shrink-0">
                  {AMENITY_LABELS[n.type] || n.type}
                </span>
                <span className="text-sm text-ink truncate flex-1">
                  {n.name || 'Unnamed'}
                </span>
                {n.distance_m != null && (
                  <span className="text-xs text-ink-faint shrink-0 tabular-nums">
                    {walkMinutes(n.distance_m)} min
                    <span className="text-ink-faint/50 ml-0.5">({n.distance_m.toLocaleString()}m)</span>
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
