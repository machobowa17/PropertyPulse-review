/**
 * Redesigned detail renderers — ported from the Prototype page.
 *
 * These provide custom visualisations for 14 specific metrics that the
 * prototype's UX review approved. They override the generic fallback
 * grid that MetricCard would otherwise render.
 */
import type { Metric } from '../types';

// ─── Generic Bar Component ──────────────────────────────────────────
export function GenericBars({ bands, details, sorted, enhanced, parentDetails }: {
  bands: { key: string; label: string; color: string }[];
  details: Record<string, unknown>;
  sorted?: boolean;
  enhanced?: boolean;
  parentDetails?: Record<string, unknown>;
}) {
  let entries = bands
    .map(b => ({
      ...b,
      value: typeof details[b.key] === 'number' ? details[b.key] as number : null,
      parentValue: parentDetails && typeof parentDetails[b.key] === 'number' ? parentDetails[b.key] as number : null,
    }))
    .filter(e => e.value != null && e.value > 0);
  if (entries.length === 0) return null;
  if (sorted) entries = [...entries].sort((a, b) => b.value! - a.value!);
  const maxVal = Math.max(...entries.map(e => e.value!));
  return (
    <div className="space-y-2">
      {entries.map((e, idx) => (
        <div key={e.key} className="flex items-center gap-2">
          {enhanced && <span className="w-5 text-[10px] text-ink-faint tabular-nums text-right">{idx + 1}</span>}
          <span className="w-20 text-xs text-ink-muted text-right shrink-0 truncate">{e.label}</span>
          <div className="flex-1 h-5 rounded bg-divider/40 overflow-hidden relative">
            <div
              className={`h-full rounded ${e.color}`}
              style={{
                width: `${(e.value! / maxVal) * 100}%`,
                transition: enhanced ? 'width 0.7s ease-out' : undefined,
                animation: enhanced ? `enhanced-bar-fill 0.7s ease-out ${idx * 80}ms both` : undefined,
              }}
            />
            {enhanced && e.parentValue != null && e.parentValue > 0 && (
              <div
                className="absolute top-0 w-0.5 h-full bg-amber-500 rounded-full"
                style={{ left: `${Math.min((e.parentValue / maxVal) * 100, 100)}%` }}
                title={`Parent: ${e.parentValue.toFixed(1)}%`}
              />
            )}
          </div>
          <span className="w-12 text-xs text-ink tabular-nums text-right">{e.value!.toFixed(1)}%</span>
        </div>
      ))}
    </div>
  );
}

// ─── Crime Breakdown ────────────────────────────────────────────────
const CRIME_COLOURS: Record<string, string> = {
  'Anti social behaviour': '#8b5cf6',
  'Violence and sexual offences': '#dc2626',
  'Criminal damage and arson': '#ea580c',
  'Burglary': '#d97706',
  'Vehicle crime': '#0891b2',
  'Shoplifting': '#059669',
  'Public order': '#7c3aed',
  'Other theft': '#2563eb',
  'Drugs': '#be185d',
  'Theft from the person': '#0d9488',
  'Robbery': '#b91c1c',
  'Bicycle theft': '#65a30d',
  'Possession of weapons': '#991b1b',
  'Other crime': '#6b7280',
};

export function CrimeBreakdown({ details, enhanced }: { details: Record<string, unknown>; enhanced?: boolean }) {
  const skipKeys = new Set(['rolling_12m_crimes', 'months_with_data', 'resident_population', 'high_footfall_note', 'data_unavailable_note', 'detail_unit']);
  const entries = Object.entries(details)
    .filter(([k, v]) => !skipKeys.has(k) && typeof v === 'number' && !k.endsWith('_note') && !k.startsWith('parent_'))
    .map(([k, v]) => ({
      label: k.replace(/_/g, ' ').replace(/^(.)/, c => c.toUpperCase()),
      count: v as number,
    }))
    .sort((a, b) => b.count - a.count);
  if (entries.length === 0) return null;
  const maxCount = entries[0].count;
  const total = entries.reduce((s, e) => s + e.count, 0);

  return (
    <div className="space-y-2">
      <div className="text-xs text-ink-faint mb-2">
        {total.toLocaleString()} crimes in rolling 12 months
      </div>
      {entries.map((e, idx) => {
        const colour = enhanced ? (CRIME_COLOURS[e.label] ?? '#f43f5e') : undefined;
        const pct = total > 0 ? (e.count / total * 100) : 0;
        return (
          <div key={e.label} className="flex items-center gap-2">
            {enhanced && <span className="w-5 text-[10px] text-ink-faint tabular-nums text-right">{idx + 1}</span>}
            <span className="w-20 text-xs text-ink-muted text-right shrink-0 truncate">{e.label}</span>
            <div className="flex-1 h-5 rounded bg-divider/40 overflow-hidden relative">
              <div
                className={`h-full rounded ${enhanced ? '' : 'bg-rose-400/70'}`}
                style={{
                  width: `${(e.count / maxCount) * 100}%`,
                  backgroundColor: colour,
                  transition: enhanced ? 'width 0.7s ease-out' : undefined,
                  animation: enhanced ? `enhanced-bar-fill 0.7s ease-out ${idx * 60}ms both` : undefined,
                }}
              />
            </div>
            <span className="w-12 text-xs text-ink tabular-nums text-right">{e.count.toLocaleString()}</span>
            {enhanced && <span className="w-10 text-[10px] text-ink-faint tabular-nums text-right">{pct.toFixed(0)}%</span>}
          </div>
        );
      })}
    </div>
  );
}

// ─── Range Chart (for price_spread) ─────────────────────────────────
export function RangeChart({ min, max, p10, p25, p50, p75, p90, enhanced, parentMedian }: {
  min: number; max: number; p10: number; p25?: number; p50?: number; p75?: number; p90: number;
  enhanced?: boolean; parentMedian?: number | null;
}) {
  const range = max - min || 1;
  const pos = (v: number) => ((v - min) / range) * 100;
  const fmt = (v: number) => '£' + (v >= 1000000 ? (v / 1000000).toFixed(1) + 'M' : (v / 1000).toFixed(0) + 'K');
  const median = p50 ?? (min + max) / 2;
  return (
    <div className="py-3">
      <div className="relative h-10 mx-2">
        <div className="absolute top-1/2 -translate-y-1/2 h-1 bg-divider rounded-full" style={{ left: '0%', width: '100%' }} />
        <div
          className="absolute top-1/2 -translate-y-1/2 h-3 bg-brand-300/50 rounded-full"
          style={{
            left: `${pos(p10)}%`,
            width: `${pos(p90) - pos(p10)}%`,
            animation: enhanced ? 'enhanced-bar-fill 0.7s ease-out both' : undefined,
          }}
        />
        {p25 != null && p75 != null && (
          <div
            className="absolute top-1/2 -translate-y-1/2 h-5 bg-brand-500 rounded-full"
            style={{
              left: `${pos(p25)}%`,
              width: `${pos(p75) - pos(p25)}%`,
              animation: enhanced ? 'enhanced-bar-fill 0.7s ease-out 0.1s both' : undefined,
            }}
          />
        )}
        <div className="absolute top-1/2 -translate-y-1/2 w-0.5 h-7 bg-ink" style={{ left: `${pos(median)}%` }} />
        {enhanced && parentMedian != null && parentMedian >= min && parentMedian <= max && (
          <div className="absolute top-1/2 -translate-y-1/2 h-9 flex flex-col items-center" style={{ left: `${pos(parentMedian)}%` }}>
            <div className="w-px h-full border-l-2 border-dashed border-amber-500" />
            <span className="absolute -top-5 left-1/2 -translate-x-1/2 text-[9px] font-medium text-amber-600 whitespace-nowrap bg-white/80 px-1 rounded">
              Area {fmt(parentMedian)}
            </span>
          </div>
        )}
      </div>
      <div className="flex justify-between text-xs text-ink-faint mt-1 mx-2">
        <span>{fmt(min)}</span>
        <span className="text-ink font-medium">Median: {fmt(median)}</span>
        <span>{fmt(max)}</span>
      </div>
      <div className="flex justify-center gap-4 text-xs text-ink-faint mt-1">
        <span>P10: {fmt(p10)}</span>
        {p25 != null && <span>P25: {fmt(p25)}</span>}
        {p75 != null && <span>P75: {fmt(p75)}</span>}
        <span>P90: {fmt(p90)}</span>
      </div>
    </div>
  );
}

// ─── Noise Scale ────────────────────────────────────────────────────
export function NoiseScale({ road, rail, air, band, enhanced, parentRoad, parentRail, parentAir }: {
  road?: number | null; rail?: number | null; air?: number | null; band?: string | null; enhanced?: boolean;
  parentRoad?: number | null; parentRail?: number | null; parentAir?: number | null;
}) {
  const parentMap: Record<string, number | null | undefined> = { Road: parentRoad, Rail: parentRail, Air: parentAir };
  const levels = [
    { label: 'Road', db: road },
    { label: 'Rail', db: rail },
    { label: 'Air', db: air },
  ].filter(l => l.db != null);
  const getColor = (db: number) => {
    if (db <= 40) return 'bg-signal-green';
    if (db <= 55) return 'bg-amber-400';
    if (db <= 65) return 'bg-amber-500';
    return 'bg-signal-red';
  };
  const getLabel = (db: number) => {
    if (db <= 40) return 'Quiet';
    if (db <= 55) return 'Moderate';
    if (db <= 65) return 'Noticeable';
    return 'Loud';
  };
  return (
    <div className="space-y-3">
      {band && <div className="text-sm text-ink-muted">Overall: <span className="text-ink font-medium">{band}</span></div>}
      {enhanced && (
        <div className="relative h-2 rounded-full overflow-hidden" style={{ background: 'linear-gradient(to right, #059669, #facc15, #ea580c, #dc2626)' }}>
          {/* Threshold labels */}
          <div className="absolute top-full mt-0.5 text-[9px] text-ink-faint" style={{ left: '0%' }}>0</div>
          <div className="absolute top-full mt-0.5 text-[9px] text-ink-faint" style={{ left: '50%', transform: 'translateX(-50%)' }}>40</div>
          <div className="absolute top-full mt-0.5 text-[9px] text-ink-faint" style={{ left: '81.25%', transform: 'translateX(-50%)' }}>65</div>
          <div className="absolute top-full mt-0.5 text-[9px] text-ink-faint" style={{ right: '0' }}>80</div>
        </div>
      )}
      {levels.map((l, idx) => (
        <div key={l.label}>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-ink-muted">{l.label}</span>
            <span className="text-ink font-medium">{l.db!.toFixed(0)} dB <span className="text-xs text-ink-faint">({getLabel(l.db!)})</span></span>
          </div>
          <div className="h-3 rounded-full bg-divider/40 overflow-hidden relative">
            <div
              className={`h-full rounded-full ${getColor(l.db!)} transition-all`}
              style={{
                width: `${Math.min((l.db! / 80) * 100, 100)}%`,
                transition: enhanced ? 'width 0.7s ease-out' : undefined,
                animation: enhanced ? `enhanced-bar-fill 0.7s ease-out ${idx * 100}ms both` : undefined,
              }}
            />
            {enhanced && parentMap[l.label] != null && parentMap[l.label]! > 0 && (
              <div
                className="absolute top-0 w-0.5 h-full bg-amber-500 rounded-full"
                style={{ left: `${Math.min((parentMap[l.label]! / 80) * 100, 100)}%` }}
                title={`Area avg: ${parentMap[l.label]!.toFixed(0)} dB`}
              />
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Air Quality Gauge ──────────────────────────────────────────────
export function AirQualityGauge({ value, unit, whoLimit, exceedsWho, enhanced }: {
  value: number | string | null;
  unit: string;
  whoLimit?: number;
  exceedsWho?: boolean;
  enhanced?: boolean;
}) {
  const numVal = typeof value === 'number' ? value : parseFloat(String(value));
  if (isNaN(numVal)) return null;
  const maxScale = (whoLimit ?? 40) * 2;
  const pct = Math.min((numVal / maxScale) * 100, 100);
  const color = exceedsWho ? 'bg-signal-red' : numVal < (whoLimit ?? 40) * 0.5 ? 'bg-signal-green' : 'bg-amber-500';
  const whoPct = whoLimit != null ? Math.min((whoLimit / maxScale) * 100, 100) : null;
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-ink-muted">{unit}</span>
        <span className="text-ink font-semibold">{numVal.toFixed(1)} µg/m³</span>
      </div>
      <div className="relative h-4 rounded-full overflow-hidden" style={enhanced ? { background: 'linear-gradient(to right, #059669, #facc15, #ea580c, #dc2626)' } : undefined}>
        {!enhanced && <div className="absolute inset-0 bg-divider/40" />}
        <div
          className={`h-full rounded-full ${enhanced ? '' : color} transition-all relative z-10`}
          style={{
            width: `${pct}%`,
            background: enhanced ? 'transparent' : undefined,
            transition: enhanced ? 'width 0.7s ease-out' : undefined,
            animation: enhanced ? 'enhanced-bar-fill 0.7s ease-out both' : undefined,
          }}
        />
        {/* Mask: cover everything after the fill */}
        {enhanced && (
          <div
            className="absolute top-0 right-0 h-full bg-divider/40 z-[5]"
            style={{ width: `${100 - pct}%` }}
          />
        )}
        {whoLimit != null && whoPct != null && (
          <div
            className={`absolute top-0 z-20 ${enhanced ? 'h-6 -top-1' : 'h-full'} border-r-2 border-dashed border-ink/60`}
            style={{ left: `${whoPct}%` }}
            title={`WHO guideline: ${whoLimit}`}
          >
            {enhanced && (
              <span className="absolute -top-4 left-1/2 -translate-x-1/2 text-[9px] text-ink-faint font-medium whitespace-nowrap bg-white/80 px-1 rounded">
                WHO {whoLimit}
              </span>
            )}
          </div>
        )}
      </div>
      <div className="text-xs mt-0.5 text-ink-faint">
        WHO guideline: {whoLimit} µg/m³ {exceedsWho ? <span className="text-signal-red font-medium">— Exceeded</span> : <span className="text-signal-green">— Within limit</span>}
      </div>
    </div>
  );
}

// ─── Governance Detail ──────────────────────────────────────────────
export function GovernanceDetail({ metric, enhanced }: { metric: Metric; enhanced?: boolean }) {
  const d = metric.details;
  if (!d) return null;

  if (metric.id === 'controlling_party') {
    const breakdown = d.party_breakdown as { party: string; authority_count: number }[] | undefined;
    const controls = d.authority_controls as { lad_name: string; controlling_party: string; majority_seats?: number; total_seats?: number }[] | undefined;
    return (
      <div className="space-y-3">
        {breakdown && breakdown.length > 0 && (
          <div>
            <div className="text-xs text-ink-faint uppercase tracking-wider mb-2">Party Breakdown</div>
            {breakdown.map(p => {
              const maxSeats = Math.max(...breakdown.map(b => b.authority_count));
              const color = p.party.toLowerCase().includes('labour') ? 'bg-red-500' : p.party.toLowerCase().includes('conservative') ? 'bg-blue-500' : p.party.toLowerCase().includes('lib') ? 'bg-amber-500' : p.party.toLowerCase().includes('green') ? 'bg-emerald-500' : 'bg-ink-faint';
              return (
                <div key={p.party} className="flex items-center gap-2 mb-1.5">
                  <span className="w-28 text-xs text-ink-muted truncate text-right">{p.party}</span>
                  <div className="flex-1 h-4 rounded bg-divider/40 overflow-hidden">
                    <div
                      className={`h-full rounded ${color}`}
                      style={{
                        width: `${(p.authority_count / maxSeats) * 100}%`,
                        transition: enhanced ? 'width 0.7s ease-out' : undefined,
                        animation: enhanced ? 'enhanced-bar-fill 0.7s ease-out both' : undefined,
                      }}
                    />
                  </div>
                  <span className="w-8 text-xs text-ink tabular-nums">{p.authority_count}</span>
                </div>
              );
            })}
          </div>
        )}
        {controls && controls.length > 0 && (
          <div>
            <div className="text-xs text-ink-faint uppercase tracking-wider mb-2">Council Control</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
              {controls.map(c => (
                <div key={c.lad_name} className="flex justify-between text-xs bg-surface-warm rounded-lg px-3 py-1.5">
                  <span className="text-ink">{c.lad_name}</span>
                  <span className="text-ink-muted">{c.controlling_party}{c.total_seats ? ` (${c.majority_seats}/${c.total_seats})` : ''}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  if (metric.id === 'local_authority') {
    const authorities = d.authorities as string[] | undefined;
    const regions = d.regions as string[] | undefined;
    const counties = d.counties as string[] | undefined;
    return (
      <div className="space-y-2">
        {authorities && authorities.length > 0 && (
          <div>
            <div className="text-xs text-ink-faint uppercase tracking-wider mb-1">Authorities</div>
            <div className="flex flex-wrap gap-1.5">
              {authorities.map(a => <span key={a} className="px-2.5 py-1 rounded-lg bg-surface-warm text-xs text-ink border border-divider">{a}</span>)}
            </div>
          </div>
        )}
        {counties && counties.length > 0 && (
          <div>
            <div className="text-xs text-ink-faint uppercase tracking-wider mb-1">Counties</div>
            <div className="flex flex-wrap gap-1.5">
              {counties.map(c => <span key={c} className="px-2.5 py-1 rounded-lg bg-surface-warm text-xs text-ink border border-divider">{c}</span>)}
            </div>
          </div>
        )}
        {regions && regions.length > 0 && (
          <div>
            <div className="text-xs text-ink-faint uppercase tracking-wider mb-1">Regions</div>
            <div className="flex flex-wrap gap-1.5">
              {regions.map(r => <span key={r} className="px-2.5 py-1 rounded-lg bg-surface-warm text-xs text-ink border border-divider">{r}</span>)}
            </div>
          </div>
        )}
      </div>
    );
  }

  if (metric.id === 'water_company') {
    const providers = d.providers as string[] | undefined;
    const authProviders = d.authority_providers as { lad_name: string; water_company: string }[] | undefined;
    return (
      <div className="space-y-2">
        {providers && providers.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {providers.map(p => <span key={p} className="px-2.5 py-1 rounded-lg bg-brand-50 text-xs text-brand-700 border border-brand-200">{p}</span>)}
          </div>
        )}
        {authProviders && authProviders.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 mt-2">
            {authProviders.map(ap => (
              <div key={ap.lad_name} className="flex justify-between text-xs bg-surface-warm rounded-lg px-3 py-1.5">
                <span className="text-ink">{ap.lad_name}</span>
                <span className="text-brand-600">{ap.water_company}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  return null;
}

// ─── Set of metrics that have redesigned detail renderers ───────────
export const REDESIGNED_METRIC_IDS = new Set([
  'ethnicity', 'religion', 'crime_rate', 'price_spread',
  'noise', 'air_quality_no2', 'air_quality_pm25',
  'median_age', 'household_composition', 'household_size', 'commute_distance',
  'controlling_party', 'local_authority', 'water_company',
]);

// ─── Main dispatcher: returns redesigned JSX or null ────────────────
export function renderRedesignedDetail(metric: Metric, enhanced?: boolean): React.ReactNode | null {
  const d = metric.details;
  if (!d) return null;

  if (metric.id === 'ethnicity') {
    return <GenericBars bands={[
      { key: 'pct_white', label: 'White', color: 'bg-blue-500' },
      { key: 'pct_asian', label: 'Asian', color: 'bg-emerald-500' },
      { key: 'pct_black', label: 'Black', color: 'bg-purple-500' },
      { key: 'pct_mixed', label: 'Mixed', color: 'bg-amber-500' },
      { key: 'pct_other', label: 'Other', color: 'bg-slate-500' },
    ]} details={d as Record<string, unknown>} sorted enhanced={enhanced} />;
  }

  if (metric.id === 'religion') {
    const skipKeys = new Set(['detail_unit']);
    const items = Object.entries(d)
      .filter(([k, v]) => !skipKeys.has(k) && typeof v === 'number' && (v as number) > 0)
      .sort((a, b) => (b[1] as number) - (a[1] as number));
    const colors = ['bg-blue-500', 'bg-emerald-500', 'bg-purple-500', 'bg-amber-500', 'bg-rose-500', 'bg-cyan-500', 'bg-slate-500', 'bg-pink-500'];
    return <GenericBars bands={items.map(([k], idx) => ({ key: k, label: k, color: colors[idx % colors.length] }))} details={d as Record<string, unknown>} enhanced={enhanced} />;
  }

  if (metric.id === 'crime_rate') return <CrimeBreakdown details={d as Record<string, unknown>} enhanced={enhanced} />;

  if (metric.id === 'price_spread') {
    const min_price = d.min_price as number | undefined;
    const max_price = d.max_price as number | undefined;
    const p10 = d.p10 as number | undefined;
    const p90 = d.p90 as number | undefined;
    if (min_price != null && max_price != null && p10 != null && p90 != null) {
      return <RangeChart min={min_price} max={max_price} p10={p10} p25={d.p25 as number | undefined} p50={d.p50 as number | undefined} p75={d.p75 as number | undefined} p90={p90} enhanced={enhanced} />;
    }
  }

  if (metric.id === 'noise') return <NoiseScale road={d.road_db as number | null} rail={d.rail_db as number | null} air={d.air_db as number | null} band={d.noise_band as string | null} enhanced={enhanced} />;
  if (metric.id === 'air_quality_no2') return <AirQualityGauge value={metric.local_value} unit="NO\u2082" whoLimit={d.who_limit as number | undefined} exceedsWho={d.exceeds_who as boolean | undefined} enhanced={enhanced} />;
  if (metric.id === 'air_quality_pm25') return <AirQualityGauge value={metric.local_value} unit="PM2.5" whoLimit={d.who_limit as number | undefined} exceedsWho={d.exceeds_who as boolean | undefined} enhanced={enhanced} />;

  if (metric.id === 'median_age') return <GenericBars bands={[{ key: '0–15 years', label: '0–15', color: 'bg-sky-500' }, { key: '16–64 years', label: '16–64', color: 'bg-brand-500' }, { key: '65+ years', label: '65+', color: 'bg-amber-500' }]} details={d as Record<string, unknown>} enhanced={enhanced} />;
  if (metric.id === 'household_composition') return <GenericBars bands={[{ key: 'pct_families', label: 'Families', color: 'bg-emerald-500' }, { key: 'pct_singles', label: 'Singles', color: 'bg-sky-500' }, { key: 'pct_sharers', label: 'Sharers', color: 'bg-purple-500' }]} details={d as Record<string, unknown>} enhanced={enhanced} />;
  if (metric.id === 'household_size') return <GenericBars bands={[{ key: '1 person', label: '1 person', color: 'bg-sky-500' }, { key: '2 people', label: '2 people', color: 'bg-brand-500' }, { key: '3–4 people', label: '3–4', color: 'bg-emerald-500' }, { key: '5+ people', label: '5+', color: 'bg-amber-500' }]} details={d as Record<string, unknown>} enhanced={enhanced} />;
  if (metric.id === 'commute_distance') return <GenericBars bands={[{ key: 'Under 2 km', label: '<2 km', color: 'bg-emerald-500' }, { key: '2–10 km', label: '2–10 km', color: 'bg-sky-500' }, { key: '10–30 km', label: '10–30 km', color: 'bg-brand-500' }, { key: '30+ km', label: '30+ km', color: 'bg-purple-500' }, { key: 'Work from home', label: 'WFH', color: 'bg-amber-500' }]} details={d as Record<string, unknown>} enhanced={enhanced} />;

  if (metric.id === 'controlling_party' || metric.id === 'local_authority' || metric.id === 'water_company') return <GovernanceDetail metric={metric} enhanced={enhanced} />;

  return null;
}
