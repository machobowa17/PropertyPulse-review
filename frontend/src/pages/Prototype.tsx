/**
 * Prototype page — redesigned metric components for UX review.
 *
 * Lives at /prototype. Fetches real data from the API for a configurable
 * search query and renders BOTH current and proposed designs side-by-side.
 *
 * Uses the SAME light theme as the main portal (bg-surface, text-ink, etc.)
 * and includes the MapView component for spatial context.
 *
 * Does NOT touch any existing components or pages.
 */
import { useState, useEffect, useCallback, useMemo, lazy, Suspense } from 'react';
import type { Metric, AreaResponse, TabName } from '../types';
import { resolveSearch, fetchAreaTab, fetchBoundary } from '../api/client';
import {
  Home, Coffee, TreePine, Users, Landmark,
  PoundSterling, TrendingUp, BarChart3, Receipt, Building2,
  Train, Wifi, ShoppingBag,
  Shield, Wind, Leaf,
  UserCircle, Globe, GraduationCap, Scale, HeartPulse,
  CirclePlus, CircleMinus,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

const MapView = lazy(() => import('../components/MapView'));

// ─── Constants ──────────────────────────────────────────────────────
const ALL_TABS: TabName[] = [
  'Property & Market',
  'Lifestyle & Connectivity',
  'Environment & Safety',
  'Community & Education',
  'Local Governance',
];

const DEMO_QUERIES = [
  'CR5 1RA',
  'Surrey',
  'Croydon',
  'Camden',
  'Whitby',
];

// ─── Tab & Section Icons (Set A — subtle/pastel) ────────────────────
const TAB_ICONS: Record<string, LucideIcon> = {
  'Property & Market': Home,
  'Lifestyle & Connectivity': Coffee,
  'Environment & Safety': TreePine,
  'Community & Education': Users,
  'Local Governance': Landmark,
};

const SECTION_ICONS: Record<string, LucideIcon> = {
  'Prices & Value': PoundSterling,
  'Market Activity': TrendingUp,
  'Trends': BarChart3,
  'Costs & Income': Receipt,
  'Housing Stock': Building2,
  'Transport & Access': Train,
  'Digital Connectivity': Wifi,
  'Amenities': ShoppingBag,
  'Safety': Shield,
  'Environment': Wind,
  'Green Space': Leaf,
  'People': UserCircle,
  'Diversity': Globe,
  'Schools': GraduationCap,
  'Deprivation': Scale,
  'Health Services': HeartPulse,
  'Governance': Landmark,
};

// ─── Sparkline Component ────────────────────────────────────────────
function Sparkline({ values, color = '#3b82f6', height = 20, width = 60 }: {
  values: number[];
  color?: string;
  height?: number;
  width?: number;
}) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * width;
    const y = height - ((v - min) / range) * (height - 4) - 2;
    return `${x},${y}`;
  }).join(' ');
  return (
    <svg width={width} height={height} className="inline-block align-middle">
      <polyline points={points} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={(values.length - 1) / (values.length - 1) * width} cy={height - ((values[values.length - 1] - min) / range) * (height - 4) - 2} r="2.5" fill={color} />
    </svg>
  );
}

// ─── Trend Text Helper ──────────────────────────────────────────────
function trendText(values: (number | null | undefined)[], suffix = ''): string {
  const clean = values.filter((v): v is number => v != null);
  if (clean.length < 2) return '';
  const first = clean[0];
  const last = clean[clean.length - 1];
  const diff = last - first;
  const sign = diff > 0 ? '+' : '';
  return `${sign}${diff.toFixed(1)}${suffix} over ${clean.length} yrs`;
}

function trendDirection(values: (number | null | undefined)[]): 'up' | 'down' | 'flat' {
  const clean = values.filter((v): v is number => v != null);
  if (clean.length < 2) return 'flat';
  const diff = clean[clean.length - 1] - clean[0];
  if (Math.abs(diff) < 0.5) return 'flat';
  return diff > 0 ? 'up' : 'down';
}

// ─── Range Chart (for price_spread) ─────────────────────────────────
function RangeChart({ min, max, p10, p25, p50, p75, p90 }: {
  min: number; max: number; p10: number; p25?: number; p50?: number; p75?: number; p90: number;
}) {
  const range = max - min || 1;
  const pos = (v: number) => ((v - min) / range) * 100;
  const fmt = (v: number) => '£' + (v >= 1000000 ? (v / 1000000).toFixed(1) + 'M' : (v / 1000).toFixed(0) + 'K');
  const median = p50 ?? (min + max) / 2;
  return (
    <div className="py-3">
      <div className="relative h-10 mx-2">
        <div className="absolute top-1/2 -translate-y-1/2 h-1 bg-divider rounded-full" style={{ left: '0%', width: '100%' }} />
        <div className="absolute top-1/2 -translate-y-1/2 h-3 bg-brand-300/50 rounded-full" style={{ left: `${pos(p10)}%`, width: `${pos(p90) - pos(p10)}%` }} />
        {p25 != null && p75 != null && (
          <div className="absolute top-1/2 -translate-y-1/2 h-5 bg-brand-500 rounded-full" style={{ left: `${pos(p25)}%`, width: `${pos(p75) - pos(p25)}%` }} />
        )}
        <div className="absolute top-1/2 -translate-y-1/2 w-0.5 h-7 bg-ink" style={{ left: `${pos(median)}%` }} />
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
function NoiseScale({ road, rail, air, band }: { road?: number | null; rail?: number | null; air?: number | null; band?: string | null }) {
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
      {levels.map(l => (
        <div key={l.label}>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-ink-muted">{l.label}</span>
            <span className="text-ink font-medium">{l.db!.toFixed(0)} dB <span className="text-xs text-ink-faint">({getLabel(l.db!)})</span></span>
          </div>
          <div className="h-3 rounded-full bg-divider/40 overflow-hidden">
            <div className={`h-full rounded-full ${getColor(l.db!)} transition-all`} style={{ width: `${Math.min((l.db! / 80) * 100, 100)}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Air Quality Indicator ──────────────────────────────────────────
function AirQualityGauge({ value, unit, whoLimit, exceedsWho }: {
  value: number | string | null;
  unit: string;
  whoLimit?: number;
  exceedsWho?: boolean;
}) {
  const numVal = typeof value === 'number' ? value : parseFloat(String(value));
  if (isNaN(numVal)) return null;
  const maxScale = (whoLimit ?? 40) * 2;
  const pct = Math.min((numVal / maxScale) * 100, 100);
  const color = exceedsWho ? 'bg-signal-red' : numVal < (whoLimit ?? 40) * 0.5 ? 'bg-signal-green' : 'bg-amber-500';
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-ink-muted">{unit}</span>
        <span className="text-ink font-semibold">{numVal.toFixed(1)} µg/m³</span>
      </div>
      <div className="relative h-4 rounded-full bg-divider/40 overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${pct}%` }} />
        {whoLimit != null && (
          <div className="absolute top-0 h-full border-r-2 border-dashed border-ink/40" style={{ left: `${Math.min((whoLimit / maxScale) * 100, 100)}%` }} title={`WHO guideline: ${whoLimit}`} />
        )}
      </div>
      <div className="text-xs mt-0.5 text-ink-faint">
        WHO guideline: {whoLimit} µg/m³ {exceedsWho ? <span className="text-signal-red font-medium">— Exceeded</span> : <span className="text-signal-green">— Within limit</span>}
      </div>
    </div>
  );
}

// ─── Crime Bar Chart ────────────────────────────────────────────────
function CrimeBreakdown({ details }: { details: Record<string, unknown> }) {
  const skipKeys = new Set(['rolling_12m_crimes', 'months_with_data', 'resident_population', 'high_footfall_note', 'data_unavailable_note', 'detail_unit']);
  const entries = Object.entries(details)
    .filter(([k, v]) => !skipKeys.has(k) && typeof v === 'number' && !k.endsWith('_note'))
    .map(([k, v]) => ({ label: k.replace(/_/g, ' ').replace(/^(.)/, c => c.toUpperCase()), count: v as number }))
    .sort((a, b) => b.count - a.count);
  if (entries.length === 0) return null;
  const maxCount = entries[0].count;
  const total = entries.reduce((s, e) => s + e.count, 0);
  return (
    <div className="space-y-2">
      <div className="text-xs text-ink-faint mb-2">{total.toLocaleString()} crimes in rolling 12 months</div>
      {entries.map(e => (
        <div key={e.label} className="flex items-center gap-2">
          <span className="w-20 text-xs text-ink-muted text-right shrink-0 truncate">{e.label}</span>
          <div className="flex-1 h-5 rounded bg-divider/40 overflow-hidden">
            <div className="h-full rounded bg-rose-400/70" style={{ width: `${(e.count / maxCount) * 100}%` }} />
          </div>
          <span className="w-12 text-xs text-ink tabular-nums text-right">{e.count.toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
}

// ─── Governance Detail ──────────────────────────────────────────────
function GovernanceDetail({ metric }: { metric: Metric }) {
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
                    <div className={`h-full rounded ${color}`} style={{ width: `${(p.authority_count / maxSeats) * 100}%` }} />
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

// ─── Generic Bar Components ─────────────────────────────────────────
function GenericBars({ bands, details, sorted }: { bands: { key: string; label: string; color: string }[]; details: Record<string, unknown>; sorted?: boolean }) {
  let entries = bands.map(b => ({ ...b, value: typeof details[b.key] === 'number' ? details[b.key] as number : null })).filter(e => e.value != null && e.value > 0);
  if (entries.length === 0) return null;
  if (sorted) entries = [...entries].sort((a, b) => b.value! - a.value!);
  const maxVal = Math.max(...entries.map(e => e.value!));
  return (
    <div className="space-y-2">
      {entries.map(e => (
        <div key={e.key} className="flex items-center gap-2">
          <span className="w-20 text-xs text-ink-muted text-right shrink-0 truncate">{e.label}</span>
          <div className="flex-1 h-5 rounded bg-divider/40 overflow-hidden">
            <div className={`h-full rounded ${e.color}`} style={{ width: `${(e.value! / maxVal) * 100}%` }} />
          </div>
          <span className="w-12 text-xs text-ink tabular-nums text-right">{e.value!.toFixed(1)}%</span>
        </div>
      ))}
    </div>
  );
}

// ─── School Results Sparkline View ──────────────────────────────────
function SchoolResultsSparkline({ school }: { school: Record<string, unknown> }) {
  const ks2 = school.ks2 as { academic_year?: string; pct_rwm_expected?: number; pct_rwm_higher?: number; reading_progress?: number; maths_progress?: number }[] | undefined;
  const ks4 = school.ks4 as { academic_year?: string; attainment_8?: number; progress_8?: number; pct_grade_5_em?: number; pct_entering_ebacc?: number }[] | undefined;
  const ks5 = school.ks5 as { academic_year?: string; avg_point_score_a?: number }[] | undefined;

  interface SparkRow { label: string; value: string; values: number[]; trend: string; color: string }
  const renderSection = (title: string, latestYear: string | undefined, rows: SparkRow[]) => (
    <div className="mb-4">
      <div className="flex justify-between items-baseline mb-2">
        <span className="text-sm font-semibold text-ink">{title}</span>
        {latestYear && <span className="text-xs text-ink-faint">Latest: {latestYear}</span>}
      </div>
      <div className="rounded-xl bg-surface-raised border border-divider divide-y divide-divider/50">
        {rows.map(row => (
          <div key={row.label} className="flex items-center justify-between px-4 py-2.5">
            <span className="text-sm text-ink-muted w-32">{row.label}</span>
            <span className="text-sm font-bold text-ink tabular-nums w-16 text-right">{row.value}</span>
            <Sparkline values={row.values} color={row.color} width={50} height={18} />
            <span className={`text-xs w-36 text-right ${row.trend.startsWith('+') || row.trend.startsWith('Imp') ? 'text-signal-green' : row.trend.startsWith('-') || row.trend.startsWith('Dec') ? 'text-signal-red' : 'text-ink-faint'}`}>
              {row.trend}
            </span>
          </div>
        ))}
      </div>
      <button className="text-xs text-brand-600 hover:text-brand-700 mt-1.5 ml-1">View full table &rarr;</button>
    </div>
  );

  return (
    <div>
      {ks2 && ks2.length > 0 && renderSection('KS2 (Year 6)', ks2[0]?.academic_year, [
        { label: 'RWM Expected', value: ks2[0]?.pct_rwm_expected != null ? `${Math.round(ks2[0].pct_rwm_expected)}%` : '—', values: [...ks2].reverse().map(y => y.pct_rwm_expected ?? 0), trend: trendText([...ks2].reverse().map(y => y.pct_rwm_expected), 'pts'), color: '#059669' },
        { label: 'RWM Higher', value: ks2[0]?.pct_rwm_higher != null ? `${Math.round(ks2[0].pct_rwm_higher)}%` : '—', values: [...ks2].reverse().map(y => y.pct_rwm_higher ?? 0), trend: trendText([...ks2].reverse().map(y => y.pct_rwm_higher), 'pts'), color: '#3b82f6' },
        { label: 'Reading Prog', value: ks2[0]?.reading_progress != null ? (ks2[0].reading_progress > 0 ? '+' : '') + ks2[0].reading_progress.toFixed(1) : '—', values: [...ks2].reverse().map(y => y.reading_progress ?? 0), trend: trendDirection([...ks2].reverse().map(y => y.reading_progress)) === 'up' ? 'Improving' : trendDirection([...ks2].reverse().map(y => y.reading_progress)) === 'down' ? 'Declining' : 'Stable', color: '#8b5cf6' },
        { label: 'Maths Prog', value: ks2[0]?.maths_progress != null ? (ks2[0].maths_progress > 0 ? '+' : '') + ks2[0].maths_progress.toFixed(1) : '—', values: [...ks2].reverse().map(y => y.maths_progress ?? 0), trend: trendDirection([...ks2].reverse().map(y => y.maths_progress)) === 'up' ? 'Improving' : trendDirection([...ks2].reverse().map(y => y.maths_progress)) === 'down' ? 'Declining' : 'Stable', color: '#ec4899' },
      ])}
      {ks4 && ks4.length > 0 && renderSection('GCSE', ks4[0]?.academic_year, [
        { label: 'Attainment 8', value: ks4[0]?.attainment_8?.toFixed(1) ?? '—', values: [...ks4].reverse().map(y => y.attainment_8 ?? 0), trend: trendText([...ks4].reverse().map(y => y.attainment_8)), color: '#059669' },
        { label: 'Progress 8', value: ks4[0]?.progress_8 != null ? (ks4[0].progress_8 > 0 ? '+' : '') + ks4[0].progress_8.toFixed(2) : '—', values: [...ks4].reverse().map(y => y.progress_8 ?? 0), trend: trendDirection([...ks4].reverse().map(y => y.progress_8)) === 'up' ? 'Improving' : 'Stable', color: '#3b82f6' },
        { label: '5+ Eng & Maths', value: ks4[0]?.pct_grade_5_em != null ? `${Math.round(ks4[0].pct_grade_5_em)}%` : '—', values: [...ks4].reverse().map(y => y.pct_grade_5_em ?? 0), trend: trendText([...ks4].reverse().map(y => y.pct_grade_5_em), 'pts'), color: '#8b5cf6' },
        { label: 'EBacc Entry', value: ks4[0]?.pct_entering_ebacc != null ? `${Math.round(ks4[0].pct_entering_ebacc)}%` : '—', values: [...ks4].reverse().map(y => y.pct_entering_ebacc ?? 0), trend: trendText([...ks4].reverse().map(y => y.pct_entering_ebacc), 'pts'), color: '#ec4899' },
      ])}
      {ks5 && ks5.length > 0 && renderSection('A-Level', ks5[0]?.academic_year, [
        { label: 'A-Level APS', value: ks5[0]?.avg_point_score_a?.toFixed(1) ?? '—', values: [...ks5].reverse().map(y => y.avg_point_score_a ?? 0), trend: trendText([...ks5].reverse().map(y => y.avg_point_score_a)), color: '#059669' },
      ])}
      {!ks2?.length && !ks4?.length && !ks5?.length && (
        <div className="text-sm text-ink-faint italic">School results data will appear here when a school is expanded. This prototype shows the layout — expand a school in the main portal to see real data fed through this design.</div>
      )}
    </div>
  );
}

// ─── Section Summary Badge ──────────────────────────────────────────
function SectionBadge({ metrics }: { metrics: Metric[] }) {
  const above = metrics.filter(m => m.comparison_flag === 'higher_than_parent').length;
  const below = metrics.filter(m => m.comparison_flag === 'lower_than_parent').length;
  const equal = metrics.filter(m => m.comparison_flag === 'equal_to_parent').length;
  if (above + below + equal === 0) return null;
  const dominant = above >= below ? (above > equal ? 'Above Average' : 'Average') : 'Below Average';
  const color = above >= below ? (above > equal ? 'text-signal-green bg-signal-green-bg border-signal-green/20' : 'text-ink-muted bg-surface-warm border-divider') : 'text-signal-amber bg-signal-amber-bg border-signal-amber/20';
  return <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${color}`}>{dominant}</span>;
}

// ─── Format Value ───────────────────────────────────────────────────
function formatValue(value: number | string | null, unit: string): string {
  if (value == null) return '—';
  if (typeof value === 'string') return value;
  if (unit === 'GBP' || unit === 'GBP/month' || unit === 'GBP/year') return '£' + value.toLocaleString('en-GB', { maximumFractionDigits: 0 });
  if (unit === '%' || unit === 'pct') return value.toFixed(1) + '%';
  if (unit === 'years') return value.toFixed(1);
  if (unit === 'ratio') return value.toFixed(2);
  if (unit === 'dB') return value.toFixed(0) + ' dB';
  if (unit === 'score') return value.toFixed(1);
  return value.toLocaleString('en-GB', { maximumFractionDigits: 1 });
}

// ─── Comparison Icon ────────────────────────────────────────────────
function CompIcon({ flag }: { flag: Metric['comparison_flag'] }) {
  if (flag === 'higher_than_parent') return <span className="text-signal-green">&#9650;</span>;
  if (flag === 'lower_than_parent') return <span className="text-signal-amber">&#9660;</span>;
  return <span className="text-ink-faint">&#9644;</span>;
}

// ─── Redesigned Detail Renderer ─────────────────────────────────────
function RedesignedDetail({ metric }: { metric: Metric }) {
  const d = metric.details;
  if (!d) return null;

  if (metric.id === 'ethnicity') {
    return <GenericBars bands={[
      { key: 'pct_white', label: 'White', color: 'bg-blue-500' },
      { key: 'pct_asian', label: 'Asian', color: 'bg-emerald-500' },
      { key: 'pct_black', label: 'Black', color: 'bg-purple-500' },
      { key: 'pct_mixed', label: 'Mixed', color: 'bg-amber-500' },
      { key: 'pct_other', label: 'Other', color: 'bg-slate-500' },
    ]} details={d as Record<string, unknown>} sorted />;
  }

  if (metric.id === 'religion') {
    const skipKeys = new Set(['detail_unit']);
    const items = Object.entries(d)
      .filter(([k, v]) => !skipKeys.has(k) && typeof v === 'number' && (v as number) > 0)
      .sort((a, b) => (b[1] as number) - (a[1] as number));
    const colors = ['bg-blue-500', 'bg-emerald-500', 'bg-purple-500', 'bg-amber-500', 'bg-rose-500', 'bg-cyan-500', 'bg-slate-500', 'bg-pink-500'];
    return <GenericBars bands={items.map(([k], idx) => ({ key: k, label: k, color: colors[idx % colors.length] }))} details={d as Record<string, unknown>} />;
  }

  if (metric.id === 'crime_rate') return <CrimeBreakdown details={d as Record<string, unknown>} />;

  if (metric.id === 'price_spread') {
    const min_price = d.min_price as number | undefined;
    const max_price = d.max_price as number | undefined;
    const p10 = d.p10 as number | undefined;
    const p90 = d.p90 as number | undefined;
    if (min_price != null && max_price != null && p10 != null && p90 != null) {
      return <RangeChart min={min_price} max={max_price} p10={p10} p25={d.p25 as number | undefined} p50={d.p50 as number | undefined} p75={d.p75 as number | undefined} p90={p90} />;
    }
  }

  if (metric.id === 'noise') return <NoiseScale road={d.road_db as number | null} rail={d.rail_db as number | null} air={d.air_db as number | null} band={d.noise_band as string | null} />;
  if (metric.id === 'air_quality_no2') return <AirQualityGauge value={metric.local_value} unit="NO₂" whoLimit={d.who_limit as number | undefined} exceedsWho={d.exceeds_who as boolean | undefined} />;
  if (metric.id === 'air_quality_pm25') return <AirQualityGauge value={metric.local_value} unit="PM2.5" whoLimit={d.who_limit as number | undefined} exceedsWho={d.exceeds_who as boolean | undefined} />;

  if (metric.id === 'median_age') return <GenericBars bands={[{ key: '0–15 years', label: '0–15', color: 'bg-sky-500' }, { key: '16–64 years', label: '16–64', color: 'bg-brand-500' }, { key: '65+ years', label: '65+', color: 'bg-amber-500' }]} details={d as Record<string, unknown>} />;
  if (metric.id === 'household_composition') return <GenericBars bands={[{ key: 'pct_families', label: 'Families', color: 'bg-emerald-500' }, { key: 'pct_singles', label: 'Singles', color: 'bg-sky-500' }, { key: 'pct_sharers', label: 'Sharers', color: 'bg-purple-500' }]} details={d as Record<string, unknown>} />;
  if (metric.id === 'household_size') return <GenericBars bands={[{ key: '1 person', label: '1 person', color: 'bg-sky-500' }, { key: '2 people', label: '2 people', color: 'bg-brand-500' }, { key: '3–4 people', label: '3–4', color: 'bg-emerald-500' }, { key: '5+ people', label: '5+', color: 'bg-amber-500' }]} details={d as Record<string, unknown>} />;
  if (metric.id === 'commute_distance') return <GenericBars bands={[{ key: 'Under 2 km', label: '<2 km', color: 'bg-emerald-500' }, { key: '2–10 km', label: '2–10 km', color: 'bg-sky-500' }, { key: '10–30 km', label: '10–30 km', color: 'bg-brand-500' }, { key: '30+ km', label: '30+ km', color: 'bg-purple-500' }, { key: 'Work from home', label: 'WFH', color: 'bg-amber-500' }]} details={d as Record<string, unknown>} />;

  if (metric.id === 'controlling_party' || metric.id === 'local_authority' || metric.id === 'water_company') return <GovernanceDetail metric={metric} />;

  return null;
}

// ─── Section Grouping ───────────────────────────────────────────────
const SECTION_MAP: Record<string, { label: string; metrics: string[] }> = {
  prices: { label: 'Prices & Value', metrics: ['avg_price', 'median_price', 'price_per_sqft', 'price_spread', 'affordability', 'investment_grade'] },
  market: { label: 'Market Activity', metrics: ['transaction_volume', 'freehold_leasehold', 'new_build_proportion'] },
  trends: { label: 'Trends', metrics: ['price_trend_yoy', 'official_hpi'] },
  costs: { label: 'Costs & Income', metrics: ['council_tax', 'median_rent', 'gross_yield', 'median_earnings'] },
  housing: { label: 'Housing Stock', metrics: ['epc_energy_score', 'housing_tenure', 'housing_type'] },
  transport: { label: 'Transport & Access', metrics: ['nearest_station', 'stations_in_area', 'ptal_score', 'commuter_connectivity', 'cycling', 'commute_distance', 'ev_chargers'] },
  digital: { label: 'Digital Connectivity', metrics: ['broadband', 'mobile_coverage'] },
  amenities: { label: 'Amenities', metrics: ['amenities_15min'] },
  safety: { label: 'Safety', metrics: ['crime_rate', 'crime_trend'] },
  environment: { label: 'Environment', metrics: ['flood_risk', 'air_quality_no2', 'air_quality_pm25', 'noise'] },
  green: { label: 'Green Space', metrics: ['green_cover', 'nearest_park', 'parks_1km', 'green_spaces', 'sports_recreation'] },
  people: { label: 'People', metrics: ['demographics_overview', 'median_age', 'household_composition', 'household_size', 'good_health', 'economically_active', 'degree_educated', 'no_car', 'born_abroad'] },
  diversity: { label: 'Diversity', metrics: ['ethnicity', 'religion'] },
  schools: { label: 'Schools', metrics: ['primary_schools', 'secondary_schools', 'nurseries'] },
  deprivation: { label: 'Deprivation', metrics: ['deprivation', 'deprivation_income', 'deprivation_employment', 'deprivation_education', 'deprivation_health', 'deprivation_crime', 'deprivation_barriers', 'deprivation_living'] },
  health: { label: 'Health Services', metrics: ['nhs_facilities'] },
  governance: { label: 'Governance', metrics: ['council_tax', 'local_authority', 'controlling_party', 'water_company'] },
};

function groupMetrics(metrics: Metric[]): { label: string; metrics: Metric[]; badge: string }[] {
  const metricMap = new Map(metrics.map(m => [m.id, m]));
  const used = new Set<string>();
  const groups: { label: string; metrics: Metric[]; badge: string }[] = [];
  for (const [, section] of Object.entries(SECTION_MAP)) {
    const sectionMetrics = section.metrics.map(id => metricMap.get(id)).filter((m): m is Metric => m != null && m.local_value != null);
    if (sectionMetrics.length === 0) continue;
    sectionMetrics.forEach(m => used.add(m.id));
    const above = sectionMetrics.filter(m => m.comparison_flag === 'higher_than_parent').length;
    const below = sectionMetrics.filter(m => m.comparison_flag === 'lower_than_parent').length;
    const badge = above > below ? 'Above Average' : below > above ? 'Below Average' : 'Average';
    groups.push({ label: section.label, metrics: sectionMetrics, badge });
  }
  const ungrouped = metrics.filter(m => !used.has(m.id) && m.local_value != null);
  if (ungrouped.length > 0) groups.push({ label: 'Other', metrics: ungrouped, badge: '' });
  return groups;
}

// ─── Summary pill selection: top 3 per section, deduplicated ────────
// Metrics that are redundant with each other — if one is shown, skip the rest
const REDUNDANT_GROUPS: string[][] = [
  ['avg_price', 'median_price'],              // don't show both
  ['primary_schools', 'secondary_schools'],    // one school metric is enough
  ['air_quality_no2', 'air_quality_pm25'],     // one AQ is enough
  ['green_cover', 'nearest_park', 'parks_1km', 'green_spaces'],
  ['housing_tenure', 'housing_type'],
  ['median_rent', 'gross_yield'],
  ['deprivation', 'deprivation_income', 'deprivation_employment', 'deprivation_education', 'deprivation_health', 'deprivation_crime', 'deprivation_barriers', 'deprivation_living'],
  ['household_composition', 'household_size'],
  ['crime_rate', 'crime_trend'],
  ['nearest_station', 'stations_in_area'],
  ['broadband', 'mobile_coverage'],
];

// Priority ordering — higher priority metrics shown first in summary pills
const METRIC_PRIORITY: Record<string, number> = {
  avg_price: 1, transaction_volume: 2, price_trend_yoy: 3, crime_rate: 4,
  amenities_15min: 5, primary_schools: 6, deprivation: 7, flood_risk: 8,
  median_rent: 9, council_tax: 10, nearest_station: 11, broadband: 12,
  demographics_overview: 13, ethnicity: 14, epc_energy_score: 15,
  freehold_leasehold: 16, new_build_proportion: 17, official_hpi: 18,
  ptal_score: 19, green_cover: 20, noise: 21, air_quality_no2: 22,
  median_age: 23, household_composition: 24, commute_distance: 25,
  controlling_party: 26, local_authority: 27, water_company: 28,
};

function pickSummaryPills(metrics: Metric[], max = 3): Metric[] {
  // Sort by priority (lower = more important), then by display_priority from registry
  const sorted = [...metrics].sort((a, b) => {
    const pa = METRIC_PRIORITY[a.id] ?? 50;
    const pb = METRIC_PRIORITY[b.id] ?? 50;
    return pa - pb;
  });
  const picked: Metric[] = [];
  const usedGroups = new Set<number>();
  for (const m of sorted) {
    if (picked.length >= max) break;
    // Check if this metric's redundancy group is already represented
    const groupIdx = REDUNDANT_GROUPS.findIndex(g => g.includes(m.id));
    if (groupIdx !== -1 && usedGroups.has(groupIdx)) continue;
    picked.push(m);
    if (groupIdx !== -1) usedGroups.add(groupIdx);
  }
  return picked;
}

// Pill colors based on comparison flag — softer tones than section badge
function pillColor(flag: Metric['comparison_flag']): string {
  if (flag === 'higher_than_parent') return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (flag === 'lower_than_parent') return 'bg-orange-50 text-orange-700 border-orange-200';
  return 'bg-slate-50 text-slate-600 border-slate-200';
}

const IMPROVED_METRIC_IDS = new Set([
  'ethnicity', 'religion', 'crime_rate', 'price_spread',
  'noise', 'air_quality_no2', 'air_quality_pm25',
  'median_age', 'household_composition', 'household_size', 'commute_distance',
  'controlling_party', 'local_authority', 'water_company',
]);

// ─── Main Prototype Page ────────────────────────────────────────────
export default function Prototype() {
  const [query, setQuery] = useState('Surrey');
  const [inputVal, setInputVal] = useState('Surrey');
  const [sessionKey, setSessionKey] = useState<string | null>(null);
  const [areaName, setAreaName] = useState('');
  const [lat, setLat] = useState<number | null>(null);
  const [lon, setLon] = useState<number | null>(null);
  const [boundary, setBoundary] = useState<GeoJSON.Feature | GeoJSON.FeatureCollection | null>(null);
  const [tabData, setTabData] = useState<Record<string, AreaResponse>>({});
  const [activeTab, setActiveTab] = useState<TabName>('Property & Market');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedMetric, setExpandedMetric] = useState<string | null>(null);
  const [expandedSection, setExpandedSection] = useState<string | null>(null);
  const [view, setView] = useState<'redesigned' | 'current'>('redesigned');

  const doSearch = useCallback(async (q: string) => {
    setLoading(true);
    setError(null);
    setTabData({});
    setSessionKey(null);
    setBoundary(null);
    try {
      const resolved = await resolveSearch(q);
      if (!resolved.session_key) { setError(resolved.error || 'Could not resolve search'); return; }
      setSessionKey(resolved.session_key);
      setAreaName(resolved.geo?.entity?.display_name || q);
      setLat(resolved.coordinates?.lat ?? null);
      setLon(resolved.coordinates?.lon ?? null);
      // Fetch boundary + all tabs in parallel
      const [boundaryResult, ...tabResults] = await Promise.allSettled([
        fetchBoundary(resolved.session_key),
        ...ALL_TABS.map(tab => fetchAreaTab(resolved.session_key!, tab)),
      ]);
      if (boundaryResult.status === 'fulfilled' && boundaryResult.value) setBoundary(boundaryResult.value);
      const data: Record<string, AreaResponse> = {};
      tabResults.forEach((r, i) => { if (r.status === 'fulfilled') data[ALL_TABS[i]] = r.value; });
      setTabData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { doSearch(query); }, [query, doSearch]);

  const currentTabMetrics = useMemo(() => tabData[activeTab]?.metrics ?? [], [tabData, activeTab]);
  const sections = useMemo(() => groupMetrics(currentTabMetrics), [currentTabMetrics]);

  return (
    <div className="min-h-screen bg-surface">
      {/* Header */}
      <div className="sticky top-0 z-50 bg-white/95 backdrop-blur-md border-b border-divider">
        <div className="max-w-[1400px] mx-auto px-4 py-3">
          <div className="flex items-center gap-4 flex-wrap">
            <a href="/" className="text-lg font-bold text-brand-600 shrink-0">PropertyPulse</a>
            <span className="text-xs font-medium text-brand-500 bg-brand-50 px-2 py-0.5 rounded-full border border-brand-200">UX Prototype</span>
            <form onSubmit={e => { e.preventDefault(); setQuery(inputVal); }} className="flex gap-2 flex-1 min-w-[200px]">
              <input
                type="text"
                value={inputVal}
                onChange={e => setInputVal(e.target.value)}
                className="flex-1 px-3 py-1.5 rounded-lg bg-surface border border-divider text-sm text-ink placeholder-ink-faint focus:outline-none focus:ring-2 focus:ring-brand-500"
                placeholder="Search postcode, place, county..."
              />
              <button type="submit" className="px-4 py-1.5 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 transition-colors">Search</button>
            </form>
            <div className="flex gap-1.5">
              {DEMO_QUERIES.map(q => (
                <button key={q} onClick={() => { setInputVal(q); setQuery(q); }} className={`px-2.5 py-1 rounded-full text-xs border transition-colors ${query === q ? 'bg-brand-600 border-brand-500 text-white' : 'bg-surface border-divider text-ink-muted hover:border-ink-faint'}`}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Loading / Error */}
      {loading && (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full" />
          <span className="ml-3 text-ink-muted">Loading {query}...</span>
        </div>
      )}
      {error && <div className="max-w-[1400px] mx-auto px-4 py-8"><div className="bg-signal-red-bg border border-signal-red/20 rounded-lg px-4 py-3 text-signal-red text-sm">{error}</div></div>}

      {/* Content: metrics left, map right */}
      {!loading && sessionKey && (
        <div className="max-w-[1400px] mx-auto w-full flex-1 flex flex-col lg:flex-row">
          {/* Left: Metrics Panel */}
          <main className="flex-1 min-w-0 px-4 lg:px-6 py-6">
            {/* Area name + view toggle */}
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-2xl font-bold text-ink">{areaName}</h2>
                <p className="text-xs text-ink-faint">Session: {sessionKey.slice(0, 12)}...</p>
              </div>
              <div className="flex rounded-lg border border-divider overflow-hidden">
                <button onClick={() => setView('redesigned')} className={`px-4 py-1.5 text-sm font-medium transition-colors ${view === 'redesigned' ? 'bg-brand-600 text-white' : 'bg-surface text-ink-muted hover:bg-surface-warm'}`}>Redesigned</button>
                <button onClick={() => setView('current')} className={`px-4 py-1.5 text-sm font-medium transition-colors ${view === 'current' ? 'bg-brand-600 text-white' : 'bg-surface text-ink-muted hover:bg-surface-warm'}`}>Current</button>
              </div>
            </div>

            {/* Tabs */}
            <div className="flex gap-1 overflow-x-auto pb-3 mb-4 border-b border-divider">
              {ALL_TABS.map(tab => {
                const TabIcon = TAB_ICONS[tab];
                return (
                  <button
                    key={tab}
                    onClick={() => { setActiveTab(tab); setExpandedMetric(null); setExpandedSection(null); }}
                    className={`shrink-0 flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${activeTab === tab ? 'bg-brand-600 text-white' : 'text-ink-muted hover:bg-surface-warm'}`}
                  >
                    {TabIcon && (
                      <div className={`w-6 h-6 rounded-md flex items-center justify-center ${activeTab === tab ? 'bg-white/20' : 'bg-blue-50'}`}>
                        <TabIcon size={14} className={activeTab === tab ? 'text-white' : 'text-blue-700'} />
                      </div>
                    )}
                    {tab.split(' & ')[0]}
                  </button>
                );
              })}
            </div>

            {/* Metrics */}
            {view === 'redesigned' ? (
              <div className="space-y-2">
                {sections.map(section => {
                  const isSectionOpen = expandedSection === section.label;
                  return (
                    <div key={section.label} className="rounded-2xl border border-divider bg-white overflow-hidden shadow-sm">
                      {/* Section header — always visible, clickable */}
                      <button
                        onClick={() => {
                          setExpandedSection(isSectionOpen ? null : section.label);
                          setExpandedMetric(null);
                        }}
                        className="w-full flex items-center gap-3 px-5 py-3 text-left hover:bg-surface-warm/50 transition-colors"
                      >
                        {(() => {
                          const SIcon = SECTION_ICONS[section.label];
                          return SIcon ? (
                            <div className="w-7 h-7 rounded-md bg-amber-50 flex items-center justify-center shrink-0">
                              <SIcon size={15} className="text-amber-700" />
                            </div>
                          ) : null;
                        })()}
                        <h3 className="text-sm font-semibold text-ink">{section.label}</h3>
                        <div className="flex-1" />
                        <SectionBadge metrics={section.metrics} />
                        {isSectionOpen
                          ? <CircleMinus size={20} className="text-ink-faint shrink-0" />
                          : <CirclePlus size={20} className="text-ink-faint shrink-0" />
                        }
                      </button>

                      {/* Collapsed summary — top 3 pills, deduplicated, colored */}
                      {!isSectionOpen && (() => {
                        const pills = pickSummaryPills(section.metrics, 3);
                        const remaining = section.metrics.length - pills.length;
                        return (
                          <div className="px-5 pb-3 flex flex-wrap gap-2">
                            {pills.map(m => (
                              <span key={m.id} className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs border ${pillColor(m.comparison_flag)}`}>
                                <span className="truncate max-w-[120px]">{m.name}</span>
                                <span className="font-semibold font-mono tabular-nums">{formatValue(m.local_value, m.unit)}</span>
                              </span>
                            ))}
                            {remaining > 0 && (
                              <span className="inline-flex items-center px-2.5 py-1 rounded-lg bg-surface-warm text-xs text-ink-faint border border-divider/50">
                                +{remaining} more
                              </span>
                            )}
                          </div>
                        );
                      })()}

                      {/* Expanded section — full metric rows */}
                      {isSectionOpen && (
                        <div className="divide-y divide-divider/50 border-t border-divider/50">
                          {section.metrics.map(m => {
                            const isExpanded = expandedMetric === m.id;
                            const hasRedesign = IMPROVED_METRIC_IDS.has(m.id);
                            return (
                              <div key={m.id} className={isExpanded ? 'bg-brand-50/30 border-l-2 border-l-brand-500' : ''}>
                                <button
                                  onClick={() => setExpandedMetric(isExpanded ? null : m.id)}
                                  className="w-full flex items-center gap-4 px-5 py-3.5 text-left hover:bg-surface-warm/50 transition-colors"
                                >
                                  <div className="flex-1 min-w-0">
                                    <div className="text-sm font-semibold text-ink truncate">{m.name}</div>
                                    {m.decision_question && <div className="text-[11px] text-ink-faint truncate">{m.decision_question}</div>}
                                  </div>
                                  <div className="text-right shrink-0">
                                    <div className="text-lg font-bold font-mono text-ink tabular-nums">{formatValue(m.local_value, m.unit)}</div>
                                    {m.trend?.direction && m.trend.direction !== 'flat' && (
                                      <div className={`text-[11px] font-medium ${m.trend.direction === 'up' ? 'text-signal-green' : 'text-signal-amber'}`}>
                                        {m.trend.direction === 'up' ? '↑' : '↓'} {m.trend.value != null ? formatValue(m.trend.value, m.unit) : ''} {m.trend.window_label || ''}
                                      </div>
                                    )}
                                  </div>
                                  <div className="w-28 text-right shrink-0">
                                    {m.parent_value != null ? (
                                      <span className="text-sm text-ink-muted"><CompIcon flag={m.comparison_flag} /> {formatValue(m.parent_value, m.unit)}</span>
                                    ) : <span className="text-ink-faint">—</span>}
                                  </div>
                                  <div className="w-28 shrink-0">
                                    {m.capsule?.text ? (
                                      <span className={`inline-block px-2.5 py-1 rounded-lg text-xs font-medium ${m.capsule.tone === 'positive' ? 'bg-signal-green-bg text-signal-green border border-signal-green/20' : m.capsule.tone === 'cautionary' ? 'bg-signal-amber-bg text-signal-amber border border-signal-amber/20' : 'bg-surface-warm text-ink-muted border border-divider'}`}>
                                        {m.capsule.text.length > 25 ? m.capsule.text.slice(0, 22) + '...' : m.capsule.text}
                                      </span>
                                    ) : null}
                                  </div>
                                  <svg className={`w-4 h-4 text-ink-faint shrink-0 transition-transform ${isExpanded ? 'rotate-90' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
                                </button>
                                {isExpanded && m.details && (
                                  <div className="px-5 pb-4 pt-1 bg-surface-warm/30">
                                    {hasRedesign ? (
                                      <div>
                                        <div className="text-xs text-brand-600 font-medium mb-2 uppercase tracking-wider">Redesigned View</div>
                                        <RedesignedDetail metric={m} />
                                      </div>
                                    ) : (
                                      <div className="text-sm text-ink-faint italic">Uses existing renderer (no redesign needed for this metric)</div>
                                    )}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              /* Current view — flat list */
              <div className="space-y-1">
                {currentTabMetrics.filter(m => m.local_value != null).map(m => {
                  const isExpanded = expandedMetric === m.id;
                  return (
                    <div key={m.id} className="rounded-xl border border-divider bg-white shadow-sm">
                      <button onClick={() => setExpandedMetric(isExpanded ? null : m.id)} className="w-full flex items-center gap-4 px-5 py-3.5 text-left hover:bg-surface-warm/50 transition-colors">
                        <div className="flex-1 min-w-0"><div className="text-sm font-semibold text-ink truncate">{m.name}</div></div>
                        <div className="text-lg font-bold font-mono text-ink tabular-nums">{formatValue(m.local_value, m.unit)}</div>
                        <div className="w-28 text-right shrink-0">
                          {m.parent_value != null ? <span className="text-sm text-ink-muted"><CompIcon flag={m.comparison_flag} /> {formatValue(m.parent_value, m.unit)}</span> : <span className="text-ink-faint">—</span>}
                        </div>
                        <svg className={`w-4 h-4 text-ink-faint shrink-0 transition-transform ${isExpanded ? 'rotate-90' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
                      </button>
                      {isExpanded && m.details && (
                        <div className="px-5 pb-4 pt-1 border-t border-divider/50">
                          <div className="text-xs text-ink-faint uppercase tracking-wider mb-2">Current generic grid view</div>
                          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
                            {Object.entries(m.details).filter(([k, v]) => v != null && typeof v !== 'object' && !k.endsWith('_note') && k !== 'detail_unit' && k !== 'trend' && k !== 'breakdown_type' && k !== 'count_label').map(([k, v]) => {
                              const isPct = k.includes('pct') || (m.details as Record<string, unknown>).detail_unit === '%';
                              const display = typeof v === 'number' ? (isPct ? (v as number).toFixed(1) + '%' : (v as number).toLocaleString('en-GB', { maximumFractionDigits: 1 })) : String(v);
                              return (
                                <div key={k} className="p-2.5 rounded-xl bg-surface">
                                  <div className="text-[11px] text-ink-faint uppercase tracking-wide font-medium">{k.replace(/_/g, ' ').replace(/pct /g, '% ')}</div>
                                  <div className="text-sm font-semibold text-ink mt-0.5">{display}</div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* School Results Sparkline Demo */}
            {activeTab === 'Community & Education' && view === 'redesigned' && (
              <div className="mt-8 rounded-2xl border border-brand-200 bg-brand-50/50 p-6">
                <h3 className="text-lg font-bold text-brand-700 mb-1">School Results — Redesigned View</h3>
                <p className="text-sm text-ink-muted mb-4">Instead of raw multi-year tables, school results show sparklines with trend summaries. Expand a school above to see current data, or view the layout preview below.</p>
                <SchoolResultsSparkline school={{}} />
              </div>
            )}
          </main>

          {/* Right: Map Sidebar (desktop) */}
          {lat != null && lon != null && (
            <aside className="hidden lg:block w-[40%] shrink-0 sticky top-[53px] h-[calc(100vh-53px)] p-4 pl-0">
              <div className="rounded-2xl overflow-hidden shadow-sm h-full relative border border-divider">
                <Suspense fallback={<div className="w-full h-full bg-surface-warm animate-pulse" />}>
                  <MapView lat={lat} lon={lon} boundary={boundary as GeoJSON.Feature | null} />
                </Suspense>
              </div>
            </aside>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="border-t border-divider mt-12 py-6 text-center text-xs text-ink-faint">
        Prototype page — does not affect the main portal. <a href="/" className="text-brand-600 hover:underline">Back to main site</a>
      </div>
    </div>
  );
}
